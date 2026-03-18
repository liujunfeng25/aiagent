# -*- coding: utf-8 -*-
"""
报价抓取（新发地）模块路由：API 与页面。
"""

from datetime import date, timedelta
import threading

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from config import PROJECT_ROOT
from app.xinfadi.crawler import crawl_for_date

router = APIRouter()

cache = {}
current_job = {"date": None, "progress": 0, "result": None, "error": None}
job_lock = threading.Lock()


def default_date():
    d = date.today() - timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def api_date_str(d):
    return d.replace("-", "/") if d else ""


def run_crawl(target_date):
    global current_job
    api_date = api_date_str(target_date)

    def progress_cb(current_page, total_count, pct):
        with job_lock:
            current_job["progress"] = pct

    try:
        rows = crawl_for_date(api_date, progress_callback=progress_cb)
        with job_lock:
            current_job["progress"] = 100
            current_job["result"] = rows
            current_job["error"] = None
    except Exception as e:
        with job_lock:
            current_job["progress"] = 0
            current_job["result"] = None
            current_job["error"] = str(e)


def _crawl_then_cache(target_date):
    global current_job, cache
    run_crawl(target_date)
    with job_lock:
        if current_job["result"] is not None:
            cache[target_date] = current_job["result"]
        current_job["date"] = None
        current_job["progress"] = 0
        current_job["result"] = None
        current_job["error"] = None


# --- 页面（独立 HTML，供 iframe 使用）---

@router.get("/admin/price", include_in_schema=False)
def price_page(request: Request):
    from starlette.templating import Jinja2Templates
    templates_dir = PROJECT_ROOT / "templates"
    if not templates_dir.exists():
        templates_dir.mkdir(parents=True, exist_ok=True)
    templates = Jinja2Templates(directory=str(templates_dir))
    return templates.TemplateResponse(
        "admin/price.html",
        {"request": request, "default_date": default_date()},
    )


# --- API ---

@router.get("/api/xinfadi/default_date")
def api_default_date():
    return {"date": default_date()}


@router.get("/api/xinfadi/data")
def api_data(date: str = Query("")):
    d = date.strip()
    if not d:
        return JSONResponse({"error": "缺少 date 参数"}, status_code=400)
    if d in cache:
        return {"date": d, "data": cache[d]}
    with job_lock:
        if current_job["date"] == d:
            if current_job["error"]:
                return {"date": d, "data": [], "error": current_job["error"]}
            if current_job["result"] is not None:
                return {"date": d, "data": current_job["result"]}
            return JSONResponse({"date": d, "data": [], "status": "crawling"}, status_code=202)
    return {"date": d, "data": []}


@router.post("/api/xinfadi/crawl")
def api_crawl(date: str = Query("")):
    d = date.strip()
    if not d:
        return JSONResponse({"error": "缺少 date 参数"}, status_code=400)
    with job_lock:
        if current_job["date"] == d and current_job["result"] is not None:
            return {"status": "done", "progress": 100}
        if current_job["date"] == d and current_job["error"]:
            return {"status": "error", "progress": 0, "message": current_job["error"]}
        if current_job["date"] == d:
            return {"status": "crawling", "progress": current_job["progress"]}
        if current_job["date"] is not None:
            return JSONResponse({"status": "busy", "message": "请等待当前爬取任务完成"}, status_code=409)
        if d in cache:
            return {"status": "cached", "progress": 100}
        current_job["date"] = d
        current_job["progress"] = 0
        current_job["result"] = None
        current_job["error"] = None
    t = threading.Thread(target=_crawl_then_cache, args=(d,))
    t.daemon = True
    t.start()
    return {"status": "started"}


@router.get("/api/xinfadi/progress")
def api_progress(date: str = Query("")):
    d = date.strip()
    if not d:
        return JSONResponse({"error": "缺少 date 参数"}, status_code=400)
    with job_lock:
        if current_job["date"] != d:
            if d in cache:
                return {"status": "done", "progress": 100}
            return {"status": "idle", "progress": 0}
        if current_job["error"]:
            return {"status": "error", "progress": 0, "message": current_job["error"]}
        if current_job["result"] is not None:
            return {"status": "done", "progress": 100}
        return {"status": "crawling", "progress": current_job["progress"]}
