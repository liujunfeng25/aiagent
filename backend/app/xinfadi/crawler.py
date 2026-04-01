# -*- coding: utf-8 -*-
"""
新发地价格爬虫：纯 HTTP 拉取与解析，无进程内状态。
进度由调用方通过 progress_callback 上报；环境变量 XINFADI_PRICE_API 可覆盖接口地址。
礼貌/快速：进程内可切换（报价页按钮）；启动时默认读环境变量 XINFADI_POLITE_CRAWL。
开：翻页间隔 0.5～1.2s、失败重试间隔 2s；关：无页间休眠、重试 0.5s。
"""

import json
import os
import random
import time
from urllib.parse import urlparse

import requests
from pathlib import Path

from config import PROJECT_ROOT

_DEFAULT_API = "http://www.xinfadi.com.cn/getPriceData.html"

# region agent log
def _debug_log_path() -> Path:
    p = PROJECT_ROOT.parent / ".cursor" / "debug-32f924.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _agent_log(message: str, data: dict, hypothesis_id: str, location: str = "") -> None:
    try:
        p = _debug_log_path()
        line = {
            "sessionId": "32f924",
            "location": location or "crawler.py:_agent_log",
            "message": message,
            "data": data,
            "hypothesisId": hypothesis_id,
            "timestamp": int(time.time() * 1000),
        }
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass


# endregion
BASE_URL = (os.environ.get("XINFADI_PRICE_API") or "").strip() or _DEFAULT_API
PER_PAGE = 200
MAX_RETRIES = 2
# (连接, 读取) 秒；读取过长会长时间卡在某一百分比
REQUEST_TIMEOUT = (10, 25)


def _env_polite_crawl() -> bool:
    v = (os.environ.get("XINFADI_POLITE_CRAWL") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


_polite_runtime: bool = _env_polite_crawl()


def polite_crawl_enabled() -> bool:
    return _polite_runtime


def set_polite_crawl(enabled: bool) -> None:
    global _polite_runtime
    _polite_runtime = bool(enabled)


def _page_delay_bounds() -> tuple[float, float]:
    if polite_crawl_enabled():
        return (0.5, 1.2)
    return (0.0, 0.0)


def _inter_page_delay() -> None:
    mn, mx = _page_delay_bounds()
    if mx <= 0:
        return
    time.sleep(random.uniform(mn, mx))


def _retry_delay_sec() -> float:
    return 2.0 if polite_crawl_enabled() else 0.5


ALLOWED_CAT_IDS = {1186, 1187, 1188, 1189, 1190, 1203, 1204}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

FIELDNAMES = ["一级分类", "二级分类", "品名", "最低价", "平均价", "最高价", "规格", "产地", "单位", "发布日期"]


def _canon_yyyy_mm_dd(s) -> str:
    """统一为 YYYY-MM-DD，避免 2026-3-8 与 2026-03-08 比较失败。"""
    if s is None or s == "":
        return ""
    t = str(s).strip().replace("/", "-").split()[0]
    parts = t.split("-")
    if len(parts) != 3:
        return t[:10]
    try:
        y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{y:04d}-{mo:02d}-{d:02d}"
    except ValueError:
        return t[:10]


def filter_by_pub_date(rows, ymd_slash_or_dash: str):
    """只保留发布日期与查询日一致的行；ymd 可为 YYYY-MM-DD 或 YYYY/MM/DD。"""
    want = _canon_yyyy_mm_dd(ymd_slash_or_dash)
    if not want:
        return []
    return [r for r in rows if _canon_yyyy_mm_dd(r.get("发布日期")) == want]


def _as_int(val, default=0) -> int:
    try:
        if val is None or val == "":
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def get_headers():
    parsed = urlparse(BASE_URL)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else "http://www.xinfadi.com.cn"
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": origin,
        "Referer": f"{origin}/priceDetail.html",
    }


def fetch_page(session, date_str, current):
    """请求一页数据，date_str 格式 YYYY/MM/DD。"""
    data = {
        "current": current,
        "limit": PER_PAGE,
        "pubDateStartTime": date_str,
        "pubDateEndTime": date_str,
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = session.post(BASE_URL, data=data, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(_retry_delay_sec())
            else:
                raise e


def row_to_record(item):
    """将接口单条转为与页面表格一致的字段。"""
    return {
        "一级分类": item.get("prodCat") or "",
        "二级分类": item.get("prodPcat") or "",
        "品名": item.get("prodName") or "",
        "最低价": item.get("lowPrice") or "",
        "平均价": item.get("avgPrice") or "",
        "最高价": item.get("highPrice") or "",
        "规格": item.get("specInfo") or "",
        "产地": item.get("place") or "",
        "单位": item.get("unitInfo") or "",
        "发布日期": (item.get("pubDate") or "").split()[0] if item.get("pubDate") else "",
    }


def crawl_for_date(date_str, progress_callback=None):
    """
    爬取指定日期的 7 个一级分类价格明细。
    date_str: YYYY/MM/DD
    progress_callback: (current_page, total_count, pct) -> None，可选。
    返回去重后的 list[dict]。
    """
    session = requests.Session()
    session.trust_env = False
    session.headers.update(get_headers())
    all_rows = []
    current = 1
    total_count = None
    max_pages = 80

    while current <= max_pages:
        # 第一页请求完成前旧版从不回调，界面会长时间停在 0%
        if progress_callback:
            if total_count:
                pct = min(99, round(((current - 1) * PER_PAGE + 1) / max(total_count, 1) * 100))
            else:
                pct = min(95, 5 + (current - 1) * 8)
            progress_callback(current, total_count or 0, pct)

        resp = fetch_page(session, date_str, current)
        count = _as_int(resp.get("count"), 0)
        if total_count is None:
            total_count = count
        if progress_callback and total_count:
            pct = min(100, round(current * PER_PAGE / total_count * 100))
            progress_callback(current, total_count, pct)

        lst = resp.get("list") or []
        if not lst:
            break
        for item in lst:
            raw_id = item.get("prodCatid")
            if raw_id is None or raw_id == "":
                continue
            try:
                cat_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if cat_id in ALLOWED_CAT_IDS:
                all_rows.append(row_to_record(item))
        if current * PER_PAGE >= count:
            break
        current += 1
        _inter_page_delay()

    seen = set()
    unique = []
    for r in all_rows:
        key = (r["品名"], r["一级分类"], r["产地"], r["发布日期"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    n_before = len(unique)
    filtered = filter_by_pub_date(unique, date_str)
    _agent_log(
        "crawl_for_date_filter",
        {
            "api_date": date_str,
            "rows_before_pubdate_filter": n_before,
            "rows_after_pubdate_filter": len(filtered),
        },
        "H1",
        location="crawler.py:crawl_for_date_filter",
    )
    return filtered
