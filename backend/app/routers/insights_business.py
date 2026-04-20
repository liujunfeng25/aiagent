# 业务库只读聚合（数据洞察 Tab），SQL 白名单 + 日期范围上限
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, time
from decimal import Decimal
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket
from zoneinfo import ZoneInfo

import pymysql

from app.business_insights import schema as S
from app.business_insights.order_items_resolver import (
    build_qty_sql,
    coalesce_item_goods_trim_sql,
    resolve_goods_catalog_spec,
    resolve_order_items_spec,
)
from app.services.amap_geocode import amap_key
from app.services.jjj_delivery_geocode import geocode_single_for_delivery_route
from app.services.business_mysql import BusinessMysqlConfig, resolve_business_mysql
from app.services.db_connector import get_connection

router = APIRouter()

_TZ = ZoneInfo("Asia/Shanghai")


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


def _day_start_ts(d: date) -> int:
    dt = datetime.combine(d, time.min, tzinfo=_TZ)
    return int(dt.timestamp())


def _day_end_ts(d: date) -> int:
    dt = datetime.combine(d, time(23, 59, 59), tzinfo=_TZ)
    return int(dt.timestamp())


def _parse_range(
    start_date: Optional[str],
    end_date: Optional[str],
    *,
    default_span_days: int = S.DEFAULT_RANGE_DAYS,
) -> tuple[date, date]:
    today = datetime.now(_TZ).date()
    if end_date:
        try:
            end = date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(400, "end_date 须为 YYYY-MM-DD") from None
    else:
        end = today
    if start_date:
        try:
            start = date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(400, "start_date 须为 YYYY-MM-DD") from None
    else:
        start = end - timedelta(days=default_span_days - 1)
    if start > end:
        start, end = end, start
    max_days = S.MAX_RANGE_DAYS
    if (end - start).days > max_days:
        start = end - timedelta(days=max_days)
    return start, end


def _jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat() if hasattr(v, "isoformat") else str(v)
        else:
            out[k] = v
    return out


@router.get("/health")
def health():
    cfg = resolve_business_mysql()
    if not cfg:
        return {
            "ok": False,
            "source": None,
            "message": "未配置：请设置 INSIGHTS_MYSQL_* 环境变量",
        }
    try:
        conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
        conn.ping()
        conn.close()
        return {"ok": True, "source": cfg.source, "database": cfg.database, "message": "连接正常"}
    except Exception as e:
        return {"ok": False, "source": cfg.source, "message": str(e)}


@router.get("/orders-daily")
def orders_daily(
    start_date: Optional[str] = Query(
        None,
        description="YYYY-MM-DD；未传时与 end 组成窗口，驾驶舱默认见 COCKPIT_DEFAULT_RANGE_DAYS",
    ),
    end_date: Optional[str] = Query(None),
    district_name: Optional[str] = Query(
        None, description="可选：仅统计收货地址匹配该区县的订单"
    ),
):
    cfg = _cfg_or_503()
    start, end = _parse_range(
        start_date, end_date, default_span_days=S.COCKPIT_DEFAULT_RANGE_DAYS
    )
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot, ta = S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    addr_fr, addr_params = _orders_addr_filter_fragment(maddr, None, district_name)
    sql = f"""
        SELECT DATE(FROM_UNIXTIME(`{ot}`)) AS day,
               COUNT(*) AS order_count,
               COALESCE(SUM(`{ta}`), 0) AS gmv
        FROM `{S.ORDERS_TABLE}`
        WHERE `{ot}` >= %s AND `{ot}` <= %s{addr_fr}
        GROUP BY DATE(FROM_UNIXTIME(`{ot}`))
        ORDER BY day
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1) + addr_params)
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（MySQL 未就绪或缺表 `{S.ORDERS_TABLE}` 等）：{e}",
            ) from e
    finally:
        conn.close()
    total_orders = sum(int(r.get("order_count") or 0) for r in rows)
    total_gmv = sum(float(r.get("gmv") or 0) for r in rows)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_range_days": S.MAX_RANGE_DAYS,
        "series": rows,
        "summary": {"order_count": total_orders, "gmv": total_gmv},
    }


@router.get("/orders-top-members")
def orders_top_members(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(S.TOP_MEMBERS_DEFAULT, ge=1, le=S.TOP_MEMBERS_MAX),
    district_name: Optional[str] = Query(
        None, description="可选：仅统计收货地址匹配该区县的订单"
    ),
):
    cfg = _cfg_or_503()
    start, end = _parse_range(
        start_date, end_date, default_span_days=S.COCKPIT_DEFAULT_RANGE_DAYS
    )
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot = S.ORDERS_TIME_COL
    mid, mname, ta = S.ORDERS_MEMBER_COL, S.ORDERS_MEMBER_NAME_COL, S.ORDERS_AMOUNT_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    addr_fr, addr_params = _orders_addr_filter_fragment(maddr, None, district_name)
    sql = f"""
        SELECT `{mid}` AS member_id,
               MAX(`{mname}`) AS member_name,
               COUNT(*) AS order_count,
               COALESCE(SUM(`{ta}`), 0) AS gmv
        FROM `{S.ORDERS_TABLE}`
        WHERE `{ot}` >= %s AND `{ot}` <= %s{addr_fr}
        GROUP BY `{mid}`
        ORDER BY gmv DESC
        LIMIT %s
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1) + addr_params + (limit,))
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（MySQL 未就绪或缺表 `{S.ORDERS_TABLE}` 等）：{e}",
            ) from e
    finally:
        conn.close()
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_range_days": S.MAX_RANGE_DAYS,
        "rows": rows,
    }


@router.get("/backorder-daily")
def backorder_daily(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    cfg = _cfg_or_503()
    start, end = _parse_range(start_date, end_date)
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    bt, ba = S.BACKORDER_TIME_COL, S.BACKORDER_AMOUNT_COL
    sql = f"""
        SELECT DATE(FROM_UNIXTIME(`{bt}`)) AS day,
               COUNT(*) AS backorder_count,
               COALESCE(SUM(`{ba}`), 0) AS amount_sum
        FROM `{S.BACKORDER_TABLE}`
        WHERE `{bt}` IS NOT NULL AND `{bt}` > 0 AND `{bt}` >= %s AND `{bt}` <= %s
        GROUP BY DATE(FROM_UNIXTIME(`{bt}`))
        ORDER BY day
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1))
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（MySQL 未就绪或缺表 `{S.BACKORDER_TABLE}` 等）：{e}",
            ) from e
    finally:
        conn.close()
    total_cnt = sum(int(r.get("backorder_count") or 0) for r in rows)
    total_amt = sum(float(r.get("amount_sum") or 0) for r in rows)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_range_days": S.MAX_RANGE_DAYS,
        "series": rows,
        "summary": {"backorder_count": total_cnt, "amount_sum": total_amt},
    }


@router.get("/xinfadi-summary-series")
def xinfadi_summary_series(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    cfg = _cfg_or_503()
    start, end = _parse_range(start_date, end_date)
    dc = S.XINFADI_DATE_COL
    tbl = S.XINFADI_SUMMARY_TABLE
    sql = f"""
        SELECT `{dc}` AS day, min_price, avg_price, max_price, quantity
        FROM `{tbl}`
        WHERE `{dc}` >= %s AND `{dc}` <= %s
        ORDER BY `{dc}`
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (start, end))
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（MySQL 未就绪或缺表 `{tbl}` 等）：{e}",
            ) from e
    finally:
        conn.close()
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_range_days": S.MAX_RANGE_DAYS,
        "series": rows,
        "note": "库内预聚合表 chart_xinfadi_price_summary，与爬虫明细口径可能不同",
    }


