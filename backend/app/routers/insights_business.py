# 业务库只读聚合（数据洞察 Tab），SQL 白名单 + 日期范围上限
from __future__ import annotations

from datetime import date, datetime, timedelta, time
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from zoneinfo import ZoneInfo

import pymysql

from app.business_insights import schema as S
from app.services.business_mysql import BusinessMysqlConfig, resolve_business_mysql
from app.services.db_connector import get_connection

router = APIRouter()

_TZ = ZoneInfo("Asia/Shanghai")


def _cfg_or_503() -> BusinessMysqlConfig:
    cfg = resolve_business_mysql()
    if not cfg:
        raise HTTPException(
            status_code=503,
            detail="未配置业务库连接：请在环境变量中设置 INSIGHTS_MYSQL_HOST（及 PORT/USER/PASSWORD/DATABASE），"
            "或在「数据源」中添加一条 MySQL 数据源。",
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
        start = end - timedelta(days=S.DEFAULT_RANGE_DAYS - 1)
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
            "message": "未配置：请设置 INSIGHTS_MYSQL_* 或添加 MySQL 数据源",
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
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD，默认与 end 组成近30天"),
    end_date: Optional[str] = Query(None),
):
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
):
    cfg = _cfg_or_503()
    start, end = _parse_range(start_date, end_date)
    t0, t1 = _day_start_ts(start), _day_end_ts(end)
    ot = S.ORDERS_TIME_COL
    mid, mname, ta = S.ORDERS_MEMBER_COL, S.ORDERS_MEMBER_NAME_COL, S.ORDERS_AMOUNT_COL
    sql = f"""
        SELECT `{mid}` AS member_id,
               MAX(`{mname}`) AS member_name,
               COUNT(*) AS order_count,
               COALESCE(SUM(`{ta}`), 0) AS gmv
        FROM `{S.ORDERS_TABLE}`
        WHERE `{ot}` >= %s AND `{ot}` <= %s
        GROUP BY `{mid}`
        ORDER BY gmv DESC
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
