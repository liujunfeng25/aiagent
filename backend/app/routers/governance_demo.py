# 系统治理：智能分单（只读抽样业务库订单；确认结果写入本地文件，不写业务库）
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pymysql
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.business_insights import schema as S
from app.business_insights.order_items_resolver import build_qty_sql, resolve_order_items_spec
from app.services.amap_geocode import amap_key, geocode_address, haversine_km
from app.services.jjj_delivery_geocode import geocode_single_for_delivery_route
from app.services.business_mysql import BusinessMysqlConfig, resolve_business_mysql
from app.services.db_connector import get_connection
router = APIRouter()

_MAX_SAMPLE_ORDERS = 12
_MIN_LINE_ITEMS = 2
_SUPPLIER_POOL_SIZE = 24
_SH_TZ = ZoneInfo("Asia/Shanghai")
_GOODS_LIMIT_PER_ORDER = 80
_MAX_CONFIRM_LINES = 2000
_STRATEGY_KEYS = frozenset({"composite", "rating", "price", "distance"})
_DEFAULT_MARKET_ADDRESS = (
    "北京市丰台区西四环中路136号京丰岳各庄农副产品批发市场"
)
# 明细里常见「同市场不同档口」长地址，地理编码应对齐到同一关键点，避免同址不同距。
_MARKET_GEO_UNIFY_SUBSTR = "京丰岳各庄农副产品批发市场"
# 新发地片区档口地址长短不一，统一到同一编码键，避免同市场多点漂移。
_XINFADI_MARKER_SUBSTR = "新发地"
_XINFADI_GEOCODE_KEY = "北京市丰台区新发地农产品批发市场"
# 智能分单：业务约定客户与供货方均在北京市，高德统一加 city，并用市域 bbox 过滤误解析。
_SMART_SPLIT_AMAP_CITY = "北京"


# 供货方地址无法地理编码时回退；智能排线固定起点（仓/集散点）
_SMART_SPLIT_ADDRESS_GEO_FALLBACK = (
    "中国北京市丰台区梅市口东路与西四环中路辅路交叉口东160米"
)
DELIVERY_ROUTE_DEPOT_ADDRESS = _SMART_SPLIT_ADDRESS_GEO_FALLBACK
_RATINGS_FILENAME = "supplier_ratings.json"


def _coord_plausible_beijing_metro(lng: float, lat: float) -> bool:
    """北京市域大致范围（略放宽），坐标落在外省时视为无效。"""
    return 115.7 <= lng <= 117.6 and 39.4 <= lat <= 41.1


def _strategies_list() -> list[dict[str, str]]:
    return [
        {"key": "composite", "label": "综合表现"},
        {"key": "rating", "label": "评分优先"},
        {"key": "price", "label": "价格优先"},
        {"key": "distance", "label": "距离优先"},
    ]


def _data_dir() -> Path:
    base = Path(__file__).resolve().parent.parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _confirmations_path() -> Path:
    return _data_dir() / "smart_split_confirmations.jsonl"


def _confirmation_dedupe_key(rec: dict[str, Any]) -> tuple[str, int]:
    p = rec.get("payload") or {}
    sn = str(p.get("order_sn") or "").strip()
    try:
        oid = int(p.get("order_id"))
    except (TypeError, ValueError):
        oid = 0
    return (sn, oid)