@router.get("/goods-top")
def goods_top(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(S.TOP_GOODS_DEFAULT, ge=1, le=S.TOP_GOODS_MAX),
    district_name: Optional[str] = Query(
        None, description="可选：仅统计收货地址匹配该区县的订单"
    ),
):
    """单品排名：按商品名称分组，SUM 数量与金额，取 TOP N。明细表通过 INFORMATION_SCHEMA 自动识别。"""
    cfg = _cfg_or_503()
    start, end = _parse_range(
        start_date, end_date, default_span_days=S.COCKPIT_DEFAULT_RANGE_DAYS
    )
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot = S.ORDERS_TIME_COL
    otbl = S.ORDERS_TABLE
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    addr_fr, addr_params = _orders_addr_filter_fragment(maddr, "o", district_name)
    conn = _mysql_connect(cfg)
    try:
        spec = resolve_order_items_spec(conn, cfg.database, otbl)
        if not spec:
            return {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "rows": [],
                "warning": "未识别到可用的订单明细表（需含订单外键、品名、数量、单价等字段）。"
                " 可设置环境变量 INSIGHTS_ORDER_ITEMS_TABLE 等，详见 data_catalog.md。",
            }
        qty_expr = build_qty_sql("g", spec.qty_cols)
        gn = spec.goods_name_col
        gp = spec.price_col
        join_fk = spec.items_order_fk
        opk = spec.orders_pk
        itbl = spec.items_table
        sql = f"""
            SELECT g.`{gn}` AS goods_name,
                   COALESCE(SUM({qty_expr}), 0) AS total_qty,
                   COALESCE(SUM(g.`{gp}` * ({qty_expr})), 0) AS total_amount
            FROM `{itbl}` g
            JOIN `{otbl}` o ON g.`{join_fk}` = o.`{opk}`
            WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s{addr_fr}
            GROUP BY g.`{gn}`
            ORDER BY total_amount DESC
            LIMIT %s
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1) + addr_params + (limit,))
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（明细表 `{itbl}` JOIN `{otbl}`）：{e}",
            ) from e
    finally:
        conn.close()
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "rows": rows,
        "resolved_items_table": itbl,
        "resolved_orders_pk": opk,
    }


@router.get("/region-distribution")
def region_distribution(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(S.TOP_REGIONS_DEFAULT, ge=1, le=S.TOP_REGIONS_MAX),
):
    """区域/客户分布：按客户名分组统计订单量与 GMV。"""
    cfg = _cfg_or_503()
    start, end = _parse_range(start_date, end_date)
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot = S.ORDERS_TIME_COL
    mname = S.ORDERS_MEMBER_NAME_COL
    ta = S.ORDERS_AMOUNT_COL
    otbl = S.ORDERS_TABLE
    sql = f"""
        SELECT `{mname}` AS region_name,
               COUNT(*) AS order_count,
               COALESCE(SUM(`{ta}`), 0) AS gmv
        FROM `{otbl}`
        WHERE `{ot}` >= %s AND `{ot}` <= %s
              AND `{mname}` IS NOT NULL AND `{mname}` != ''
        GROUP BY `{mname}`
        ORDER BY order_count DESC
        LIMIT %s
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1, limit))
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：{e}",
            ) from e
    finally:
        conn.close()
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "rows": rows,
    }


_COCKPIT_MAP_POINTS_MAX = 500
_MAX_MEMBER_ORDERS_IN_RANGE = 500


