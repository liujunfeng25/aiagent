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


_spec_cache: dict[str, Optional[OrderItemsSpec]] = {}


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
        spec = OrderItemsSpec(
            items_table=explicit_table,
            items_order_fk=fk,
            orders_pk=explicit_pk or orders_pk,
            goods_name_col=gname,
            price_col=price,
            qty_cols=qty_parts,
            category_col=cat_col,
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


def clear_order_items_spec_cache() -> None:
    _spec_cache.clear()