def _load_confirmation_records_raw(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            rec = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("id"):
            out.append(rec)
    return out


def _write_confirmations_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(path)


def _load_and_compact_confirmations(path: Path) -> tuple[list[dict[str, Any]], int]:
    """
    同一 (order_sn, order_id) 仅保留 saved_at 最新一条；必要时写回磁盘。
    返回 (全部记录按时间升序, 删除的重复条数)。
    """
    raw = _load_confirmation_records_raw(path)
    if not raw:
        return [], 0
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for rec in raw:
        k = _confirmation_dedupe_key(rec)
        if k[1] == 0 and not k[0]:
            continue
        prev = by_key.get(k)
        if prev is None or str(rec.get("saved_at") or "") > str(
            prev.get("saved_at") or ""
        ):
            by_key[k] = rec
    new_list = sorted(by_key.values(), key=lambda r: str(r.get("saved_at") or ""))
    removed = len(raw) - len(new_list)
    if removed > 0:
        try:
            _write_confirmations_atomic(path, new_list)
        except OSError:
            return raw, 0
    return new_list, removed


def _blocked_orders_from_recs(records: list[dict[str, Any]]) -> tuple[set[int], set[str]]:
    ids: set[int] = set()
    sns: set[str] = set()
    for rec in records:
        p = rec.get("payload") or {}
        sn = str(p.get("order_sn") or "").strip()
        if sn:
            sns.add(sn)
        try:
            ids.add(int(p.get("order_id")))
        except (TypeError, ValueError):
            pass
    return ids, sns


def _confirmation_is_duplicate(
    records: list[dict[str, Any]], order_id: int, order_sn: str
) -> bool:
    sn = (order_sn or "").strip()
    for rec in records:
        p = rec.get("payload") or {}
        try:
            if int(p.get("order_id")) == int(order_id):
                return True
        except (TypeError, ValueError):
            pass
        if str(p.get("order_sn") or "").strip() == sn and sn:
            return True
    return False


def _ratings_path() -> Path:
    return _data_dir() / _RATINGS_FILENAME


def _load_ratings_dict() -> dict[str, float]:
    p = _ratings_path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in raw.items():
            try:
                fv = float(v)
                if 3.0 <= fv <= 5.0:
                    out[str(k)] = round(fv, 2)
            except (TypeError, ValueError):
                continue
        return out
    except (OSError, json.JSONDecodeError):
        return {}


def _save_ratings_dict(d: dict[str, float]) -> None:
    _data_dir().mkdir(parents=True, exist_ok=True)
    clean = {k: round(float(v), 2) for k, v in d.items() if 3.0 <= float(v) <= 5.0}
    _ratings_path().write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def _table_columns_exact(cur, database: str, table: str) -> dict[str, str]:
    """lowercase -> exact COLUMN_NAME for SQL backticks."""
    cur.execute(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        (database, table),
    )
    m: dict[str, str] = {}
    for r in cur.fetchall():
        c = str(r["COLUMN_NAME"])
        m[c.lower()] = c
    return m


def _pick_goods_id_col(cols_lower: set[str]) -> Optional[str]:
    for c in (
        "goods_id",
        "product_id",
        "commodity_id",
        "spu_id",
        "sku_id",
        "item_id",
        "food_id",
        "material_id",
        "gid",
    ):
        if c in cols_lower:
            return c
    return None


def _resolve_supplier_goods_meta(
    cur, database: str
) -> Optional[tuple[str, str, str, str]]:
    try:
        cur.execute(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
              AND TABLE_TYPE = 'BASE TABLE'
              AND LOWER(TABLE_NAME) = 'supplier_goods'
            LIMIT 1
            """,
            (database,),
        )
        row = cur.fetchone()
        if not row or not row.get("TABLE_NAME"):
            return None
        tbl = str(row["TABLE_NAME"])
        if not _safe_ident(tbl):
            return None
        cmap = _table_columns_exact(cur, database, tbl)
        cl = set(cmap.keys())
        gkey = _pick_goods_id_col(cl)
        if not gkey:
            return None
        pkey = None
        for c in ("price", "sale_price", "goods_price", "unit_price"):
            if c in cl:
                pkey = c
                break
        skey = None
        for c in (
            "supplier_id",
            "sup_id",
            "sid",
            "vendor_id",
            "user_id",
            "member_id",
            "shop_id",
            "provider_id",
            "dealer_id",
        ):
            if c in cl:
                skey = c
                break
        if not pkey or not skey:
            return None
        return (tbl, cmap[skey], cmap[gkey], cmap[pkey])
    except pymysql.MySQLError:
        return None


def _rating_for_supplier_db(
    db_id: Optional[int], name: str, ratings: dict[str, float]
) -> float:
    if db_id is not None:
        k = str(db_id)
        if k in ratings:
            return max(3.0, min(5.0, float(ratings[k])))
    h = _stable_u32(f"{db_id or name}|srating")
    return round(3.0 + (h % 201) / 100.0, 2)


def _ensure_ratings_for_ids(
    supplier_db_ids: list[int], ratings: dict[str, float]
) -> dict[str, float]:
    changed = False
    for sid in supplier_db_ids:
        k = str(sid)
        if k not in ratings:
            h = _stable_u32(k + ":init")
            ratings[k] = round(3.0 + (h % 201) / 100.0, 2)
            changed = True
    if changed:
        _save_ratings_dict(ratings)
    return ratings


def _saved_at_date_sh(saved_at: str) -> Optional[date]:
    try:
        s = (saved_at or "").strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_SH_TZ).date()
    except (TypeError, ValueError):
        return None


def _today_sh():
    return datetime.now(_SH_TZ).date()


def _cfg_or_503() -> BusinessMysqlConfig:
    cfg = resolve_business_mysql()
    if not cfg:
        raise HTTPException(
            status_code=503,
            detail="未配置业务库连接：请在环境变量中设置 INSIGHTS_MYSQL_HOST（及 PORT/USER/PASSWORD/DATABASE）。",
        )
    return cfg


def _mysql_connect(cfg: BusinessMysqlConfig):
    try:
        return get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
    except pymysql.MySQLError as e:
        raise HTTPException(status_code=503, detail=f"无法连接业务库：{e}") from e


def _jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def _stable_u32(s: str) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)


def _geocode_key_for_supplier_address(addr: str) -> str:
    """统一同一批发市场内各档口地址的编码键，避免同市场不同字符串算出不同运距。"""
    a = (addr or "").strip()
    if not a:
        return _DEFAULT_MARKET_ADDRESS
    if _MARKET_GEO_UNIFY_SUBSTR in a or _DEFAULT_MARKET_ADDRESS in a:
        return _DEFAULT_MARKET_ADDRESS
    if _XINFADI_MARKER_SUBSTR in a:
        return _XINFADI_GEOCODE_KEY
    return a


def _clean_customer_geocode_query(raw: str) -> str:
    """去掉客户展示名里的编码前缀（如 XC），提高高德命中率。"""
    s = (raw or "").strip()
    if not s:
        return ""
    s2 = re.sub(r"^[A-Za-z0-9_-]+", "", s).strip()
    return s2 or s


def _geocode_customer_for_distance(raw_name: str) -> Optional[tuple[float, float]]:
    """订单客户展示名 → 经纬度；固定北京市 city，减少偏到外省的误解析。"""
    if not amap_key():
        return None
    q = _clean_customer_geocode_query(raw_name)
    if not q:
        return None
    city = _SMART_SPLIT_AMAP_CITY
    coord = geocode_address(q, city=city)
    if coord is None and not q.startswith("北京"):
        coord = geocode_address(f"北京市{q}", city=city)
    if coord is not None:
        lng, lat = coord
        if not _coord_plausible_beijing_metro(lng, lat):
            return None
    return coord


def _demo_distance_km_for_address(addr: str) -> float:
    """无有效经纬度时的演示运距：同城合理区间，避免 30～280km 误导。"""
    key = _geocode_key_for_supplier_address(addr)
    h = _stable_u32(key + ":demo_km")
    return float(6 + (h % 34))


def _safe_ident(s: str) -> bool:
    return bool(s and re.match(r"^[a-zA-Z0-9_]+$", s))


def _warn_merge(a: Optional[str], b: str) -> str:
    if a and b:
        return f"{a},{b}"
    return a or b


_MIN_SUPPLIERS_FOR_DEMO = 3


def _resolve_supplier_table_name(cur, database: str) -> Optional[str]:
    try:
        cur.execute(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s
              AND TABLE_TYPE = 'BASE TABLE'
              AND LOWER(TABLE_NAME) = 'supplier'
            LIMIT 1
            """,
            (database,),
        )
        row = cur.fetchone()
        if not row or not row.get("TABLE_NAME"):
            return None
        t = str(row["TABLE_NAME"])
        return t if _safe_ident(t) else None
    except pymysql.MySQLError:
        return None


def _load_suppliers_realname_address(
    cur, database: str
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """
    从 supplier 表读取 realname；address 可为空，空则用默认批发市场地址（便于距离策略/高德）。
    """
    tbl = _resolve_supplier_table_name(cur, database)
    if not tbl:
        return [], "no_supplier_table"

    try:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """,
            (database, tbl),
        )
        cols = {str(r["COLUMN_NAME"]).lower() for r in cur.fetchall()}
    except pymysql.MySQLError:
        return [], "supplier_columns_failed"

    if "realname" not in cols:
        return [], "supplier_missing_realname"

    has_id = "id" in cols and _safe_ident("id")
    has_addr = "address" in cols and _safe_ident("address")
    if has_id:
        addr_sel = "TRIM(`address`)" if has_addr else "''"
        cur.execute(
            f"""
            SELECT `id` AS db_id, TRIM(`realname`) AS realname, {addr_sel} AS address
            FROM `{tbl}`
            WHERE `realname` IS NOT NULL AND TRIM(`realname`) != ''
            ORDER BY `id` ASC
            LIMIT 64
            """
        )
    else:
        addr_sel = "TRIM(`address`)" if has_addr else "''"
        cur.execute(
            f"""
            SELECT {addr_sel} AS address, TRIM(`realname`) AS realname
            FROM `{tbl}`
            WHERE `realname` IS NOT NULL AND TRIM(`realname`) != ''
            LIMIT 64
            """
        )

    raw = [_jsonable_row(dict(r)) for r in cur.fetchall()]
    out: list[dict[str, Any]] = []
    seen_name: set[str] = set()
    for r in raw:
        name = str(r.get("realname") or "").strip()
        addr = str(r.get("address") or "").strip()
        if not name or name in seen_name:
            continue
        if not addr:
            addr = _DEFAULT_MARKET_ADDRESS
        seen_name.add(name)
        row_d: dict[str, Any] = {"name": name, "address": addr}
        if has_id and r.get("db_id") is not None:
            try:
                row_d["db_id"] = int(r["db_id"])
            except (TypeError, ValueError):
                row_d["db_id"] = None
        out.append(row_d)
        if len(out) >= _SUPPLIER_POOL_SIZE:
            break

    if len(out) < _MIN_SUPPLIERS_FOR_DEMO:
        return [], "supplier_pool_too_small"

    return out, None


_MAX_QUOTED_SUPPLIERS = 400


def _load_suppliers_by_db_ids(
    cur, database: str, db_ids: list[int]
) -> tuple[list[dict[str, Any]], Optional[str]]:
    """按 supplier.id 批量加载 realname/address（仅用于已有 supplier_goods 报价的供方）。"""
    if not db_ids:
        return [], None
    tbl = _resolve_supplier_table_name(cur, database)
    if not tbl:
        return [], "no_supplier_table"
    try:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """,
            (database, tbl),
        )
        cols = {str(r["COLUMN_NAME"]).lower() for r in cur.fetchall()}
    except pymysql.MySQLError:
        return [], "supplier_columns_failed"
    if "realname" not in cols or "id" not in cols:
        return [], "supplier_missing_realname_or_id"
    has_addr = "address" in cols and _safe_ident("address")
    addr_sel = "TRIM(`address`)" if has_addr else "''"
    uniq = sorted({int(x) for x in db_ids if x is not None})[:_MAX_QUOTED_SUPPLIERS]
    ph = ",".join(["%s"] * len(uniq))
    try:
        cur.execute(
            f"""
            SELECT `id` AS db_id, TRIM(`realname`) AS realname, {addr_sel} AS address
            FROM `{tbl}`
            WHERE `id` IN ({ph})
              AND `realname` IS NOT NULL AND TRIM(`realname`) != ''
            ORDER BY `id` ASC
            """,
            tuple(uniq),
        )
    except pymysql.MySQLError:
        return [], "supplier_by_id_query_failed"
    raw = [_jsonable_row(dict(r)) for r in cur.fetchall()]
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for r in raw:
        try:
            did = int(r["db_id"])
        except (TypeError, ValueError, KeyError):
            continue
        if did in seen:
            continue
        name = str(r.get("realname") or "").strip()
        if not name:
            continue
        addr = str(r.get("address") or "").strip()
        if not addr:
            addr = _DEFAULT_MARKET_ADDRESS
        seen.add(did)
        out.append({"name": name, "address": addr, "db_id": did})
    return out, None


class SupplierRatingBody(BaseModel):
    supplier_id: int
    rating: float = Field(..., ge=3.0, le=5.0)


@router.post("/smart-split-supplier-rating")
def smart_split_supplier_rating(body: SupplierRatingBody):
    """写入本地供货方评分（3～5 星），不写业务库。"""
    d = _load_ratings_dict()
    rid = str(body.supplier_id)
    d[rid] = round(float(body.rating), 2)
    _save_ratings_dict(d)
    return {"ok": True, "supplier_id": body.supplier_id, "rating": d[rid]}


class SmartSplitConfirmBody(BaseModel):
    order_id: int
    order_sn: str = Field(..., min_length=1, max_length=128)
    customer_name: str = Field(default="", max_length=512)
    customer_address: str = Field(default="", max_length=1024)
    strategy: str = Field(..., min_length=1, max_length=32)
    demo_note: str = Field(default="", max_length=4000)
    lines: list[dict[str, Any]] = Field(default_factory=list)
    grouped: Optional[list[dict[str, Any]]] = None

    @field_validator("strategy")
    @classmethod
    def _strategy_ok(cls, v: str) -> str:
        if v not in _STRATEGY_KEYS:
            raise ValueError("strategy 无效")
        return v


@router.post("/smart-split-confirm")
def smart_split_confirm(body: SmartSplitConfirmBody):
    """将已生成的分单方案写入 Agent 本地 JSONL（非业务库）。"""
    if not body.lines:
        raise HTTPException(status_code=400, detail="lines 不能为空")
    if len(body.lines) > _MAX_CONFIRM_LINES:
        raise HTTPException(
            status_code=400,
            detail=f"明细行过多（上限 {_MAX_CONFIRM_LINES}）",
        )

    path = _confirmations_path()
    records, _ = _load_and_compact_confirmations(path)
    if _confirmation_is_duplicate(records, body.order_id, body.order_sn):
        raise HTTPException(
            status_code=409,
            detail="该订单已确认分单，不可重复提交",
        )

    rec_id = str(uuid.uuid4())
    saved_at = datetime.now(timezone.utc).isoformat()
    record = {
        "id": rec_id,
        "saved_at": saved_at,
        "payload": body.model_dump(),
    }
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"本地写入失败：{e}") from e

    return {"ok": True, "id": rec_id, "saved_at": saved_at}


