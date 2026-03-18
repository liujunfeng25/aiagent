# -*- coding: utf-8 -*-
"""
新发地价格爬虫核心：支持进度回调。
"""

import random
import time

import requests

BASE_URL = "http://wap.xinfadi.com.cn/getPriceData.html"
PER_PAGE = 200
MIN_DELAY = 0.8
MAX_DELAY = 1.8
MAX_RETRIES = 3
RETRY_DELAY = 5
ALLOWED_CAT_IDS = {1186, 1187, 1188, 1189, 1190, 1203, 1204}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

FIELDNAMES = ["一级分类", "二级分类", "品名", "最低价", "平均价", "最高价", "规格", "产地", "单位", "发布日期"]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "http://wap.xinfadi.com.cn",
        "Referer": "http://wap.xinfadi.com.cn/priceDetail.html",
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
            r = session.post(BASE_URL, data=data, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise e
    return None


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
    session.headers.update(get_headers())
    all_rows = []
    current = 1
    total_count = None

    while True:
        resp = fetch_page(session, date_str, current)
        count = resp.get("count", 0)
        if total_count is None:
            total_count = count
        if progress_callback and total_count:
            pct = min(100, round(current * PER_PAGE / total_count * 100))
            progress_callback(current, total_count, pct)

        lst = resp.get("list") or []
        if not lst:
            break
        for item in lst:
            cat_id = item.get("prodCatid")
            if cat_id is not None and cat_id in ALLOWED_CAT_IDS:
                all_rows.append(row_to_record(item))
        if current * PER_PAGE >= count:
            break
        current += 1
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    seen = set()
    unique = []
    for r in all_rows:
        key = (r["品名"], r["一级分类"], r["产地"], r["发布日期"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique
