"""
根据 INFORMATION_SCHEMA 解析「订单明细」表及字段，兼容不同业务库命名。

已知：
- 本地 agent 样例库可能为 order_goods + orders.order_id
- 线上 shixunwang 常见为 orders_items + orders.id（明细 order_id 引用主表 id）
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

import pymysql

from app.business_insights import schema as S


@dataclass(frozen=True)
class OrderItemsSpec:
    items_table: str
    """明细表上指向订单主表的列名（如 order_id）"""
    items_order_fk: str
    """订单主表主键列名（id 或 order_id）"""
    orders_pk: str
    goods_name_col: str
    price_col: str
    """数量列，按顺序参与 COALESCE"""
    qty_cols: tuple[str, ...]
    """商品类别列；无则 None（类别分布归为「未分类」）"""
    category_col: Optional[str] = None
    """关联商品主档；无则无法 JOIN 补规格/单位"""
    goods_id_col: Optional[str] = None
    """明细表上的规格、单位列（优先于商品表）"""
    item_spec_col: Optional[str] = None
    item_unit_col: Optional[str] = None


@dataclass(frozen=True)
class GoodsCatalogSpec:
    """商品主档表：用于订单明细缺规格/单位时 LEFT JOIN 补全。"""

    table: str
    pk_col: str
    spec_col: Optional[str]
    unit_col: Optional[str]


_spec_cache: dict[str, Optional[OrderItemsSpec]] = {}
_goods_catalog_cache: dict[str, Optional[GoodsCatalogSpec]] = {}


def _norm_cols(rows: list[dict]) -> dict[str, set[str]]:
    by_table: dict[str, set[str]] = {}
    for r in rows:
        t = str(r.get("TABLE_NAME") or "")
        c = str(r.get("COLUMN_NAME") or "").lower()
        if t and c:
            by_table.setdefault(t, set()).add(c)
    return by_table


def _pick_orders_pk(orders_cols: set[str]) -> Optional[str]:
    if "order_id" in orders_cols:
        return "order_id"
    if "id" in orders_cols:
        return "id"
    return None


_CATEGORY_COL_CANDIDATES: Tuple[str, ...] = (
    "goods_category",
    "category_name",
    "cate_name",
    "product_category",
    "big_cate_name",
    "big_category_name",
    "type_name",
    "cate_title",
    "class_name",
)


def _pick_category_col(cols: set[str]) -> Optional[str]:
    for c in _CATEGORY_COL_CANDIDATES:
        if c in cols:
            return c
    return None


def _pick_goods_id_col(cols: set[str]) -> Optional[str]:
    for c in ("goods_id", "product_id", "gid", "sku_id"):
        if c in cols:
            return c
    return None


def _pick_item_spec_col(cols: set[str]) -> Optional[str]:
    for c in (
        "goods_spec",
        "spec",
        "specification",
        "guige",
        "goods_guige",
        "norms",
        "packing_spec",
        "standard",
        "attr_value",
    ):
        if c in cols:
            return c
    return None


def _pick_item_unit_col(cols: set[str]) -> Optional[str]:
    for c in (
        "unit",
        "goods_unit",
        "sale_unit",
        "unit_name",
        "measure_unit",
        "goods_unit_name",
        "packing_unit",
    ):
        if c in cols:
            return c
    return None


def _find_qty_cols(cols: set[str]) -> tuple[str, ...]:
    """按优先级选取数量列（用于 COALESCE）。"""
    candidates = (
        ("goods_num",),
        ("needqty", "sendqty", "receiveqty"),
        ("num", "quantity", "qty"),
        ("sendqty", "receiveqty"),
    )
    for tup in candidates:
        found = tuple(c for c in tup if c in cols)
        if found:
            return found
    return ()


def _match_orders_items_table(
    table: str,
    cols: set[str],
    orders_pk: str,
) -> Optional[OrderItemsSpec]:
    """尝试将某表匹配为订单明细行表。"""
    lk = {
        "order_id": "order_id",
        "goods_name": "goods_name",
        "price": ("goods_price", "sale_price", "price", "unit_price", "orig_sale_price"),
    }
    order_fk = None
    for c in ("order_id", "orders_id", "pid"):
        if c in cols:
            order_fk = c
            break
    if not order_fk:
        return None
    gname = None
    for c in ("goods_name", "product_name", "name", "goods_title"):
        if c in cols:
            gname = c
            break
    if not gname:
        return None
    price_col = None
    for c in lk["price"]:
        if c in cols:
            price_col = c
            break
    if not price_col:
        return None
    qty_cols = _find_qty_cols(cols)
    if not qty_cols:
        return None
    return OrderItemsSpec(
        items_table=table,
        items_order_fk=order_fk,
        orders_pk=orders_pk,
        goods_name_col=gname,
        price_col=price_col,
        qty_cols=qty_cols,
        category_col=_pick_category_col(cols),
        goods_id_col=_pick_goods_id_col(cols),
        item_spec_col=_pick_item_spec_col(cols),
        item_unit_col=_pick_item_unit_col(cols),
    )


def resolve_order_items_spec(conn, database: str, orders_table: str = S.ORDERS_TABLE) -> Optional[OrderItemsSpec]:
    """
    连接须为 DictCursor。结果按 database 缓存，避免每请求扫 INFORMATION_SCHEMA。
    """
    cache_key = f"{database}:{orders_table}"
    if cache_key in _spec_cache:
        return _spec_cache[cache_key]

    explicit_table = os.environ.get("INSIGHTS_ORDER_ITEMS_TABLE", "").strip()
    explicit_fk = os.environ.get("INSIGHTS_ORDER_ITEMS_FK", "").strip()
    explicit_pk = os.environ.get("INSIGHTS_ORDERS_PK", "").strip()
    explicit_name = os.environ.get("INSIGHTS_ORDER_ITEMS_NAME_COL", "").strip()
    explicit_price = os.environ.get("INSIGHTS_ORDER_ITEMS_PRICE_COL", "").strip()
    explicit_qty = os.environ.get("INSIGHTS_ORDER_ITEMS_QTY_COLS", "").strip()
    explicit_category = os.environ.get("INSIGHTS_ORDER_ITEMS_CATEGORY_COL", "").strip()
    explicit_gid = os.environ.get("INSIGHTS_ORDER_ITEMS_GOODS_ID_COL", "").strip()
    explicit_isc = os.environ.get("INSIGHTS_ORDER_ITEMS_SPEC_COL", "").strip()
    explicit_iuc = os.environ.get("INSIGHTS_ORDER_ITEMS_UNIT_COL", "").strip()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            """,
            (database,),
        )
        raw = cur.fetchall()

    by_table = _norm_cols([dict(r) for r in raw])
    orders_cols = by_table.get(orders_table, set())
    orders_pk = explicit_pk or _pick_orders_pk(orders_cols)
    if not orders_pk:
        _spec_cache[cache_key] = None
        return None

    if explicit_table and explicit_table in by_table:
        cols = by_table[explicit_table]
        fk = explicit_fk or ("order_id" if "order_id" in cols else None)
        gname = explicit_name or ("goods_name" if "goods_name" in cols else None)
        price = explicit_price
        if not fk or not gname:
            _spec_cache[cache_key] = None
            return None
        if explicit_qty:
            qty_parts = tuple(x.strip() for x in explicit_qty.split(",") if x.strip())
            if not all(q in cols for q in qty_parts):
                _spec_cache[cache_key] = None
                return None
        else:
            qty_parts = _find_qty_cols(cols)
        if not price:
            for c in ("sale_price", "goods_price", "price", "unit_price"):
                if c in cols:
                    price = c
                    break
        if not price or not qty_parts:
            _spec_cache[cache_key] = None
            return None
        cat_col: Optional[str] = None
        if explicit_category:
            if explicit_category not in cols:
                _spec_cache[cache_key] = None
                return None
            cat_col = explicit_category
        else:
            cat_col = _pick_category_col(cols)
        gid_col = (
            explicit_gid
            if explicit_gid and explicit_gid.lower() in cols
            else _pick_goods_id_col(cols)
        )
        isc = (
            explicit_isc
            if explicit_isc and explicit_isc.lower() in cols
            else _pick_item_spec_col(cols)
        )
        iuc = (
            explicit_iuc
            if explicit_iuc and explicit_iuc.lower() in cols
            else _pick_item_unit_col(cols)
        )
        spec = OrderItemsSpec(
            items_table=explicit_table,
            items_order_fk=fk,
            orders_pk=explicit_pk or orders_pk,
            goods_name_col=gname,
            price_col=price,
            qty_cols=qty_parts,
            category_col=cat_col,
            goods_id_col=gid_col,
            item_spec_col=isc,
            item_unit_col=iuc,
        )
        _spec_cache[cache_key] = spec
        return spec

    preference = (
        "orders_items",
        "order_goods",
        "order_products",
        "orders_goods",
    )
    candidates: list[tuple[int, str, OrderItemsSpec]] = []
    for table, cols in by_table.items():
        if table == orders_table:
            continue
        spec = _match_orders_items_table(table, cols, orders_pk)
        if not spec:
            continue
        score = 0
        tl = table.lower()
        if tl in preference:
            score = 100 - preference.index(tl)
        elif "item" in tl or "good" in tl or "product" in tl:
            score = 10
        candidates.append((score, table, spec))

    if not candidates:
        _spec_cache[cache_key] = None
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    spec = candidates[0][2]
    _spec_cache[cache_key] = spec
    return spec