@router.get("/smart-split-confirmed")
def smart_split_confirmed(limit: int = 20):
    """当日（Asia/Shanghai）确认的本地留存，新在前；并返回全量已确认订单 id/sn 供前端禁用下拉。"""
    lim = max(1, min(100, int(limit)))
    path = _confirmations_path()
    records, dedupe_removed = _load_and_compact_confirmations(path)
    blocked_ids, blocked_sns = _blocked_orders_from_recs(records)

    today = _today_sh()
    parsed: list[dict[str, Any]] = []
    for rec in records:
        d = _saved_at_date_sh(str(rec.get("saved_at") or ""))
        if d == today:
            parsed.append(rec)

    def _sort_key(r: dict[str, Any]) -> str:
        return str(r.get("saved_at") or "")

    parsed.sort(key=_sort_key, reverse=True)
    return {
        "items": parsed[:lim],
        "blocked_order_ids": sorted(blocked_ids),
        "blocked_order_sns": sorted(blocked_sns),
        "dedupe_removed": dedupe_removed,
    }


_MAX_GEOCODE_ADDRESSES = 48

# 智能排线：未指派司机桶（orders.driver_id IS NULL）
_DELIVERY_ROUTE_UNASSIGNED_KEY = "__unassigned__"


def _delivery_route_driver_identifiers() -> tuple[str, ...]:
    """orders + driver 表字段名校验（仅标识符，防 SQL 注入）。"""
    otbl = S.ORDERS_TABLE
    pk = S.ORDERS_PK_COL
    osn = S.ORDERS_SN_COL
    mreal = S.ORDERS_MEMBER_NAME_COL
    mlogin = S.ORDERS_MEMBER_LOGIN_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    sdate = S.ORDERS_SEND_DATE_COL
    rmk = S.ORDERS_REMARK_COL
    did = S.ORDERS_DRIVER_ID_COL
    dtbl = S.DRIVER_TABLE
    dpk = S.DRIVER_PK_COL
    dplate = S.DRIVER_CAR_PLATE_COL
    dphone = S.DRIVER_PHONE_COL
    cols = (
        otbl,
        pk,
        osn,
        mreal,
        mlogin,
        maddr,
        sdate,
        rmk,
        did,
        dtbl,
        dpk,
        dplate,
        dphone,
    )
    if not all(_safe_ident(x) for x in cols):
        raise HTTPException(500, "业务库字段名异常，已拒绝拼接 SQL")
    return cols