@router.get("/category-distribution")
def category_distribution(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(S.TOP_REGIONS_DEFAULT, ge=1, le=S.TOP_REGIONS_MAX),
):
    """类别分布：订单明细 JOIN 订单，按商品类别汇总明细行金额（与 goods-top 同源）。"""
    cfg = _cfg_or_503()
    start, end = _parse_range(
        start_date, end_date, default_span_days=S.COCKPIT_DEFAULT_RANGE_DAYS
    )
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot = S.ORDERS_TIME_COL
    otbl = S.ORDERS_TABLE
    conn = _mysql_connect(cfg)
    try:
        spec = resolve_order_items_spec(conn, cfg.database, otbl)
        if not spec:
            return {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "rows": [],
                "warning": (
                    "未识别到可用的订单明细表。可设置环境变量 INSIGHTS_ORDER_ITEMS_TABLE 等，详见 data_catalog.md。"
                ),
            }
        qty_expr = build_qty_sql("g", spec.qty_cols)
        gp = spec.price_col
        join_fk = spec.items_order_fk
        opk = spec.orders_pk
        itbl = spec.items_table
        if spec.category_col:
            cat_expr = f"NULLIF(TRIM(CAST(g.`{spec.category_col}` AS CHAR)), '')"
            group_name = f"COALESCE({cat_expr}, '未分类')"
        else:
            group_name = "'未分类'"
        sql = f"""
            SELECT {group_name} AS category_name,
                   COALESCE(SUM(g.`{gp}` * ({qty_expr})), 0) AS line_gmv,
                   COUNT(*) AS line_count,
                   COUNT(DISTINCT o.`{opk}`) AS order_count
            FROM `{itbl}` g
            JOIN `{otbl}` o ON g.`{join_fk}` = o.`{opk}`
            WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
            GROUP BY 1
            ORDER BY line_gmv DESC
            LIMIT %s
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1, limit))
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（类别分布 `{itbl}` JOIN `{otbl}`）：{e}",
            ) from e
        out: dict[str, Any] = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "rows": rows,
            "resolved_items_table": itbl,
            "resolved_category_col": spec.category_col,
        }
        if not spec.category_col:
            out["warning"] = (
                "明细表未识别到类别列，已全部归为「未分类」。可通过 INSIGHTS_ORDER_ITEMS_CATEGORY_COL 指定。"
            )
        return out
    finally:
        conn.close()


def _cockpit_map_address_key(addr: str) -> str:
    """稳定键：同一收货地址对应唯一地图落点（不随进程变化）。"""
    h = hashlib.md5(addr.strip().encode("utf-8")).hexdigest()[:14]
    return f"a:{h}"


# 驾驶舱地图：无高德 Web Key 时无法调用地理编码，订单光柱会全部为空。
# 对收货地址做「区县关键字 → GCJ-02 近似中心」兜底（与侧栏 _BJ_DISTRICT_LIKE_ORDER / 雄安三县白名单一致）。
_COCKPIT_MAP_BJ_DISTRICT_APPROX: dict[str, tuple[float, float]] = {
    "门头沟区": (116.105, 39.937),
    "石景山区": (116.223, 39.906),
    "房山区": (116.143, 39.749),
    "大兴区": (116.338, 39.728),
    "通州区": (116.656, 39.909),
    "顺义区": (116.654, 40.130),
    "昌平区": (116.231, 40.221),
    "延庆区": (115.974, 40.465),
    "密云区": (116.843, 40.377),
    "怀柔区": (116.632, 40.316),
    "平谷区": (117.112, 40.144),
    "朝阳区": (116.486, 39.948),
    "丰台区": (116.287, 39.858),
    "海淀区": (116.298, 39.959),
    "西城区": (116.372, 39.916),
    "东城区": (116.422, 39.934),
    "容城县": (115.874, 39.052),
    "雄县": (116.109, 38.990),
    "安新县": (115.927, 38.936),
}


def _cockpit_map_approx_coord_from_address(addr: str) -> Optional[tuple[float, float]]:
    s = (addr or "").strip()
    if not s:
        return None
    for name in sorted(_COCKPIT_MAP_BJ_DISTRICT_APPROX.keys(), key=len, reverse=True):
        if name in s:
            return _COCKPIT_MAP_BJ_DISTRICT_APPROX[name]
    return None


@router.get("/cockpit-customer-map-points")
def cockpit_customer_map_points(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=_COCKPIT_MAP_POINTS_MAX),
):
    """智能驾驶舱地图：按收货地址聚合订单数/GMV（同一地址仅一个落点）；地理编码与智能排线同源。"""
    cfg = _cfg_or_503()
    start, end = _parse_range(
        start_date, end_date, default_span_days=S.COCKPIT_DEFAULT_RANGE_DAYS
    )
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot = S.ORDERS_TIME_COL
    otbl = S.ORDERS_TABLE
    mid = S.ORDERS_MEMBER_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    mreal = S.ORDERS_MEMBER_NAME_COL
    mlogin = S.ORDERS_MEMBER_LOGIN_COL
    ta = S.ORDERS_AMOUNT_COL
    sql = f"""
        SELECT TRIM(o.`{maddr}`) AS address,
               COUNT(*) AS order_count,
               COALESCE(SUM(o.`{ta}`), 0) AS gmv,
               COUNT(DISTINCT o.`{mid}`) AS member_count,
               MAX(o.`{mid}`) AS member_id_sample,
               MAX(COALESCE(
                   NULLIF(TRIM(o.`{mreal}`), ''),
                   NULLIF(TRIM(o.`{mlogin}`), ''),
                   '—'
               )) AS customer_name
        FROM `{otbl}` o
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
          AND NULLIF(TRIM(o.`{maddr}`), '') IS NOT NULL
        GROUP BY TRIM(o.`{maddr}`)
        ORDER BY order_count DESC
        LIMIT %s
    """
    conn = _mysql_connect(cfg)
    rows_raw: list[dict[str, Any]] = []
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1, limit))
                rows_raw = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（驾驶舱地图 `{otbl}`）：{e}",
            ) from e
    finally:
        conn.close()

    uniq_addrs: list[str] = []
    seen_a: set[str] = set()
    for r in rows_raw:
        a = str(r.get("address") or "").strip()
        if a and a not in seen_a:
            seen_a.add(a)
            uniq_addrs.append(a)

    coord_by: dict[str, tuple[float, float]] = {}
    if amap_key():
        for a in uniq_addrs:
            c = geocode_single_for_delivery_route(a)
            if c:
                coord_by[a] = (float(c[0]), float(c[1]))

    points: list[dict[str, Any]] = []
    failed = 0
    approx_placed = 0
    for r in rows_raw:
        addr = str(r.get("address") or "").strip()
        member_count = int(r.get("member_count") or 0)
        mid_int: int | None = None
        if member_count == 1:
            mid_v = r.get("member_id_sample")
            try:
                mid_int = int(mid_v) if mid_v is not None else None
            except (TypeError, ValueError):
                mid_int = None
        if member_count > 1:
            display_name = f"同址{member_count}个客户"
        else:
            display_name = str(r.get("customer_name") or "—")
        c = coord_by.get(addr)
        source = "amap"
        if not c:
            ac = _cockpit_map_approx_coord_from_address(addr)
            if ac:
                c = ac
                source = "approx_district"
                approx_placed += 1
        if not c:
            failed += 1
            continue
        lng, lat = c
        row_out: dict[str, Any] = {
            "member_key": _cockpit_map_address_key(addr),
            "member_id": mid_int,
            "member_count": member_count,
            "customer_name": display_name,
            "address": addr,
            "order_count": int(r.get("order_count") or 0),
            "gmv": float(r.get("gmv") or 0),
            "lng": lng,
            "lat": lat,
        }
        if source == "approx_district":
            row_out["coord_source"] = "approx_district"
        points.append(row_out)

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "points": points,
        "failed_geocode_count": failed,
        "geocode_enabled": bool(amap_key()),
        "approx_district_points": approx_placed,
    }


# 智能驾驶舱右侧：收货地址中匹配区县关键字（与地图 Geo命名一致，用于 GMV 环比与汇总）
_BJ_DISTRICT_LIKE_ORDER: tuple[str, ...] = (
    "门头沟区",
    "石景山区",
    "房山区",
    "大兴区",
    "通州区",
    "顺义区",
    "昌平区",
    "延庆区",
    "密云区",
    "怀柔区",
    "平谷区",
    "朝阳区",
    "丰台区",
    "海淀区",
    "西城区",
    "东城区",
)


def _beijing_district_case_sql(addr_col: str) -> str:
    # PyMySQL mogrify 用 % 做占位符，SQL 里 LIKE 的 % 必须写成 %%，否则会 ValueError
    parts = [
        f"WHEN TRIM(o.`{addr_col}`) LIKE '%%{name}%%' THEN '{name}'"
        for name in _BJ_DISTRICT_LIKE_ORDER
    ]
    return "CASE " + " ".join(parts) + " ELSE NULL END"


# 与地图 GeoJSON 命名及白名单一致；雄安三县等可在此扩展
_DISTRICT_NAMES_ALLOWED: frozenset[str] = frozenset(
    _BJ_DISTRICT_LIKE_ORDER + ("容城县", "雄县", "安新县"),
)


def _normalize_district_name_param(district_name: Optional[str]) -> Optional[str]:
    if district_name is None:
        return None
    t = str(district_name).strip()
    if not t or t not in _DISTRICT_NAMES_ALLOWED:
        return None
    return t


def _orders_addr_filter_fragment(
    addr_col: str,
    table_alias: Optional[str],
    district_name: Optional[str],
) -> tuple[str, tuple[Any, ...]]:
    """按收货地址关键字过滤（与 CASE 推断一致）；非法区县名忽略。"""
    d = _normalize_district_name_param(district_name)
    if not d:
        return "", ()
    pref = f"{table_alias}." if table_alias else ""
    ref = f"{pref}`{addr_col}`"
    return (
        f" AND NULLIF(TRIM({ref}), '') IS NOT NULL AND TRIM({ref}) LIKE %s",
        (f"%{d}%",),
    )


def _prev_range(start: date, end: date) -> tuple[date, date]:
    span_days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span_days - 1)
    return prev_start, prev_end


@router.get("/cockpit-smart-side-insights")
def cockpit_smart_side_insights(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    district_name: Optional[str] = Query(
        None,
        description="可选：仅统计该区县（与 GeoJSON properties.name / 地址关键字一致）",
    ),
):
    """智能驾驶舱地图侧栏：重点区域（区县 GMV + 环比）· 客单价分布；区县由地址关键字推断。"""
    cfg = _cfg_or_503()
    start, end = _parse_range(
        start_date, end_date, default_span_days=S.COCKPIT_DEFAULT_RANGE_DAYS
    )
    prev_start, prev_end = _prev_range(start, end)
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    pt0, pt1 = _day_start_ts(prev_start), _day_end_ts(prev_end)
    ot = S.ORDERS_TIME_COL
    otbl = S.ORDERS_TABLE
    ta = S.ORDERS_AMOUNT_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    dcase = _beijing_district_case_sql(maddr)
    d_only = _normalize_district_name_param(district_name)
    dist_eq_sql = " AND t.district_name = %s" if d_only else ""
    addr_fr, addr_params = _orders_addr_filter_fragment(maddr, "o", district_name)

    sql_district = f"""
        SELECT t.district_name AS district_name,
               COUNT(*) AS order_count,
               COALESCE(SUM(t.amount), 0) AS gmv
        FROM (
            SELECT {dcase} AS district_name,
                   o.`{ta}` AS amount
            FROM `{otbl}` o
            WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
              AND NULLIF(TRIM(o.`{maddr}`), '') IS NOT NULL
        ) t
        WHERE t.district_name IS NOT NULL{dist_eq_sql}
        GROUP BY t.district_name
    """
    sql_ticket = f"""
        SELECT
            SUM(CASE WHEN o.`{ta}` < 500 THEN 1 ELSE 0 END) AS b_lt500,
            SUM(CASE WHEN o.`{ta}` >= 500 AND o.`{ta}` < 2000 THEN 1 ELSE 0 END) AS b_500_2k,
            SUM(CASE WHEN o.`{ta}` >= 2000 AND o.`{ta}` < 5000 THEN 1 ELSE 0 END) AS b_2k_5k,
            SUM(CASE WHEN o.`{ta}` >= 5000 THEN 1 ELSE 0 END) AS b_gt5k,
            COALESCE(AVG(o.`{ta}`), 0) AS avg_ticket,
            COALESCE(MAX(o.`{ta}`), 0) AS max_ticket,
            COUNT(*) AS order_n
        FROM `{otbl}` o
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s{addr_fr}
    """
    sql_points = f"""
        SELECT COUNT(DISTINCT TRIM(o.`{maddr}`)) AS c
        FROM `{otbl}` o
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
          AND NULLIF(TRIM(o.`{maddr}`), '') IS NOT NULL{addr_fr}
    """

    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                p_cur = (t0, t1) + ((d_only,) if d_only else ())
                cur.execute(sql_district, p_cur)
                cur_rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
                p_prev = (pt0, pt1) + ((d_only,) if d_only else ())
                cur.execute(sql_district, p_prev)
                prev_rows = {_jsonable_row(dict(r))["district_name"]: _jsonable_row(dict(r)) for r in cur.fetchall()}
                cur.execute(sql_ticket, (t0, t1) + addr_params)
                tk = _jsonable_row(dict(cur.fetchone() or {}))
                cur.execute(sql_points, (t0, t1) + addr_params)
                ap = int(dict(cur.fetchone() or {}).get("c") or 0)
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（驾驶舱 smart-side `{otbl}`）：{e}",
            ) from e
    finally:
        conn.close()

    cur_rows.sort(key=lambda r: float(r.get("gmv") or 0), reverse=True)
    key_districts: list[dict[str, Any]] = []
    for r in cur_rows[:9]:
        name = str(r.get("district_name") or "")
        gmv = float(r.get("gmv") or 0)
        oc = int(r.get("order_count") or 0)
        pr = prev_rows.get(name)
        prev_gmv = float(pr.get("gmv") or 0) if pr else 0.0
        if prev_gmv > 0:
            mom = round(100.0 * (gmv - prev_gmv) / prev_gmv, 1)
        elif gmv > 0:
            mom = None
        else:
            mom = 0.0
        key_districts.append(
            {
                "district_name": name,
                "gmv": gmv,
                "order_count": oc,
                "mom_pct": mom,
            }
        )

    def _i(x: Any) -> int:
        try:
            return int(x or 0)
        except (TypeError, ValueError):
            return 0

    ticket_buckets = [
        {"key": "lt500", "label": "<500", "count": _i(tk.get("b_lt500"))},
        {"key": "500_2k", "label": "500~2k", "count": _i(tk.get("b_500_2k"))},
        {"key": "2k_5k", "label": "2k~5k", "count": _i(tk.get("b_2k_5k"))},
        {"key": "gt5k", "label": ">5k", "count": _i(tk.get("b_gt5k"))},
    ]

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "prev_start_date": prev_start.isoformat(),
        "prev_end_date": prev_end.isoformat(),
        "key_districts": key_districts,
        "ticket_buckets": ticket_buckets,
        "ticket_avg": round(float(tk.get("avg_ticket") or 0), 2),
        "ticket_max": round(float(tk.get("max_ticket") or 0), 2),
        "district_cover_count": len(cur_rows),
        "active_points": ap,
    }


@router.get("/member-orders-in-range")
def member_orders_in_range(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    member_id: Optional[int] = Query(None, description="会员 id，优先"),
    address: Optional[str] = Query(None, max_length=768, description="收货地址，与地图聚合键一致"),
):
    """某会员（或某地址）在时间区间内的订单列表，供驾驶舱侧栏。"""
    cfg = _cfg_or_503()
    start, end = _parse_range(
        start_date, end_date, default_span_days=S.COCKPIT_DEFAULT_RANGE_DAYS
    )
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot = S.ORDERS_TIME_COL
    otbl = S.ORDERS_TABLE
    pk = S.ORDERS_PK_COL
    osn = S.ORDERS_SN_COL
    ta = S.ORDERS_AMOUNT_COL
    mid = S.ORDERS_MEMBER_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    mreal = S.ORDERS_MEMBER_NAME_COL
    mlogin = S.ORDERS_MEMBER_LOGIN_COL

    addr_trim = (address or "").strip()
    if member_id is not None and member_id > 0:
        if addr_trim:
            where_extra = f"o.`{mid}` = %s AND TRIM(o.`{maddr}`) = %s"
            extra_params = (member_id, addr_trim)
        else:
            where_extra = f"o.`{mid}` = %s"
            extra_params = (member_id,)
    elif addr_trim:
        where_extra = f"TRIM(o.`{maddr}`) = %s"
        extra_params = (addr_trim,)
    else:
        raise HTTPException(
            status_code=400,
            detail="须提供 member_id（>0）或 address",
        )

    sql = f"""
        SELECT o.`{pk}` AS id,
               o.`{osn}` AS order_sn,
               o.`{ot}` AS add_time,
               o.`{ta}` AS total_amount,
               COALESCE(
                   NULLIF(TRIM(o.`{mreal}`), ''),
                   NULLIF(TRIM(o.`{mlogin}`), ''),
                   '—'
               ) AS customer_name,
               NULLIF(TRIM(o.`{maddr}`), '') AS member_address
        FROM `{otbl}` o
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
          AND ({where_extra})
        ORDER BY o.`{ot}` DESC, o.`{pk}` DESC
        LIMIT %s
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (t0, t1, *extra_params, _MAX_MEMBER_ORDERS_IN_RANGE),
                )
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：`{otbl}` — {e}",
            ) from e
    finally:
        conn.close()

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "member_id": member_id,
        "address": addr_trim or None,
        "rows": rows,
    }


