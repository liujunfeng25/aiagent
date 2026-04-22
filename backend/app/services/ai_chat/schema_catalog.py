"""数据库结构与接口样例缓存。

用途：
1. 用户在开 VPN 时（能连真实业务库），可主动抓取一次「表结构 + 示例接口响应」，
   落盘到 backend/data/ai_chat_catalog.json。
2. 关掉 VPN 后，若业务接口连不上，tools.dispatch_tool_call 会从这里取样例兜底，
   保证 AI 助手仍可以演示完整流程。

接口：
- POST /api/chat/catalog/refresh  → 触发一次刷新（需连得上业务库）
- GET  /api/chat/catalog           → 查看当前缓存摘要
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

from app.services.ai_chat.business_date import business_today

logger = logging.getLogger(__name__)

_CATALOG_PATH = Path(
    os.environ.get(
        "ASSISTANT_CATALOG_PATH",
        str(Path(__file__).resolve().parents[3] / "data" / "ai_chat_catalog.json"),
    )
)

# 要抓哪些示例接口（path, params）
_SAMPLE_PROBES: list[tuple[str, dict[str, Any]]] = [
    ("/kpi-summary", {"scope": "today"}),
    ("/kpi-summary", {"scope": "range"}),
    ("/orders-daily", {}),
    ("/orders-top-members", {"limit": 10}),
    ("/goods-top", {"limit": 10}),
    ("/cockpit-smart-side-insights", {}),
    ("/today-intraday-gmv", {}),
]


def _probe_key(path: str, params: Optional[dict[str, Any]] = None) -> str:
    """归一化的缓存 key：只拿 path 主体，忽略日期类参数。"""
    return path.strip()


_cache_loaded: bool = False
_catalog: dict[str, Any] = {"tables": {}, "api_samples": {}}


def _load() -> dict[str, Any]:
    global _cache_loaded, _catalog
    if _cache_loaded:
        return _catalog
    _cache_loaded = True
    try:
        if _CATALOG_PATH.is_file():
            with _CATALOG_PATH.open("r", encoding="utf-8") as f:
                _catalog = json.load(f)
    except Exception as e:
        logger.warning("读取 ai_chat_catalog.json 失败：%s", e)
        _catalog = {"tables": {}, "api_samples": {}}
    return _catalog


def get_cached_business_api_sample(path: str) -> Optional[dict[str, Any]]:
    """离线样例：给 tools.dispatch_tool_call 用的兜底。"""
    data = _load()
    return (data.get("api_samples") or {}).get(_probe_key(path))


def get_catalog_summary() -> dict[str, Any]:
    data = _load()
    return {
        "path": str(_CATALOG_PATH),
        "updated_at": data.get("updated_at"),
        "tables_count": len(data.get("tables") or {}),
        "api_sample_count": len(data.get("api_samples") or {}),
        "has_content": bool(data.get("api_samples") or data.get("tables")),
    }


def get_catalog() -> dict[str, Any]:
    return _load()


async def refresh_catalog(*, internal_api_base: str, include_tables: bool = True) -> dict[str, Any]:
    """抓一次「接口样例 + 表结构」写盘。需要当前能连真实业务库。

    为了避免参数依赖，时间类采用今日 + 近 7 天。
    表结构使用既有 /meta/tables 接口与 SHOW COLUMNS（通过 PyMySQL，避免再依赖其它）。
    """
    import httpx
    from datetime import datetime

    base = internal_api_base.rstrip("/")
    td = business_today()
    today = td.isoformat()
    week_ago = (td - timedelta(days=6)).isoformat()
    samples: dict[str, Any] = {}
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=20.0) as c:
        for path, params in _SAMPLE_PROBES:
            try:
                q = dict(params)
                # 为 range 类补今日 7 日窗
                if path in ("/orders-daily", "/orders-top-members", "/goods-top", "/cockpit-smart-side-insights"):
                    q.setdefault("start_date", week_ago)
                    q.setdefault("end_date", today)
                r = await c.get(f"{base}{path}", params=q)
                r.raise_for_status()
                samples[_probe_key(path)] = r.json()
            except Exception as e:
                errors.append(f"{path}: {e}")

    tables: dict[str, Any] = {}
    if include_tables:
        try:
            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.get(f"{base}/meta/tables")
                if r.status_code == 200:
                    tables = r.json()
        except Exception as e:
            errors.append(f"/meta/tables: {e}")

        # 对几张关键表额外抓 SHOW COLUMNS
        try:
            from app.services.business_mysql import resolve_business_mysql
            from app.services.db_connector import get_connection
            cfg = resolve_business_mysql()
            if cfg is not None:
                import pymysql
                conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
                try:
                    col_map: dict[str, list[dict[str, Any]]] = {}
                    for tname in ("orders", "backorder", "disorder", "driver"):
                        try:
                            with conn.cursor() as cur:
                                cur.execute(f"SHOW COLUMNS FROM `{tname}`")
                                col_map[tname] = [dict(r) for r in cur.fetchall()]
                        except pymysql.MySQLError as e:
                            errors.append(f"SHOW COLUMNS {tname}: {e}")
                    tables["columns_by_table"] = col_map
                finally:
                    conn.close()
        except Exception as e:
            errors.append(f"show_columns: {e}")

    data = {
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "tables": tables,
        "api_samples": samples,
        "errors": errors,
    }
    try:
        _CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CATALOG_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        errors.append(f"write_catalog: {e}")

    global _catalog, _cache_loaded
    _catalog = data
    _cache_loaded = True
    return {
        "ok": not errors,
        "path": str(_CATALOG_PATH),
        "samples": list(samples.keys()),
        "errors": errors,
    }