def _parse_delivery_route_driver_param(driver: str) -> Optional[int]:
    """返回 None 表示未指派桶；否则为 driver_id。"""
    d = (driver or "").strip()
    if d == _DELIVERY_ROUTE_UNASSIGNED_KEY:
        return None
    if not d.isdigit():
        raise HTTPException(status_code=400, detail="参数 driver 无效")
    return int(d)


@router.get("/amap-js-config")
def amap_js_config():
    """下发高德 JSAPI Key 与安全码（与容器环境变量一致），供前端加载地图。"""
    key = (os.environ.get("AMAP_JSAPI_KEY") or "").strip()
    code = (os.environ.get("AMAP_SECURITY_JSCODE") or "").strip()
    if not key or not code:
        return {"enabled": False, "key": "", "securityJsCode": ""}
    return {"enabled": True, "key": key, "securityJsCode": code}


class SmartSplitGeocodeBody(BaseModel):
    addresses: list[str] = Field(default_factory=list)
    city: Optional[str] = None
    # 最后一项为客户时传 len(addresses)-1，仅对供货方失败项应用默认回退坐标
    customer_index: Optional[int] = Field(default=None, ge=0)
    fallback_disabled: bool = False
    # True：智能排线京津冀模式，按每条 address 单独选择 city（见 jjj_delivery_geocode.delivery_route_geocode_city_hint）
    delivery_route_jjj: bool = False

    @field_validator("addresses")
    @classmethod
    def _cap_addresses(cls, v: list[str]) -> list[str]:
        if len(v) > _MAX_GEOCODE_ADDRESSES:
            raise ValueError(f"地址过多（上限 {_MAX_GEOCODE_ADDRESSES}）")
        return v