_MAX_TODAY_ORDERS_LIST = 2000


@router.get("/today-orders-list")
def today_orders_list(
    limit: int = Query(500, ge=1, le=_MAX_TODAY_ORDERS_LIST),
):
    """今日 0 点起至今的订单列表（全市），供天枢大屏「今日订单」弹窗。"""
    cfg = _cfg_or_503()
    day = datetime.now(_TZ).date()
    t0 = _day_start_ts(day)
    t1 = min(_day_end_ts(day), int(datetime.now(_TZ).timestamp()))
    ot = S.ORDERS_TIME_COL
    otbl = S.ORDERS_TABLE
    pk = S.ORDERS_PK_COL
    osn = S.ORDERS_SN_COL
    ta = S.ORDERS_AMOUNT_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    mreal = S.ORDERS_MEMBER_NAME_COL
    mlogin = S.ORDERS_MEMBER_LOGIN_COL
    lim = min(int(limit), _MAX_TODAY_ORDERS_LIST)
    sql = f"""
        SELECT o.`{pk}` AS id,
               o.`{osn}` AS order_sn,
               o.`{ot}` AS add_time,
               o.`{ta}` AS total_amount,
               COALESCE(
                   NULLIF(TRIM(o.`{mreal}`), ''),
                   NULLIF(TRIM(o.`{mlogin}`), ''),
                   '—'
               ) AS customer_name,
               NULLIF(TRIM(o.`{maddr}`), '') AS member_address
        FROM `{otbl}` o
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
        ORDER BY o.`{ot}` DESC, o.`{pk}` DESC
        LIMIT %s
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1, lim))
                rows = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：`{otbl}` — {e}",
            ) from e
    finally:
        conn.close()

    return {
        "day": day.isoformat(),
        "day_start_ts": t0,
        "day_end_ts": t1,
        "limit": lim,
        "rows": rows,
    }


@router.get("/meta/tables")
def meta_tables():
    """只读：INFORMATION_SCHEMA 列清单，供盘点可用字段（不返回连接信息）。"""
    cfg = _cfg_or_503()
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, ORDINAL_POSITION
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """,
                    (cfg.database,),
                )
                raw = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(status_code=503, detail=f"读取元数据失败：{e}") from e
    finally:
        conn.close()

    tables: dict[str, list[dict[str, Any]]] = {}
    for row in raw:
        t = str(row.get("TABLE_NAME") or "")
        if not t:
            continue
        tables.setdefault(t, []).append(
            {
                "column": row.get("COLUMN_NAME"),
                "data_type": row.get("DATA_TYPE"),
            }
        )
    return {
        "database": cfg.database,
        "source": cfg.source,
        "table_count": len(tables),
        "tables": [{"name": k, "columns": v} for k, v in sorted(tables.items())],
    }


