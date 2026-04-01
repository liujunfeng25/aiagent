# -*- coding: utf-8 -*-
"""
新发地报价：内存任务与缓存（单进程 / 单 worker 有效；多 worker 时状态不一致）。
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# 单行爬取与批量补数共用，避免并发打爆源站
XINFADI_CRAWL_LOCK = threading.Lock()
BACKFILL_MAX_SPAN_DAYS = 366
BACKFILL_LOG_MAX = 400

from config import PROJECT_ROOT, XINFADI_PRICE_CACHE_DIR

from app.xinfadi.crawler import crawl_for_date, filter_by_pub_date


# region agent log
def _debug_log_path() -> Path:
    p = PROJECT_ROOT.parent / ".cursor" / "debug-32f924.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _agent_log(message: str, data: dict[str, Any], hypothesis_id: str, location: str = "") -> None:
    try:
        p = _debug_log_path()
        line = {
            "sessionId": "32f924",
            "location": location or "store.py:_agent_log",
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


def _api_date_slash(ymd: str) -> str:
    return ymd.replace("-", "/") if ymd else ""


def _history_crawl_max_age_days() -> int:
    """0 或负数表示不限制（任意未缓存日期都允许全量爬取）。"""
    raw = (os.environ.get("XINFADI_HISTORY_CRAWL_MAX_AGE_DAYS") or "365").strip()
    try:
        return int(raw)
    except ValueError:
        return 365


def _parse_iso_date(ymd: str) -> date | None:
    ymd = (ymd or "").strip()
    parts = ymd.split("-")
    if len(parts) != 3:
        return None
    try:
        y, m, d0 = int(parts[0]), int(parts[1]), int(parts[2])
        return date(y, m, d0)
    except ValueError:
        return None


def _disk_cache_path(d: str) -> Path:
    return XINFADI_PRICE_CACHE_DIR / f"{d}.json"


def _iter_day_strs(start: str, end: str) -> list[str]:
    a = _parse_iso_date(start)
    b = _parse_iso_date(end)
    if not a or not b or a > b:
        return []
    out: list[str] = []
    cur = a
    while cur <= b:
        out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def _fmt_m_d_cn(d: str) -> str:
    dt = datetime.strptime(d.strip()[:10], "%Y-%m-%d").date()
    return f"{dt.month}月{dt.day}日"


def _missing_cache_days(start: str, end: str) -> list[str]:
    return [d for d in _iter_day_strs(start, end) if not _disk_cache_path(d).is_file()]


def _history_uncached_should_refuse(d: str) -> tuple[bool, str]:
    max_age = _history_crawl_max_age_days()
    if max_age <= 0:
        return (False, "")
    req = _parse_iso_date(d)
    if req is None:
        return (False, "")
    age_days = (date.today() - req).days
    if age_days <= max_age:
        return (False, "")
    msg = (
        f"所选日期距今超过 {max_age} 天且本地无缓存：演示场景下不自动全量拉取（可能需数分钟）。 "
        "请选近期日期展示「实时拉取」，或提前在后台查询一次以写入本地缓存（变量 XINFADI_HISTORY_CRAWL_MAX_AGE_DAYS=0 可关闭此限制）。"
    )
    return (True, msg)


class PriceJobStore:
    """缓存 + 单任务进度 + 上次失败原因；与 /data、/crawl、/progress 语义对齐。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._job: dict[str, Any] | None = None
        self._last_err: dict[str, Any] = {"date": None, "message": None}
        self._backfill: dict[str, Any] | None = None

    def _warm_from_disk(self, d: str) -> None:
        if d in self._cache:
            return
        path = _disk_cache_path(d)
        if not path.is_file():
            return
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError, TypeError):
            return
        if not isinstance(data, list):
            return
        with self._lock:
            if d not in self._cache:
                self._cache[d] = data

    @staticmethod
    def _persist_cache(d: str, rows: list[dict[str, Any]]) -> None:
        try:
            XINFADI_PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = _disk_cache_path(d)
            path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def get_data(self, d: str) -> tuple[dict[str, Any], int]:
        self._warm_from_disk(d)
        if d in self._cache:
            body = {"date": d, "data": filter_by_pub_date(self._cache[d], d)}
            _agent_log(
                "get_data",
                {"branch": "cache", "date": d, "data_len": len(body["data"]), "status": 200},
                "H4",
            )
            return (body, 200)
        with self._lock:
            j = self._job
            if j and j["date"] == d:
                if j["error"]:
                    body = {"date": d, "data": [], "error": j["error"]}
                    _agent_log(
                        "get_data",
                        {"branch": "job_error", "date": d, "error": j["error"][:200]},
                        "H3",
                    )
                    return (body, 200)
                if j["result"] is not None:
                    body = {"date": d, "data": j["result"]}
                    _agent_log(
                        "get_data",
                        {"branch": "job_result", "date": d, "data_len": len(body["data"])},
                        "H4",
                    )
                    return (body, 200)
                _agent_log("get_data", {"branch": "job_crawling", "date": d}, "H4")
                return ({"date": d, "data": [], "status": "crawling"}, 202)
            if self._last_err["date"] == d and self._last_err["message"]:
                _agent_log(
                    "get_data",
                    {
                        "branch": "last_error",
                        "date": d,
                        "msg": str(self._last_err["message"])[:200],
                    },
                    "H3",
                )
                return (
                    {"date": d, "data": [], "error": self._last_err["message"]},
                    200,
                )
        refuse, hint = _history_uncached_should_refuse(d)
        if refuse:
            body = {"date": d, "data": [], "error": hint}
            _agent_log(
                "get_data",
                {"branch": "history_refused", "date": d, "max_age_days": _history_crawl_max_age_days()},
                "H4",
            )
            return (body, 200)
        _agent_log("get_data", {"branch": "empty_no_job", "date": d}, "H4")
        return ({"date": d, "data": []}, 200)

    def post_crawl(self, d: str) -> tuple[dict[str, Any], int]:
        self._warm_from_disk(d)
        with self._lock:
            bf = self._backfill
            if bf and bf.get("running"):
                return (
                    {
                        "status": "busy",
                        "message": "批量补数进行中，请稍候再试单日抓取",
                    },
                    409,
                )
            j = self._job
            if j and j["date"] == d:
                if j["result"] is not None:
                    return ({"status": "done", "progress": 100}, 200)
                if j["error"]:
                    return ({"status": "error", "progress": 0, "message": j["error"]}, 200)
                pr0 = int(j.get("progress") or 0)
                return ({"status": "crawling", "progress": max(pr0, 3)}, 200)
            if j is not None and j.get("date") is not None:
                return (
                    {
                        "status": "busy",
                        "message": "请等待当前爬取任务完成",
                        "busy_date": j["date"],
                    },
                    409,
                )
            if d in self._cache:
                return ({"status": "cached", "progress": 100}, 200)
            refuse, hint = _history_uncached_should_refuse(d)
            if refuse:
                return (
                    {"status": "skipped_history", "progress": 0, "message": hint},
                    200,
                )
            self._last_err["date"] = None
            self._last_err["message"] = None
            self._job = {
                "date": d,
                "progress": 2,
                "result": None,
                "error": None,
                "crawl_page": 0,
                "crawl_total": 0,
            }
        t = threading.Thread(target=self._run_worker, args=(d,), daemon=True)
        t.start()
        return ({"status": "started", "progress": 6}, 200)

    def get_progress(self, d: str) -> tuple[dict[str, Any], int]:
        self._warm_from_disk(d)
        with self._lock:
            j = self._job
            if j is None or j["date"] != d:
                if d in self._cache:
                    return ({"status": "done", "progress": 100}, 200)
                if self._last_err["date"] == d and self._last_err["message"]:
                    return (
                        {
                            "status": "error",
                            "progress": 0,
                            "message": self._last_err["message"],
                        },
                        200,
                    )
                return ({"status": "idle", "progress": 0}, 200)
            if j["error"]:
                return ({"status": "error", "progress": 0, "message": j["error"]}, 200)
            if j["result"] is not None:
                return ({"status": "done", "progress": 100}, 200)
            pr = int(j.get("progress") or 0)
            total = int(j.get("crawl_total") or 0)
            page = int(j.get("crawl_page") or 0)
            est_pages = max(1, (total + 199) // 200) if total > 0 else 0
            return (
                {
                    "status": "crawling",
                    "progress": max(pr, 8),
                    "page": page,
                    "total_records": total,
                    "est_pages": est_pages,
                },
                200,
            )

    def _run_worker(self, target_date: str) -> None:
        api_date = _api_date_slash(target_date)

        def progress_cb(current_page: int, total_count: int, pct: int) -> None:
            with self._lock:
                j = self._job
                if j and j["date"] == target_date:
                    j["progress"] = pct
                    j["crawl_page"] = int(current_page or 0)
                    j["crawl_total"] = int(total_count or 0)

        try:
            with self._lock:
                j = self._job
                if j and j["date"] == target_date:
                    j["progress"] = max(int(j.get("progress") or 0), 5)
            with XINFADI_CRAWL_LOCK:
                rows = crawl_for_date(api_date, progress_callback=progress_cb)
            with self._lock:
                j = self._job
                if j and j["date"] == target_date:
                    j["progress"] = 100
                    j["result"] = rows
                    j["error"] = None
        except Exception as e:
            with self._lock:
                j = self._job
                if j and j["date"] == target_date:
                    j["progress"] = 0
                    j["result"] = None
                    j["error"] = str(e)

        with self._lock:
            j = self._job
            if j is None or j["date"] != target_date:
                _agent_log(
                    "worker_skip_finalize",
                    {"date": target_date, "reason": "job_mismatch_or_none"},
                    "H4",
                )
                return
            err_msg = j.get("error")
            res = j.get("result")
            if res is not None:
                self._cache[target_date] = res
                self._persist_cache(target_date, res)
                self._last_err["date"] = target_date
                self._last_err["message"] = None
                _agent_log(
                    "worker_done",
                    {"date": target_date, "result_len": len(res), "error": None},
                    "H2",
                )
            elif err_msg:
                self._last_err["date"] = target_date
                self._last_err["message"] = err_msg
                _agent_log(
                    "worker_done",
                    {"date": target_date, "result_len": 0, "error": str(err_msg)[:300]},
                    "H3",
                )
            self._job = None

    def _backfill_append_log(self, line: str) -> None:
        with self._lock:
            if not self._backfill:
                return
            logs: list[str] = self._backfill.setdefault("logs", [])
            logs.append(line)
            if len(logs) > BACKFILL_LOG_MAX:
                del logs[: len(logs) - BACKFILL_LOG_MAX]

    def get_backfill_status(self) -> dict[str, Any]:
        with self._lock:
            if not self._backfill:
                return {
                    "running": False,
                    "finished": False,
                    "total": 0,
                    "processed": 0,
                    "success": 0,
                    "current": None,
                    "progress_pct": 0.0,
                    "logs": [],
                }
            bf = self._backfill
            total = int(bf.get("total") or 0)
            processed = int(bf.get("processed") or 0)
            pct = round(100.0 * processed / total, 1) if total > 0 else 0.0
            return {
                "running": bool(bf.get("running")),
                "finished": bool(bf.get("finished")),
                "total": total,
                "processed": processed,
                "success": int(bf.get("success") or 0),
                "current": bf.get("current"),
                "progress_pct": pct,
                "logs": list(bf.get("logs") or []),
            }

    def dismiss_backfill_state(self) -> dict[str, Any]:
        """清除已结束或空闲的批量补数状态；执行中不清除。"""
        with self._lock:
            if self._backfill and self._backfill.get("running"):
                return {"cleared": False, "reason": "running"}
            self._backfill = None
        return {"cleared": True}

    def start_backfill(self, start_date: str, end_date: str) -> tuple[dict[str, Any], int]:
        s = (start_date or "").strip()
        e = (end_date or "").strip()
        if not s or not e:
            return ({"error": "请提供 start_date 与 end_date"}, 400)
        days = _iter_day_strs(s, e)
        if not days:
            return ({"error": "日期范围无效"}, 400)
        if len(days) > BACKFILL_MAX_SPAN_DAYS:
            return ({"error": f"区间最多 {BACKFILL_MAX_SPAN_DAYS} 天"}, 400)
        missing = _missing_cache_days(s, e)
        if not missing:
            with self._lock:
                if self._backfill and not self._backfill.get("running"):
                    self._backfill = None
            return (
                {
                    "started": False,
                    "message": "所选区间内没有缺失的本地缓存，无需补抓",
                    "missing": [],
                    "total": 0,
                },
                200,
            )
        with self._lock:
            if self._backfill and self._backfill.get("running"):
                return ({"error": "已有批量补数任务进行中"}, 409)
            if self._job is not None:
                return ({"error": "单行抓取任务进行中，请稍后再试"}, 409)
            self._backfill = {
                "running": True,
                "finished": False,
                "total": len(missing),
                "processed": 0,
                "success": 0,
                "current": None,
                "logs": [
                    f"[启动] 共 {len(missing)} 个日期待补抓（区间内无本地 JSON 的日期）",
                ],
            }
        t = threading.Thread(target=self._run_backfill_worker, args=(missing,), daemon=True)
        t.start()
        return (
            {
                "started": True,
                "total": len(missing),
                "missing_preview": missing[:30],
                "message": "任务已启动",
            },
            200,
        )

    def _run_backfill_worker(self, dates: list[str]) -> None:
        try:
            for d in dates:
                with self._lock:
                    bf = self._backfill
                    if not bf:
                        break
                    bf["current"] = d

                refuse, hint = _history_uncached_should_refuse(d)
                if refuse:
                    short = (hint or "超出策略限制")[:80]
                    self._backfill_append_log(f"⊘ 跳过 {_fmt_m_d_cn(d)}（{d}）：{short}")
                    with self._lock:
                        if self._backfill:
                            self._backfill["processed"] = int(self._backfill.get("processed") or 0) + 1
                    continue

                if _disk_cache_path(d).is_file():
                    self._backfill_append_log(f"◇ 已有缓存，跳过 {_fmt_m_d_cn(d)}（{d}）")
                    with self._lock:
                        if self._backfill:
                            self._backfill["processed"] = int(self._backfill.get("processed") or 0) + 1
                    continue

                api_date = _api_date_slash(d)
                self._backfill_append_log(f"… 正在抓取 {_fmt_m_d_cn(d)}（{d}）")
                try:
                    with XINFADI_CRAWL_LOCK:
                        rows = crawl_for_date(api_date, progress_callback=None)
                    with self._lock:
                        self._cache[d] = rows
                        self._persist_cache(d, rows)
                        if self._backfill:
                            self._backfill["success"] = int(self._backfill.get("success") or 0) + 1
                    self._backfill_append_log(f"✓ 已抓取 {_fmt_m_d_cn(d)}")
                except Exception as ex:
                    self._backfill_append_log(f"✗ {d} 失败：{str(ex)[:160]}")
                finally:
                    with self._lock:
                        if self._backfill:
                            self._backfill["processed"] = int(self._backfill.get("processed") or 0) + 1
        finally:
            with self._lock:
                if self._backfill:
                    self._backfill["running"] = False
                    self._backfill["finished"] = True
                    self._backfill["current"] = None
                    logs = self._backfill.setdefault("logs", [])
                    logs.append("[完成] 批量补数已结束，可关闭窗口并刷新图表")
                    if len(logs) > BACKFILL_LOG_MAX:
                        del logs[: len(logs) - BACKFILL_LOG_MAX]