@router.post("/smart-split-geocode")
def smart_split_geocode(body: SmartSplitGeocodeBody):
    """批量地理编码（复用 Web 服务 geocode + 缓存），顺序与请求 addresses 一致。"""
    addrs = body.addresses or []
    if not addrs:
        return {"results": []}
    if not amap_key():
        raise HTTPException(
            status_code=503,
            detail="未配置 AMAP_WEB_KEY（或 GAODE_MAP_KEY），无法进行地理编码",
        )
    city = (body.city or _SMART_SPLIT_AMAP_CITY).strip() or _SMART_SPLIT_AMAP_CITY

    uniq: list[str] = []
    seen: set[str] = set()
    for a in addrs:
        t = str(a or "").strip()
        if not t:
            continue
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    coord_by: dict[str, Optional[tuple[float, float]]] = {}
    if body.delivery_route_jjj:
        for t in uniq:
            coord_by[t] = geocode_single_for_delivery_route(t)
    else:
        for t in uniq:
            coord_by[t] = geocode_address(t, city=city)

    results: list[dict[str, Any]] = []
    for a in addrs:
        t = str(a or "").strip()
        if not t:
            results.append({"address": str(a or ""), "lng": None, "lat": None})
            continue
        c = coord_by.get(t)
        if c:
            lng, lat = c
            results.append({"address": t, "lng": lng, "lat": lat})
        else:
            results.append({"address": t, "lng": None, "lat": None})

    if not body.fallback_disabled:
        ci = body.customer_index
        if ci is not None and ci >= len(results):
            ci = None
        fb_coord: Optional[tuple[float, float]] = None
        for i, r in enumerate(results):
            if r.get("lng") is not None and r.get("lat") is not None:
                continue
            if ci is not None and i == ci:
                continue
            if fb_coord is None:
                fb_coord = geocode_address(_SMART_SPLIT_ADDRESS_GEO_FALLBACK, city=city)
            if fb_coord:
                r["lng"], r["lat"] = fb_coord
    return {"results": results}


@router.get("/delivery-route-today")
def delivery_route_today():
    """今日送货订单（send_date=上海当日），按 remark 升序；仅含有效 member_address。"""
    cfg = _cfg_or_503()
    otbl = S.ORDERS_TABLE
    pk = S.ORDERS_PK_COL
    osn = S.ORDERS_SN_COL
    mreal = S.ORDERS_MEMBER_NAME_COL
    mlogin = S.ORDERS_MEMBER_LOGIN_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    sdate = S.ORDERS_SEND_DATE_COL
    rmk = S.ORDERS_REMARK_COL
    if not all(
        _safe_ident(x)
        for x in (otbl, pk, osn, mreal, mlogin, maddr, sdate, rmk)
    ):
        raise HTTPException(500, "业务库字段名异常，已拒绝拼接 SQL")
    today = _today_sh()
    conn = _mysql_connect(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.`{pk}` AS id,
                       o.`{osn}` AS order_sn,
                       COALESCE(
                         NULLIF(TRIM(o.`{mreal}`), ''),
                         NULLIF(TRIM(o.`{mlogin}`), ''),
                         '—'
                       ) AS customer_name,
                       NULLIF(TRIM(o.`{maddr}`), '') AS member_address,
                       o.`{rmk}` AS remark
                FROM `{otbl}` o
                WHERE o.`{sdate}` IS NOT NULL
                  AND DATE(o.`{sdate}`) = %s
                  AND NULLIF(TRIM(o.`{maddr}`), '') IS NOT NULL
                ORDER BY (o.`{rmk}` IS NULL) ASC,
                         (NULLIF(TRIM(o.`{rmk}`), '') IS NULL) ASC,
                         o.`{rmk}` ASC,
                         o.`{pk}` ASC
                """,
                (today,),
            )
            raw = [_jsonable_row(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()

    orders: list[dict[str, Any]] = []
    for r in raw:
        rem = r.get("remark")
        if rem is not None and not isinstance(rem, str):
            rem = str(rem)
        ma = str(r.get("member_address") or "").strip()
        if not ma:
            continue
        orders.append(
            {
                "id": int(r["id"]),
                "order_sn": str(r.get("order_sn") or r["id"]),
                "customer_name": str(r.get("customer_name") or "—"),
                "member_address": ma,
                "remark": (rem or "").strip() if rem is not None else "",
            }
        )
    return {
        "depot_address": DELIVERY_ROUTE_DEPOT_ADDRESS,
        "business_date": str(today),
        "orders": orders,
    }


def _normalize_delivery_route_order_rows(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    orders: list[dict[str, Any]] = []
    for r in raw:
        rem = r.get("remark")
        if rem is not None and not isinstance(rem, str):
            rem = str(rem)
        ma = str(r.get("member_address") or "").strip()
        if not ma:
            continue
        orders.append(
            {
                "id": int(r["id"]),
                "order_sn": str(r.get("order_sn") or r["id"]),
                "customer_name": str(r.get("customer_name") or "—"),
                "member_address": ma,
                "remark": (rem or "").strip() if rem is not None else "",
            }
        )
    return orders


@router.get("/delivery-route-drivers")
def delivery_route_drivers():
    """今日送货按 driver_id 聚合；LEFT JOIN driver 取车牌、手机；含订单数与去重客户数（与列表客户名规则一致）。不返回订单明细。"""
    cfg = _cfg_or_503()
    (
        otbl,
        _pk,
        _osn,
        mreal,
        mlogin,
        maddr,
        sdate,
        _rmk,
        did,
        dtbl,
        dpk,
        dplate,
        dphone,
    ) = _delivery_route_driver_identifiers()
    today = _today_sh()
    conn = _mysql_connect(cfg)
    try:
        with conn.cursor() as cur:
            cust_expr = (
                f"COALESCE("
                f"NULLIF(TRIM(o.`{mreal}`), ''), "
                f"NULLIF(TRIM(o.`{mlogin}`), ''), "
                f"'—'"
                f")"
            )
            cur.execute(
                f"""
                SELECT o.`{did}` AS driver_id,
                       MAX(d.`{dplate}`) AS car_plate_no,
                       MAX(d.`{dphone}`) AS phone,
                       COUNT(*) AS order_count,
                       COUNT(DISTINCT {cust_expr}) AS customer_count
                FROM `{otbl}` o
                LEFT JOIN `{dtbl}` d ON o.`{did}` = d.`{dpk}`
                WHERE o.`{sdate}` IS NOT NULL
                  AND DATE(o.`{sdate}`) = %s
                  AND NULLIF(TRIM(o.`{maddr}`), '') IS NOT NULL
                GROUP BY o.`{did}`
                ORDER BY (o.`{did}` IS NULL) ASC,
                         customer_count DESC,
                         order_count DESC,
                         o.`{did}` ASC
                """,
                (today,),
            )
            rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()

    drivers: list[dict[str, Any]] = []
    for r in rows:
        rid = r.get("driver_id")
        if rid is not None:
            rid = int(rid)
        key = _DELIVERY_ROUTE_UNASSIGNED_KEY if rid is None else str(rid)
        drivers.append(
            {
                "driver_key": key,
                "driver_id": rid,
                "order_count": int(r["order_count"]),
                "customer_count": int(r.get("customer_count") or 0),
                "car_plate_no": str(r.get("car_plate_no") or "").strip(),
                "phone": str(r.get("phone") or "").strip(),
            }
        )
    return {
        "depot_address": DELIVERY_ROUTE_DEPOT_ADDRESS,
        "business_date": str(today),
        "unassigned_driver_key": _DELIVERY_ROUTE_UNASSIGNED_KEY,
        "drivers": drivers,
    }


@router.get("/delivery-route-orders")
def delivery_route_orders(
    driver: str = Query(
        ...,
        min_length=1,
        description=f"司机键：正整数 driver_id，或 {_DELIVERY_ROUTE_UNASSIGNED_KEY}表示未指派",
    ),
):
    """今日送货订单，限定某一司机（或未指派）；排序与 delivery-route-today 一致。"""
    cfg = _cfg_or_503()
    (
        otbl,
        pk,
        osn,
        mreal,
        mlogin,
        maddr,
        sdate,
        rmk,
        did,
        _dtbl,
        _dpk,
        _dplate,
        _dphone,
    ) = _delivery_route_driver_identifiers()
    driver_id = _parse_delivery_route_driver_param(driver)
    today = _today_sh()
    if driver_id is None:
        extra_where = f"AND o.`{did}` IS NULL"
        params: tuple[Any, ...] = (today,)
    else:
        extra_where = f"AND o.`{did}` = %s"
        params = (today, driver_id)

    conn = _mysql_connect(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT o.`{pk}` AS id,
                       o.`{osn}` AS order_sn,
                       COALESCE(
                         NULLIF(TRIM(o.`{mreal}`), ''),
                         NULLIF(TRIM(o.`{mlogin}`), ''),
                         '—'
                       ) AS customer_name,
                       NULLIF(TRIM(o.`{maddr}`), '') AS member_address,
                       o.`{rmk}` AS remark
                FROM `{otbl}` o
                WHERE o.`{sdate}` IS NOT NULL
                  AND DATE(o.`{sdate}`) = %s
                  AND NULLIF(TRIM(o.`{maddr}`), '') IS NOT NULL
                  {extra_where}
                ORDER BY (o.`{rmk}` IS NULL) ASC,
                         (NULLIF(TRIM(o.`{rmk}`), '') IS NULL) ASC,
                         o.`{rmk}` ASC,
                         o.`{pk}` ASC
                """,
                params,
            )
            raw = [_jsonable_row(dict(r)) for r in cur.fetchall()]
    finally:
        conn.close()

    orders = _normalize_delivery_route_order_rows(raw)
    return {
        "depot_address": DELIVERY_ROUTE_DEPOT_ADDRESS,
        "business_date": str(today),
        "driver_key": driver.strip(),
        "orders": orders,
    }