@router.get("/today-intraday-gmv")
def today_intraday_gmv(
    date: Optional[str] = Query(
        None,
        description="YYYY-MM-DD，默认今日；历史日返回当日全日分钟桶，今日截止到当前时刻",
    ),
    district_name: Optional[str] = Query(
        None, description="可选：仅统计收货地址匹配该区县的订单"
    ),
):
    """指定日（东八区）按 1 分钟桶聚合成交额；未传 date 时为今日。前端可做 3 小时等粗粒度聚合对比。"""
    cfg = _cfg_or_503()
    now_ts = int(datetime.now(_TZ).timestamp())
    today_d = datetime.now(_TZ).date()
    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail="date 须为 YYYY-MM-DD",
            ) from e
        if day > today_d:
            raise HTTPException(status_code=400, detail="date 不能为未来日期")
    else:
        day = today_d
    t0 = _day_start_ts(day)
    t1_day_end = _day_end_ts(day)
    if day == today_d:
        t1 = min(t1_day_end, now_ts)
    else:
        t1 = t1_day_end
    ot, ta = S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    addr_fr, addr_params = _orders_addr_filter_fragment(maddr, None, district_name)
    t0_sql = int(t0)
    sql = f"""
        SELECT ({t0_sql} + FLOOR((`{ot}` - {t0_sql}) / 60) * 60) AS minute_start,
               COALESCE(SUM(`{ta}`), 0) AS bucket_gmv,
               COUNT(*) AS order_count
        FROM `{S.ORDERS_TABLE}`
        WHERE `{ot}` >= %s AND `{ot}` <= %s{addr_fr}
        GROUP BY minute_start
        ORDER BY minute_start
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1) + addr_params)
                raw = [dict(r) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：`{S.ORDERS_TABLE}` — {e}",
            ) from e
    finally:
        conn.close()

    buckets = [
        {
            "minute_start": int(r.get("minute_start") or 0),
            "bucket_gmv": float(r.get("bucket_gmv") or 0),
            "order_count": int(r.get("order_count") or 0),
        }
        for r in raw
    ]
    return {
        "date": day.isoformat(),
        "day_start_ts": t0,
        "now_ts": now_ts,
        "query_end_ts": t1,
        "buckets": buckets,
    }


_MAX_ORDERS_PER_MINUTE = 500


@router.get("/today-intraday-minute-orders")
def today_intraday_minute_orders(
    minute_start: int = Query(
        ...,
        description="分钟桶起始 UNIX 时间戳，与 today-intraday-gmv 的 minute_start 一致",
    ),
):
    """某分钟内订单明细（只读白名单字段），供运营台弹窗。"""
    cfg = _cfg_or_503()
    day = datetime.now(_TZ).date()
    t0 = _day_start_ts(day)
    t1_day_end = _day_end_ts(day)
    now_ts = int(datetime.now(_TZ).timestamp())
    t_cap = min(t1_day_end, now_ts)
    t0_sql = int(t0)
    aligned = t0_sql + ((int(minute_start) - t0_sql) // 60) * 60
    if aligned < t0 or aligned > t_cap:
        raise HTTPException(
            400,
            "minute_start 对应分钟桶不在今日可查范围内（或为未来时间）",
        )
    window_hi = aligned + 60
    pk, osn, ot, ta = S.ORDERS_PK_COL, S.ORDERS_SN_COL, S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL
    mem, mreal, mlogin = (
        S.ORDERS_MEMBER_COL,
        S.ORDERS_MEMBER_NAME_COL,
        S.ORDERS_MEMBER_LOGIN_COL,
    )
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM `{S.ORDERS_TABLE}`
                    WHERE `{ot}` >= %s AND `{ot}` < %s
                    """,
                    (aligned, window_hi),
                )
                cnt_row = dict(cur.fetchone() or {})
                total_count = int(cnt_row.get("c") or 0)
                cur.execute(
                    f"""
                    SELECT `{osn}` AS order_sn, `{pk}` AS id, `{ot}` AS add_time,
                           `{ta}` AS total_amount, `{mem}` AS member_id,
                           `{mreal}` AS member_realname, `{mlogin}` AS member_login
                    FROM `{S.ORDERS_TABLE}`
                    WHERE `{ot}` >= %s AND `{ot}` < %s
                    ORDER BY `{ot}` ASC, `{pk}` ASC
                    LIMIT %s
                    """,
                    (aligned, window_hi, _MAX_ORDERS_PER_MINUTE),
                )
                raw = [dict(r) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：`{S.ORDERS_TABLE}` — {e}",
            ) from e
    finally:
        conn.close()

    orders = [_jsonable_row(r) for r in raw]
    return {
        "minute_start": aligned,
        "minute_end_exclusive": window_hi,
        "total_count": total_count,
        "truncated": total_count > len(orders),
        "orders": orders,
    }