def build_qty_sql(alias: str, qty_cols: tuple[str, ...]) -> str:
    parts = [f"`{alias}`.`{c}`" for c in qty_cols]
    if len(parts) == 1:
        return f"COALESCE({parts[0]}, 0)"
    return "COALESCE(" + ", ".join(parts + ["0"]) + ")"


def coalesce_item_goods_trim_sql(
    alias_line: str,
    col_line: Optional[str],
    alias_goods: Optional[str],
    col_goods: Optional[str],
) -> str:
    """COALESCE(明细列, 商品表列)，空串视为 NULL；无列则返回 SQL NULL。"""
    parts: list[str] = []
    if col_line:
        parts.append(
            f"NULLIF(TRIM(CAST(`{alias_line}`.`{col_line}` AS CHAR)), '')"
        )
    if alias_goods and col_goods:
        parts.append(
            f"NULLIF(TRIM(CAST(`{alias_goods}`.`{col_goods}` AS CHAR)), '')"
        )
    if not parts:
        return "NULL"
    if len(parts) == 1:
        return parts[0]
    return "COALESCE(" + ", ".join(parts) + ")"


def resolve_goods_catalog_spec(
    conn,
    database: str,
    orders_table: str,
    items_table: str,
) -> Optional[GoodsCatalogSpec]:
    """
    解析商品主档表（与订单明细 goods_id 等关联）。
    仅在能识别出规格或单位列时返回（避免无意义 JOIN）；可用环境变量强制指定。
    """
    cache_key = f"{database}:goods_catalog"
    if cache_key in _goods_catalog_cache:
        return _goods_catalog_cache[cache_key]

    explicit_table = os.environ.get("INSIGHTS_GOODS_TABLE", "").strip()
    explicit_pk = os.environ.get("INSIGHTS_GOODS_PK_COL", "").strip()
    explicit_spec = os.environ.get("INSIGHTS_GOODS_SPEC_COL", "").strip()
    explicit_unit = os.environ.get("INSIGHTS_GOODS_UNIT_COL", "").strip()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            """,
            (database,),
        )
        raw = cur.fetchall()

    by_table = _norm_cols([dict(r) for r in raw])

    def _pick_pk(cols: set[str]) -> Optional[str]:
        if explicit_pk and explicit_pk.lower() in cols:
            return explicit_pk
        if "id" in cols:
            return "id"
        if "goods_id" in cols:
            return "goods_id"
        return None

    def _try_table(table: str, cols: set[str]) -> Optional[GoodsCatalogSpec]:
        pk = _pick_pk(cols)
        if not pk:
            return None
        if not any(
            x in cols for x in ("goods_name", "name", "goods_title", "product_name")
        ):
            return None
        spec_c = (
            explicit_spec
            if explicit_spec and explicit_spec.lower() in cols
            else _pick_item_spec_col(cols)
        )
        unit_c = (
            explicit_unit
            if explicit_unit and explicit_unit.lower() in cols
            else _pick_item_unit_col(cols)
        )
        if spec_c is None and unit_c is None:
            return None
        return GoodsCatalogSpec(
            table=table, pk_col=pk, spec_col=spec_c, unit_col=unit_c
        )

    if explicit_table and explicit_table in by_table:
        if explicit_table in (orders_table, items_table):
            _goods_catalog_cache[cache_key] = None
            return None
        spec = _try_table(explicit_table, by_table[explicit_table])
        _goods_catalog_cache[cache_key] = spec
        return spec

    preference = ("goods", "shop_goods", "goods_info", "products", "product")
    candidates: list[tuple[int, str, GoodsCatalogSpec]] = []
    for table, cols in by_table.items():
        if table == orders_table or table == items_table:
            continue
        tl = table.lower()
        if tl not in preference and "good" not in tl and "product" not in tl:
            continue
        built = _try_table(table, cols)
        if not built:
            continue
        score = 0
        if tl in preference:
            score = 100 - preference.index(tl)
        candidates.append((score, table, built))

    if not candidates:
        _goods_catalog_cache[cache_key] = None
        return None

    candidates.sort(key=lambda x: (-x[0], x[1]))
    out = candidates[0][2]
    _goods_catalog_cache[cache_key] = out
    return out


def clear_order_items_spec_cache() -> None:
    _spec_cache.clear()
    _goods_catalog_cache.clear()