@router.get("/smart-split-seed")
def smart_split_seed():
    """
    抽样多明细行订单与供货方主数据，构造分单用报价/权重（业务库只读）。
    """
    cfg = _cfg_or_503()
    otbl = S.ORDERS_TABLE
    pk = S.ORDERS_PK_COL
    ot = S.ORDERS_TIME_COL
    osn = S.ORDERS_SN_COL
    mreal = S.ORDERS_MEMBER_NAME_COL
    mlogin = S.ORDERS_MEMBER_LOGIN_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL

    conn = _mysql_connect(cfg)
    warning: Optional[str] = None
    yday = datetime.now(_SH_TZ).date() - timedelta(days=1)
    y0 = int(datetime.combine(yday, time.min, tzinfo=_SH_TZ).timestamp())
    y1 = int(datetime.combine(yday, time(23, 59, 59), tzinfo=_SH_TZ).timestamp())
    yday_iso = yday.isoformat()
    try:
        spec = resolve_order_items_spec(conn, cfg.database, otbl)
        if not spec:
            return {
                "orders": [],
                "suppliers": [],
                "strategies": _strategies_list(),
                "demo_note": (
                    "未识别到订单明细表，无法抽样。可配置 INSIGHTS_ORDER_ITEMS_TABLE 等环境变量。"
                ),
                "warning": "no_order_items_spec",
                "strict_supplier_goods": False,
                "sample_orders_date": yday_iso,
            }

        if not all(
            _safe_ident(x)
            for x in (
                otbl,
                pk,
                ot,
                osn,
                mreal,
                mlogin,
                maddr,
                spec.items_table,
                spec.items_order_fk,
                spec.goods_name_col,
                spec.price_col,
            )
        ):
            raise HTTPException(500, "业务库字段名异常，已拒绝拼接 SQL")

        qty_expr = build_qty_sql("g", spec.qty_cols)
        gn = spec.goods_name_col
        gp = spec.price_col
        fk = spec.items_order_fk
        itbl = spec.items_table

        gid_key: Optional[str] = None
        gid_sql = "NULL AS goods_id"
        sg_pair_prices: dict[tuple[int, int], float] = {}
        sg_meta: Optional[tuple[str, str, str, str]] = None
        supplier_rows: list[dict[str, Any]] = []
        goods_ids_set: set[int] = set()

        with conn.cursor() as cur:
            items_cmap = _table_columns_exact(cur, cfg.database, itbl)
            gid_key = _pick_goods_id_col(set(items_cmap.keys()))
            if gid_key:
                gid_sql = f"g.`{items_cmap[gid_key]}` AS goods_id"

            cur.execute(
                f"""
                SELECT o.`{pk}` AS id, o.`{osn}` AS order_sn,
                       COALESCE(
                         NULLIF(TRIM(o.`{mreal}`), ''),
                         NULLIF(TRIM(o.`{mlogin}`), ''),
                         '—'
                       ) AS customer_name,
                       NULLIF(TRIM(o.`{maddr}`), '') AS member_address,
                       t.c AS line_count
                FROM `{otbl}` o
                INNER JOIN (
                    SELECT g.`{fk}` AS oid, COUNT(*) AS c
                    FROM `{itbl}` g
                    GROUP BY g.`{fk}`
                    HAVING c >= %s
                ) t ON o.`{pk}` = t.oid
                WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
                ORDER BY o.`{ot}` DESC
                LIMIT %s
                """,
                (_MIN_LINE_ITEMS, y0, y1, _MAX_SAMPLE_ORDERS),
            )
            order_rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]

            if not order_rows:
                note = (
                    f"东八区昨日（{yday_iso}）无符合条件的订单（须至少两条明细行）。"
                )
                if warning:
                    note = f"{note} 供货方主数据：{warning}。"
                wrn = "no_eligible_orders"
                if warning:
                    wrn = f"{wrn},{warning}"
                return {
                    "orders": [],
                    "suppliers": [],
                    "strategies": _strategies_list(),
                    "demo_note": note,
                    "warning": wrn,
                    "strict_supplier_goods": False,
                    "sample_orders_date": yday_iso,
                }

            ids = [int(r["id"]) for r in order_rows]
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(
                f"""
                SELECT g.`{fk}` AS order_id,
                       g.`{gn}` AS goods_name,
                       {gid_sql},
                       ({qty_expr}) AS qty,
                       COALESCE(g.`{gp}`, 0) AS unit_price,
                       ROUND(COALESCE(g.`{gp}`, 0) * ({qty_expr}), 4) AS line_amount
                FROM `{itbl}` g
                WHERE g.`{fk}` IN ({placeholders})
                ORDER BY g.`{fk}` ASC, g.`{gn}` ASC
                LIMIT %s
                """,
                (*ids, min(500, max(len(ids) * _GOODS_LIMIT_PER_ORDER, 50))),
            )
            line_rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]

            sg_meta = _resolve_supplier_goods_meta(cur, cfg.database)
            goods_ids_set = set()
            for r in line_rows:
                gv = r.get("goods_id")
                if gv is None:
                    continue
                try:
                    goods_ids_set.add(int(gv))
                except (TypeError, ValueError):
                    continue

            if sg_meta and goods_ids_set:
                sg_tbl, sgc, ggc, pgc = sg_meta
                ph_g = ",".join(["%s"] * len(goods_ids_set))
                cur.execute(
                    f"""
                    SELECT `{sgc}` AS sid, `{ggc}` AS gid, `{pgc}` AS pr
                    FROM `{sg_tbl}`
                    WHERE `{ggc}` IN ({ph_g})
                      AND `{pgc}` IS NOT NULL
                      AND CAST(`{pgc}` AS DECIMAL(18,4)) > 0
                    """,
                    tuple(sorted(goods_ids_set)),
                )
                for rr in cur.fetchall():
                    try:
                        sg_pair_prices[(int(rr["sid"]), int(rr["gid"]))] = float(rr["pr"])
                    except (TypeError, ValueError, KeyError):
                        continue

            quoted_supplier_ids = sorted({sid for (sid, _) in sg_pair_prices.keys()})
            supplier_rows = []
            if quoted_supplier_ids:
                capped = quoted_supplier_ids[:_MAX_QUOTED_SUPPLIERS]
                if len(quoted_supplier_ids) > _MAX_QUOTED_SUPPLIERS:
                    warning = _warn_merge(
                        warning, "supplier_goods_quoted_suppliers_truncated"
                    )
                sup_loaded, sup_err2 = _load_suppliers_by_db_ids(
                    cur, cfg.database, capped
                )
                supplier_rows = sup_loaded
                if sup_err2:
                    warning = _warn_merge(warning, sup_err2)

        sup_db_ids = [
            int(r["db_id"])
            for r in supplier_rows
            if r.get("db_id") is not None
        ]

        can_strict = bool(gid_key and sg_meta)
        strict_sg = bool(
            can_strict
            and bool(goods_ids_set)
            and len(sg_pair_prices) > 0
            and len(supplier_rows) > 0
        )
        if not gid_key:
            warning = _warn_merge(warning, "no_goods_id_on_items")
        if gid_key and not sg_meta:
            warning = _warn_merge(warning, "no_supplier_goods_table")
        if gid_key and sg_meta and not goods_ids_set:
            warning = _warn_merge(warning, "no_goods_id_values_on_lines")
        if (
            gid_key
            and sg_meta
            and goods_ids_set
            and len(sg_pair_prices) == 0
        ):
            warning = _warn_merge(warning, "supplier_goods_no_matching_quotes")
        if (
            gid_key
            and sg_meta
            and goods_ids_set
            and len(sg_pair_prices) > 0
            and not supplier_rows
        ):
            warning = _warn_merge(
                warning, "supplier_goods_sids_missing_in_supplier_table"
            )

        if not strict_sg:
            note = (
                "智能分单仅依据 supplier_goods 真实报价：抽样订单明细须含 goods_id，业务库须有 supplier_goods 表，"
                "且至少有一方供方对该批商品（goods_id）给出有效正数报价并在 supplier 表可查；不满足则不返回可分配数据。"
            )
            if warning:
                note = f"{note} 提示：{warning}。"
            wrn = "smart_split_requires_supplier_goods_quotes"
            if warning:
                wrn = f"{wrn},{warning}"
            return {
                "orders": [],
                "suppliers": [],
                "strategies": _strategies_list(),
                "demo_note": note,
                "warning": wrn,
                "strict_supplier_goods": True,
                "sample_orders_date": yday_iso,
            }

        by_order: dict[int, list[dict]] = {}
        for r in line_rows:
            oid = int(r["order_id"])
            by_order.setdefault(oid, [])
            name = str(r.get("goods_name") or "").strip() or "（未命名商品）"
            q = float(r.get("qty") or 0)
            up = float(r.get("unit_price") or 0)
            if up <= 0 and q > 0:
                la = float(r.get("line_amount") or 0)
                up = la / q if la > 0 else 0.01
            if up <= 0:
                up = 0.01
            gid_out: Optional[int] = None
            gv2 = r.get("goods_id")
            if gv2 is not None:
                try:
                    gid_out = int(gv2)
                except (TypeError, ValueError):
                    gid_out = None
            by_order[oid].append(
                {
                    "goods_name": name,
                    "goods_id": gid_out,
                    "qty": q,
                    "unit_hint": "斤",
                    "base_unit_price": round(up, 4),
                }
            )

        orders_out = []
        for orow in order_rows:
            oid = int(orow["id"])
            lines = by_order.get(oid, [])
            if len(lines) < _MIN_LINE_ITEMS:
                continue
            ma = orow.get("member_address")
            ma_str = str(ma).strip() if ma is not None else ""
            orders_out.append(
                {
                    "id": oid,
                    "order_sn": str(orow.get("order_sn") or oid),
                    "customer_name": str(orow.get("customer_name") or "—"),
                    "member_address": ma_str,
                    "lines": lines[:_GOODS_LIMIT_PER_ORDER],
                }
            )

        if not orders_out:
            note = "订单明细行数不足，无法加载。"
            if warning:
                note = f"{note} 供货方主数据：{warning}。"
            wrn = "no_eligible_orders_after_join"
            if warning:
                wrn = f"{wrn},{warning}"
            return {
                "orders": [],
                "suppliers": [],
                "strategies": _strategies_list(),
                "demo_note": note,
                "warning": wrn,
                "strict_supplier_goods": False,
                "sample_orders_date": yday_iso,
            }

        ratings_store = _load_ratings_dict()
        ratings_store = _ensure_ratings_for_ids(sup_db_ids, ratings_store)

        use_amap = bool(amap_key())
        suppliers_out = []
        supplier_geo: dict[str, Optional[tuple[float, float]]] = {}
        addr_geo_cache: dict[str, Optional[tuple[float, float]]] = {}

        def _geo_for_supplier_addr(addr: str) -> Optional[tuple[float, float]]:
            if not use_amap:
                return None
            key = _geocode_key_for_supplier_address(addr)
            if not key:
                return None
            if key not in addr_geo_cache:
                c = geocode_address(key, city=_SMART_SPLIT_AMAP_CITY)
                if c is not None and _coord_plausible_beijing_metro(c[0], c[1]):
                    addr_geo_cache[key] = c
                else:
                    addr_geo_cache[key] = None
            return addr_geo_cache[key]

        for i, row in enumerate(supplier_rows):
            name = str(row["name"])
            addr = str(row.get("address") or "")
            db_id = row.get("db_id")
            sid = f"s{db_id}" if db_id is not None else f"s{i}"
            quotes: dict[str, float] = {}
            if db_id is not None:
                sid_int = int(db_id)
                for gid in goods_ids_set:
                    pr = sg_pair_prices.get((sid_int, gid))
                    if pr is not None and pr > 0:
                        quotes[str(gid)] = round(float(pr), 4)
            if not quotes:
                continue
            rating_val = _rating_for_supplier_db(
                int(db_id) if db_id is not None else None,
                name,
                ratings_store,
            )
            geo = _geo_for_supplier_addr(addr) if addr else None
            supplier_geo[sid] = geo
            suppliers_out.append(
                {
                    "id": sid,
                    "db_id": int(db_id) if db_id is not None else None,
                    "name": name,
                    "address": addr,
                    "rating": rating_val,
                    "distance_km": round(_demo_distance_km_for_address(addr), 2),
                    "quote_by_goods": quotes,
                }
            )

        for o in orders_out:
            dkm: dict[str, float] = {}
            cust_g = None
            if use_amap:
                addr_q = str(o.get("member_address") or "").strip()
                cust_g = _geocode_customer_for_distance(
                    addr_q if addr_q else str(o.get("customer_name") or "")
                )
            for sup in suppliers_out:
                sid = str(sup["id"])
                addr = str(sup.get("address") or "")
                demo_km = _demo_distance_km_for_address(addr)
                sg = supplier_geo.get(sid)
                if use_amap and cust_g and sg:
                    lng1, lat1 = cust_g
                    lng2, lat2 = sg
                    dkm[sid] = round(haversine_km(lng1, lat1, lng2, lat2), 2)
                else:
                    dkm[sid] = demo_km
            o["supplier_distance_km"] = dkm

        demo_note = (
            f"抽样订单为东八区昨日（{yday_iso}）下单：至少两条明细、按下单时间从新到旧最多 {_MAX_SAMPLE_ORDERS} 单。"
            "订单、客户与商品行来自业务只读同步；参与分单的供货方仅包含在 supplier_goods 中对本批订单商品（goods_id）有有效正数报价且在 supplier 表可查的记录；"
            "无地址时默认京丰岳各庄市场地址以便距离测算。"
            "评分3～5 星存于本机 supplier_ratings.json，可通过 POST /api/governance/smart-split-supplier-rating 调整。"
            "每一明细行仅允许对该行商品有真实报价的供方参与分配（每行最多 3 家）。"
            "可选 AMAP_WEB_KEY：客户名与供货方地址均按「北京市」做地理编码与市域坐标校验（业务约定均在京），直线距离仅供参考。"
            "已确认列表仅展示当日（东八区）。"
        )
        if warning:
            demo_note = f"{demo_note} 提示：{warning}。"

        return {
            "orders": orders_out,
            "suppliers": suppliers_out,
            "strategies": _strategies_list(),
            "demo_note": demo_note,
            "warning": warning,
            "strict_supplier_goods": strict_sg,
            "sample_orders_date": yday_iso,
        }
    except pymysql.MySQLError as e:
        raise HTTPException(
            status_code=503,
            detail=f"业务库查询失败：{e}",
        ) from e
    finally:
        conn.close()