# 回填「全量」时的服务端硬上限（防误扫超大表）；日常几百单远小于此值
_MAX_BACKFILL_HARD_CAP = 50_000


@router.get("/today-orders-backfill")
def today_orders_backfill(
    before_ts: int = Query(
        ...,
        description="锚点 UNIX 秒：仅返回当日 strictly 早于此时间的订单（进入页面前）",
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=_MAX_BACKFILL_HARD_CAP,
        description=f"可选；不传则返回窗口内全部订单（至多 {_MAX_BACKFILL_HARD_CAP} 条）",
    ),
):
    """今日 0 点起至 before_ts（不含）的订单摘要，与 live_gmv WebSocket batch 字段一致，供指挥台回填列表。"""
    cfg = _cfg_or_503()
    day = datetime.now(_TZ).date()
    t0 = _day_start_ts(day)
    t1_day_end = _day_end_ts(day)
    now_ts = int(datetime.now(_TZ).timestamp())
    t_cap = min(t1_day_end, now_ts)
    b = int(before_ts)
    if b < t0 or b > t_cap:
        raise HTTPException(
            400,
            "before_ts 须落在今日可查范围内 [day_start, min(now, 当日末)]",
        )
    pk, ot, ta = S.ORDERS_PK_COL, S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL
    eff_limit = int(limit) if limit is not None else _MAX_BACKFILL_HARD_CAP
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT `{pk}` AS id, `{ot}` AS add_time, `{ta}` AS amount
                    FROM `{S.ORDERS_TABLE}`
                    WHERE `{ot}` >= %s AND `{ot}` < %s
                    ORDER BY `{ot}` DESC, `{pk}` DESC
                    LIMIT %s
                    """,
                    (t0, b, eff_limit),
                )
                raw = [dict(r) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：`{S.ORDERS_TABLE}` — {e}",
            ) from e
    finally:
        conn.close()

    orders = [_jsonable_row(r) for r in raw]
    return {
        "day_start_ts": t0,
        "before_ts": b,
        "limit_applied": eff_limit,
        "limit_requested": limit,
        "orders": orders,
    }


@router.get("/order-head")
def order_head(
    order_id: int = Query(
        ...,
        description="订单主表主键，与 WebSocket batch / 分时明细的 id 一致",
    ),
):
    """单笔订单表头（指挥台实时成交点击用），字段与 today-intraday-minute-orders 单行一致。"""
    cfg = _cfg_or_503()
    pk, osn, ot, ta = S.ORDERS_PK_COL, S.ORDERS_SN_COL, S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL
    mem, mreal, mlogin = (
        S.ORDERS_MEMBER_COL,
        S.ORDERS_MEMBER_NAME_COL,
        S.ORDERS_MEMBER_LOGIN_COL,
    )
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT `{osn}` AS order_sn, `{pk}` AS id, `{ot}` AS add_time,
                           `{ta}` AS total_amount, `{mem}` AS member_id,
                           `{mreal}` AS member_realname, `{mlogin}` AS member_login
                    FROM `{S.ORDERS_TABLE}`
                    WHERE `{pk}` = %s
                    LIMIT 1
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：`{S.ORDERS_TABLE}` — {e}",
            ) from e
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在或已无权限访问")
    return _jsonable_row(dict(row))


@router.get("/order-line-items")
def order_line_items(
    order_id: int = Query(
        ...,
        description="订单主表主键，与分时明细接口返回的 id 一致",
    ),
):
    """单笔订单的商品行明细（与 goods-top 同源解析明细表）。"""
    cfg = _cfg_or_503()
    otbl = S.ORDERS_TABLE
    conn = _mysql_connect(cfg)
    try:
        spec = resolve_order_items_spec(conn, cfg.database, otbl)
        if not spec:
            return {
                "order_id": order_id,
                "rows": [],
                "warning": (
                    "未识别到可用的订单明细表。可设置环境变量 INSIGHTS_ORDER_ITEMS_TABLE 等，详见 data_catalog.md。"
                ),
            }
        qty_expr = build_qty_sql("g", spec.qty_cols)
        gn = spec.goods_name_col
        gp = spec.price_col
        join_fk = spec.items_order_fk
        itbl = spec.items_table
        goods_cat = (
            resolve_goods_catalog_spec(conn, cfg.database, otbl, itbl)
            if spec.goods_id_col
            else None
        )
        join_sql = ""
        goods_alias = "p"
        if goods_cat and spec.goods_id_col:
            join_sql = (
                f" LEFT JOIN `{goods_cat.table}` `{goods_alias}` "
                f"ON `g`.`{spec.goods_id_col}` = `{goods_alias}`.`{goods_cat.pk_col}` "
            )
        spec_sql = coalesce_item_goods_trim_sql(
            "g",
            spec.item_spec_col,
            goods_alias if join_sql else None,
            goods_cat.spec_col if goods_cat else None,
        )
        unit_sql = coalesce_item_goods_trim_sql(
            "g",
            spec.item_unit_col,
            goods_alias if join_sql else None,
            goods_cat.unit_col if goods_cat else None,
        )
        sql = f"""
            SELECT g.`{gn}` AS goods_name,
                   ({qty_expr}) AS qty,
                   ROUND(COALESCE(g.`{gp}`, 0) * ({qty_expr}), 4) AS line_amount,
                   {spec_sql} AS spec,
                   {unit_sql} AS unit
            FROM `{itbl}` g
            {join_sql}
            WHERE g.`{join_fk}` = %s
            ORDER BY g.`{gn}` ASC
            LIMIT 500
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (order_id,))
                raw = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败（订单明细 `{itbl}`）：{e}",
            ) from e
    finally:
        conn.close()
    return {"order_id": order_id, "rows": raw}


