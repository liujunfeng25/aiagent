# -*- coding: utf-8 -*-
"""新发地本地 JSON 缓存：分析聚合（无数据库）。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from config import XINFADI_PRICE_CACHE_DIR
from app.xinfadi.crawler import filter_by_pub_date

MAX_SPAN_DAYS = 366
DETAIL_ROWS_CAP = 800


def _parse_iso(s: str) -> date | None:
    try:
        return datetime.strptime((s or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def list_cached_dates() -> list[str]:
    if not XINFADI_PRICE_CACHE_DIR.is_dir():
        return []
    out: list[str] = []
    for p in XINFADI_PRICE_CACHE_DIR.glob("*.json"):
        stem = p.stem
        if len(stem) == 10 and stem[4] == "-" and stem[7] == "-" and _parse_iso(stem):
            out.append(stem)
    return sorted(out)


def _load_rows_for_day(d: str) -> list[dict[str, Any]]:
    path: Path = XINFADI_PRICE_CACHE_DIR / f"{d}.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return filter_by_pub_date(data, d)


def _num(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(str(val).strip().replace(",", ""))
    except ValueError:
        return None


def _categories_with_numeric_avg(rows: list[dict[str, Any]]) -> set[str]:
    """至少有一条有效「平均价」的一级分类集合。"""
    out: set[str] = set()
    for r in rows:
        if _num(r.get("平均价")) is None:
            continue
        c = (r.get("一级分类") or "").strip()
        if c:
            out.add(c)
    return out


def _day_mean_avg_price_in_categories(
    d: str, categories: set[str]
) -> float | None:
    """仅统计指定一级分类下、有数值平均价的行，做简单算术平均。"""
    rows = _load_rows_for_day(d)
    nums_f: list[float] = []
    for r in rows:
        if (r.get("一级分类") or "").strip() not in categories:
            continue
        v = _num(r.get("平均价"))
        if v is not None:
            nums_f.append(v)
    if not nums_f:
        return None
    return sum(nums_f) / len(nums_f)


def market_sentiment() -> dict[str, Any]:
    dates = list_cached_dates()
    if not dates:
        return {
            "has_data": False,
            "message": "暂无本地缓存数据，请先在「报价抓取」中拉取并落盘。",
            "latest_date": None,
            "previous_date": None,
            "change_pct": None,
            "direction": "flat",
        }
    latest = dates[-1]
    if len(dates) == 1:
        rows = _load_rows_for_day(latest)
        nums_f: list[float] = [x for x in (_num(r.get("平均价")) for r in rows) if x is not None]
        mu = sum(nums_f) / len(nums_f) if nums_f else None
        return {
            "has_data": True,
            "latest_date": latest,
            "previous_date": None,
            "change_pct": None,
            "direction": "flat",
            "message": f"仅有 {latest} 一日数据，暂无法对比涨跌。",
            "sample_mean": round(mu, 4) if mu is not None else None,
        }
    prev = dates[-2]
    rows_prev = _load_rows_for_day(prev)
    rows_last = _load_rows_for_day(latest)
    cats_prev = _categories_with_numeric_avg(rows_prev)
    cats_last = _categories_with_numeric_avg(rows_last)
    both_cats = cats_prev & cats_last
    if not both_cats:
        return {
            "has_data": True,
            "latest_date": latest,
            "previous_date": prev,
            "change_pct": None,
            "direction": "flat",
            "overlap_categories": 0,
            "message": (
                f"{prev} 与 {latest} 没有同时在两天出现且含有效均价的一级分类，暂无法对比景气度。"
            ),
        }

    m_prev = _day_mean_avg_price_in_categories(prev, both_cats)
    m_last = _day_mean_avg_price_in_categories(latest, both_cats)
    if m_prev is None or m_last is None or m_prev == 0:
        return {
            "has_data": True,
            "latest_date": latest,
            "previous_date": prev,
            "change_pct": None,
            "direction": "flat",
            "overlap_categories": len(both_cats),
            "message": "重叠一级分类下有效均价不足，暂无法计算整体景气度。",
        }
    pct = (m_last - m_prev) / m_prev * 100.0
    direction = "flat"
    if pct > 0.05:
        direction = "up"
    elif pct < -0.05:
        direction = "down"
    arrow = "↑" if direction == "up" else "↓" if direction == "down" else "→"
    ncat = len(both_cats)
    msg = (
        f"相对前一有数据日（{prev}→{latest}），"
        f"仅统计两天均出现的 {ncat} 个一级分类内全部报价行的均价，"
        f"变动{arrow}{abs(pct):.2f}%。"
    )
    return {
        "has_data": True,
        "latest_date": latest,
        "previous_date": prev,
        "change_pct": round(pct, 2),
        "direction": direction,
        "overlap_categories": ncat,
        "message": msg,
    }


def _iter_dates_str(start: date, end: date) -> list[str]:
    out: list[str] = []
    d = start
    while d <= end:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def timeseries_aggregate(
    start_date: str,
    end_date: str,
    prod_names: list[str],
    cat1: str | None,
) -> dict[str, Any]:
    s = _parse_iso(start_date)
    e = _parse_iso(end_date)
    if not s or not e or s > e:
        return {"error": "日期范围无效"}
    if (e - s).days + 1 > MAX_SPAN_DAYS:
        return {"error": f"区间最多 {MAX_SPAN_DAYS} 天"}
    names = [n.strip() for n in prod_names if (n or "").strip()]
    if not names:
        return {"error": "请至少选择一个品名"}
    cat1_s = (cat1 or "").strip()
    calendar = _iter_dates_str(s, e)

    series_out: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for pname in names:
        avg_list: list[float | None] = []
        low_list: list[float | None] = []
        high_list: list[float | None] = []
        n_list: list[int] = []

        for d in calendar:
            rows = _load_rows_for_day(d)
            matched = [
                r
                for r in rows
                if (r.get("品名") or "").strip() == pname
                and (not cat1_s or (r.get("一级分类") or "").strip() == cat1_s)
            ]
            if not matched:
                avg_list.append(None)
                low_list.append(None)
                high_list.append(None)
                n_list.append(0)
                continue
            avs = [_num(r.get("平均价")) for r in matched]
            avs_ok = [x for x in avs if x is not None]
            lows = [_num(r.get("最低价")) for r in matched]
            highs = [_num(r.get("最高价")) for r in matched]
            lows_ok = [x for x in lows if x is not None]
            highs_ok = [x for x in highs if x is not None]
            if not avs_ok:
                avg_list.append(None)
                low_list.append(min(lows_ok) if lows_ok else None)
                high_list.append(max(highs_ok) if highs_ok else None)
                n_list.append(len(matched))
            else:
                avg_list.append(sum(avs_ok) / len(avs_ok))
                low_list.append(min(lows_ok) if lows_ok else None)
                high_list.append(max(highs_ok) if highs_ok else None)
                n_list.append(len(matched))
            for r in matched:
                if len(details) < DETAIL_ROWS_CAP:
                    details.append(
                        {
                            "发布日期": d,
                            "品名": pname,
                            "一级分类": r.get("一级分类") or "",
                            "平均价": r.get("平均价") or "",
                            "最低价": r.get("最低价") or "",
                            "最高价": r.get("最高价") or "",
                            "产地": r.get("产地") or "",
                            "单位": r.get("单位") or "",
                        }
                    )

        series_out.append(
            {
                "name": pname,
                "avg": avg_list,
                "low": low_list,
                "high": high_list,
                "n": n_list,
            }
        )

    days_with_file = sum(1 for d in calendar if (XINFADI_PRICE_CACHE_DIR / f"{d}.json").is_file())
    points_total = sum(
        1 for ser in series_out for v in ser["avg"] if v is not None
    )

    return {
        "calendar_dates": calendar,
        "series": series_out,
        "details": details,
        "meta": {
            "prod_count": len(names),
            "day_count": len(calendar),
            "days_with_cache_file": days_with_file,
            "points_with_value": points_total,
        },
    }


def product_name_hints(query: str = "", limit: int = 120, sample_days: int = 90) -> list[str]:
    dates = list_cached_dates()
    if not dates:
        return []
    take = dates[-sample_days:]
    seen: set[str] = set()
    for d in take:
        for r in _load_rows_for_day(d):
            n = (r.get("品名") or "").strip()
            if n:
                seen.add(n)
    sorted_names = sorted(seen)
    q = (query or "").strip()
    if not q:
        return sorted_names[:limit]
    q_lower = q.lower()
    matched = [n for n in sorted_names if q in n or q_lower in n.lower()]
    return matched[:limit]