@router.get("/kpi-summary")
def kpi_summary(
    scope: Literal["range", "today"] = Query(
        "range",
        description="range：未传 start/end 时默认近 COCKPIT_DEFAULT_RANGE_DAYS 天（上海时区「今天」为结束日）；today：仅当日",
    ),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    district_name: Optional[str] = Query(
        None, description="可选：仅统计收货地址匹配该区县的订单"
    ),
):
    cfg = _cfg_or_503()
    if scope == "today":
        day = datetime.now(_TZ).date()
        start, end = day, day
    else:
        start, end = _parse_range(
            start_date, end_date, default_span_days=S.COCKPIT_DEFAULT_RANGE_DAYS
        )
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot, ta = S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL
    mid = S.ORDERS_MEMBER_COL
    maddr = S.ORDERS_MEMBER_ADDRESS_COL
    addr_fr, addr_params = _orders_addr_filter_fragment(maddr, None, district_name)
    sql_orders = f"""
        SELECT COUNT(*) AS order_count,
               COALESCE(SUM(`{ta}`), 0) AS gmv
        FROM `{S.ORDERS_TABLE}`
        WHERE `{ot}` >= %s AND `{ot}` <= %s{addr_fr}
    """
    sql_distinct_buyers = f"""
        SELECT COUNT(DISTINCT `{mid}`) AS c
        FROM `{S.ORDERS_TABLE}`
        WHERE `{ot}` >= %s AND `{ot}` <= %s
              AND `{mid}` IS NOT NULL AND `{mid}` != 0{addr_fr}
    """
    # 全库首次下单时间落在本统计窗口内的会员数（今日即「今日首单会员」）
    sql_first_order_members = f"""
        SELECT COUNT(*) AS c FROM (
            SELECT `{mid}` AS m
            FROM `{S.ORDERS_TABLE}`
            WHERE `{mid}` IS NOT NULL AND `{mid}` != 0{addr_fr}
            GROUP BY `{mid}`
            HAVING MIN(`{ot}`) >= %s AND MIN(`{ot}`) <= %s
        ) t
    """
    conn = _mysql_connect(cfg)
    distinct_buyers = 0
    first_order_members = 0
    backorder_count = 0
    backorder_amount = 0.0
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql_orders, (t0, t1) + addr_params)
                row = dict(cur.fetchone() or {})
                cur.execute(sql_distinct_buyers, (t0, t1) + addr_params)
                distinct_buyers = int(dict(cur.fetchone() or {}).get("c") or 0)
                cur.execute(
                    sql_first_order_members, addr_params + (t0, t1),
                )
                first_order_members = int(dict(cur.fetchone() or {}).get("c") or 0)
                bt, ba = S.BACKORDER_TIME_COL, S.BACKORDER_AMOUNT_COL
                try:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) AS c, COALESCE(SUM(`{ba}`), 0) AS amt
                        FROM `{S.BACKORDER_TABLE}`
                        WHERE `{bt}` IS NOT NULL AND `{bt}` > 0
                              AND `{bt}` >= %s AND `{bt}` <= %s
                        """,
                        (t0, t1),
                    )
                    br = dict(cur.fetchone() or {})
                    backorder_count = int(br.get("c") or 0)
                    backorder_amount = float(br.get("amt") or 0)
                except pymysql.MySQLError:
                    backorder_count = 0
                    backorder_amount = 0.0
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：`{S.ORDERS_TABLE}` — {e}",
            ) from e
    finally:
        conn.close()

    order_count = int(row.get("order_count") or 0)
    gmv = float(row.get("gmv") or 0)
    avg_ticket = round(gmv / order_count, 2) if order_count else 0.0
    return_rate_by_amount_pct = (
        round(100.0 * backorder_amount / gmv, 2) if gmv > 0 else 0.0
    )
    return {
        "scope": scope,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "order_count": order_count,
        "gmv": gmv,
        "avg_ticket": avg_ticket,
        "distinct_buyers": distinct_buyers,
        "first_order_members": first_order_members,
        "backorder_count": backorder_count,
        "backorder_amount": backorder_amount,
        "return_rate_by_amount_pct": return_rate_by_amount_pct,
        "metrics_note": (
            "业务库无物流/签收时间字段，无法用真实「配送及时率」；"
            "大屏「今日下单会员」为当日 DISTINCT member_id。"
            "「退货金额占GMV」= 当日 backorder 表金额合计 / 当日 orders GMV。"
            "「今日首单会员」= 全库首笔订单时间落在当日的会员数。"
        ),
    }


@router.get("/orders-calendar-heatmap")
def orders_calendar_heatmap(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """按日聚合订单量与 GMV，供 ECharts calendar+heatmap（逻辑同 orders-daily）。"""
    cfg = _cfg_or_503()
    start, end = _parse_range(start_date, end_date)
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot, ta = S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL
    sql = f"""
        SELECT DATE(FROM_UNIXTIME(`{ot}`)) AS day,
               COUNT(*) AS order_count,
               COALESCE(SUM(`{ta}`), 0) AS gmv
        FROM `{S.ORDERS_TABLE}`
        WHERE `{ot}` >= %s AND `{ot}` <= %s
        GROUP BY DATE(FROM_UNIXTIME(`{ot}`))
        ORDER BY day
    """
    conn = _mysql_connect(cfg)
    try:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (t0, t1))
                series = [_jsonable_row(dict(r)) for r in cur.fetchall()]
        except pymysql.MySQLError as e:
            raise HTTPException(
                status_code=503,
                detail=f"业务库查询失败：`{S.ORDERS_TABLE}` — {e}",
            ) from e
    finally:
        conn.close()

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "max_range_days": S.MAX_RANGE_DAYS,
        "cells": [
            {
                "date": str(r.get("day") or "")[:10],
                "order_count": int(r.get("order_count") or 0),
                "gmv": float(r.get("gmv") or 0),
            }
            for r in series
        ],
    }


@router.get("/ops-alerts")
def ops_alerts(
    limit: int = Query(20, ge=1, le=50),
    district_name: Optional[str] = Query(
        None, description="可选：仅统计关联订单收货地址匹配该区县的记录"
    ),
):
    """运营指挥台：今日补单/退货预警汇总与最近明细（只读，白名单表）。"""
    cfg = _cfg_or_503()
    day = datetime.now(_TZ).date()
    t0, t1 = _day_start_ts(day), _day_end_ts(day)
    ot = S.ORDERS_TIME_COL
    o_pk = S.ORDERS_PK_COL
    o_sn = S.ORDERS_SN_COL
    o_amt = S.ORDERS_AMOUNT_COL
    o_mem = S.ORDERS_MEMBER_NAME_COL
    o_maddr = S.ORDERS_MEMBER_ADDRESS_COL
    o_dis = S.ORDERS_DISORDER_FK_COL
    addr_fr_o, addr_p_o = _orders_addr_filter_fragment(o_maddr, "o", district_name)
    b_tbl = S.BACKORDER_TABLE
    b_t = S.BACKORDER_TIME_COL
    b_amt = S.BACKORDER_AMOUNT_COL
    b_pk = S.BACKORDER_PK_COL
    b_sn = S.BACKORDER_SN_COL
    b_oid = S.BACKORDER_ORDER_FK_COL
    b_bst = S.BACKORDER_BACK_STATUS_COL
    b_st = S.BACKORDER_STATUS_COL
    pend_max = int(S.BACKORDER_PENDING_BACK_STATUS_MAX)
    d_tbl = S.DISORDER_TABLE
    d_pk = S.DISORDER_PK_COL
    d_sn = S.DISORDER_SN_COL
    d_st = S.DISORDER_STATUS_COL
    done = int(S.DISORDER_STATUS_DONE)

    if addr_p_o:
        sql_ret_sum = f"""
            SELECT COUNT(*) AS c, COALESCE(SUM(b.`{b_amt}`), 0) AS amt
            FROM `{b_tbl}` b
            INNER JOIN `{S.ORDERS_TABLE}` o ON o.`{o_pk}` = b.`{b_oid}`
            WHERE b.`{b_t}` >= %s AND b.`{b_t}` <= %s
              AND b.`{b_bst}` <= %s{addr_fr_o}
        """
    else:
        sql_ret_sum = f"""
            SELECT COUNT(*) AS c, COALESCE(SUM(`{b_amt}`), 0) AS amt
            FROM `{b_tbl}`
            WHERE `{b_t}` >= %s AND `{b_t}` <= %s
              AND `{b_bst}` <= %s
        """
    join_orders = "INNER JOIN" if addr_p_o else "LEFT JOIN"
    sql_ret_items = f"""
        SELECT b.`{b_pk}` AS id, b.`{b_sn}` AS backorder_sn, b.`{b_oid}` AS order_id,
               b.`{b_amt}` AS total_amount, b.`{b_bst}` AS back_status, b.`{b_st}` AS status,
               b.`{b_t}` AS add_time, b.`remark` AS remark,
               o.`{o_sn}` AS order_sn, o.`{o_mem}` AS member_realname
        FROM `{b_tbl}` b
        {join_orders} `{S.ORDERS_TABLE}` o ON o.`{o_pk}` = b.`{b_oid}`
        WHERE b.`{b_t}` >= %s AND b.`{b_t}` <= %s
          AND b.`{b_bst}` <= %s{addr_fr_o}
        ORDER BY b.`{b_t}` DESC
        LIMIT %s
    """
    sql_sup_cnt = f"""
        SELECT COUNT(*) AS c
        FROM `{S.ORDERS_TABLE}` o
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
          AND o.`{o_dis}` IS NOT NULL AND o.`{o_dis}` > 0{addr_fr_o}
    """
    sql_sup_pend = f"""
        SELECT COUNT(*) AS c
        FROM `{S.ORDERS_TABLE}` o
        INNER JOIN `{d_tbl}` d ON d.`{d_pk}` = o.`{o_dis}`
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
          AND o.`{o_dis}` > 0
          AND d.`{d_st}` != %s{addr_fr_o}
    """
    sql_sup_items = f"""
        SELECT o.`{o_pk}` AS id, o.`{o_sn}` AS order_sn, o.`{o_amt}` AS total_amount,
               o.`{ot}` AS add_time, o.`{o_dis}` AS disorder_id, o.`{o_mem}` AS member_realname,
               d.`{d_sn}` AS disorder_sn, d.`{d_st}` AS disorder_status
        FROM `{S.ORDERS_TABLE}` o
        INNER JOIN `{d_tbl}` d ON d.`{d_pk}` = o.`{o_dis}`
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s
          AND o.`{o_dis}` > 0{addr_fr_o}
        ORDER BY o.`{ot}` DESC
        LIMIT %s
    """
    # 今日订单三色占比（天枢饼图）：与顶部「今日下单数」一致——仅按下单时间 add_time 落在当日。
    # 分类（互斥）：backorder 出现过该订单 → 退单；否则有补单号 disorder_id>0 → 补单；否则正常。
    sql_today_mix = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN b.order_id IS NOT NULL THEN 1 ELSE 0 END) AS n_return,
            SUM(
                CASE
                    WHEN b.order_id IS NULL
                     AND o.`{o_dis}` IS NOT NULL AND o.`{o_dis}` > 0
                    THEN 1 ELSE 0
                END
            ) AS n_supplement,
            SUM(
                CASE
                    WHEN b.order_id IS NULL
                     AND (o.`{o_dis}` IS NULL OR o.`{o_dis}` = 0)
                    THEN 1 ELSE 0
                END
            ) AS n_normal
        FROM `{S.ORDERS_TABLE}` o
        LEFT JOIN (
            SELECT DISTINCT `{b_oid}` AS order_id FROM `{b_tbl}`
        ) b ON b.order_id = o.`{o_pk}`
        WHERE o.`{ot}` >= %s AND o.`{ot}` <= %s{addr_fr_o}
    """
    _mix_note = (
        "今日范围：仅按下单时间 add_time 当日；未传收货区县时与顶部「今日下单数」同为全市口径。"
        "三色（互斥、依次判定）：订单曾在 backorder 出现 → 退单；否则有补单号 disorder_id>0 → 补单；否则正常。"
    )

    conn = _mysql_connect(cfg)
    out: dict[str, Any] = {
        "date": day.isoformat(),
        "threshold_note": (
            f"退货待处理：{b_tbl}.{b_bst}<={pend_max}；"
            f"补单：{S.ORDERS_TABLE}.{o_dis}>0 且关联 {d_tbl}；"
            f"分拣未结案：{d_tbl}.{d_st}!={done}；"
            f"饼图：{_mix_note}"
        ),
        "return_pending": {"count": 0, "amount": 0.0},
        "return_items": [],
        "supplement_today": {"linked_count": 0, "pending_disorder_count": 0},
        "supplement_items": [],
        "today_order_mix": {
            "total": 0,
            "n_return": 0,
            "n_supplement": 0,
            "n_normal": 0,
            "note": _mix_note,
        },
    }
    try:
        with conn.cursor() as cur:
            cur.execute(sql_today_mix, (t0, t1) + addr_p_o)
            mx = dict(cur.fetchone() or {})
            out["today_order_mix"] = {
                "total": int(mx.get("total") or 0),
                "n_return": int(mx.get("n_return") or 0),
                "n_supplement": int(mx.get("n_supplement") or 0),
                "n_normal": int(mx.get("n_normal") or 0),
                "note": _mix_note,
            }
            cur.execute(sql_ret_sum, (t0, t1, pend_max) + addr_p_o)
            rs = dict(cur.fetchone() or {})
            out["return_pending"] = {
                "count": int(rs.get("c") or 0),
                "amount": float(rs.get("amt") or 0),
            }
            cur.execute(sql_ret_items, (t0, t1, pend_max) + addr_p_o + (limit,))
            out["return_items"] = [_jsonable_row(dict(r)) for r in cur.fetchall()]

            cur.execute(sql_sup_cnt, (t0, t1) + addr_p_o)
            out["supplement_today"]["linked_count"] = int(
                dict(cur.fetchone() or {}).get("c") or 0,
            )
            cur.execute(sql_sup_pend, (t0, t1, done) + addr_p_o)
            out["supplement_today"]["pending_disorder_count"] = int(
                dict(cur.fetchone() or {}).get("c") or 0,
            )
            cur.execute(sql_sup_items, (t0, t1) + addr_p_o + (limit,))
            out["supplement_items"] = [_jsonable_row(dict(r)) for r in cur.fetchall()]
    except pymysql.MySQLError as e:
        raise HTTPException(
            status_code=503,
            detail=f"业务库查询失败（ops-alerts）：{e}",
        ) from e
    finally:
        conn.close()
    return out


@router.websocket("/ws/live-gmv")
async def ws_live_gmv(websocket: WebSocket):
    """今日 GMV 推送：snapshot / batch / refresh_hint（服务端轮询 orders 增量，零 DDL）。"""
    from app.services.live_gmv_poller import hub

    await hub.handle(websocket)
