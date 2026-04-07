# -*- coding: utf-8 -*-
"""
报价抓取（新发地）：HTTP 入口。业务状态见 store.PriceJobStore。
"""

from datetime import date, timedelta

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import PROJECT_ROOT
from app.xinfadi import crawler as xinfadi_crawler
from app.xinfadi import analytics as xinfadi_analytics
from app.xinfadi.store import PriceJobStore

router = APIRouter()
store = PriceJobStore()


class BackfillStartBody(BaseModel):
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")

_NOCACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _json_nocache(body: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=body, status_code=status_code, headers=_NOCACHE_HEADERS)


def default_date() -> str:
    d = date.today() - timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _embed_api_root(request: Request) -> str:
    """iframe 内 fetch 的 API 根：必须与浏览器地址栏同源（含主机名）。

    若优先用 scope.server 把 0.0.0.0 落成 127.0.0.1，而用户打开的是 http://localhost:8000，
    则 iframe 会请求 http://127.0.0.1:8000/api/...，与父页不同源，易出现 CORS/凭证或脚本表现异常。

    经 Vite 代理时 Host 为 localhost:5173，据此拼出的 URL 仍走 /api 代理，符合预期。
    """
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",")[0].strip()
    host_hdr = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    if host_hdr:
        return f"{proto}://{host_hdr}".rstrip("/")
    server = request.scope.get("server")
    if isinstance(server, (list, tuple)) and len(server) >= 2:
        host, port = str(server[0]), int(server[1])
        if host in ("0.0.0.0", "::", "[::]"):
            host = "127.0.0.1"
        scheme = (request.url.scheme or "http").split(",")[0].strip()
        if port in (80, 443):
            return f"{scheme}://{host}".rstrip("/")
        return f"{scheme}://{host}:{port}".rstrip("/")
    return str(request.base_url).rstrip("/")


@router.get("/admin/price", include_in_schema=False)
def price_page(request: Request):
    from starlette.templating import Jinja2Templates

    templates_dir = PROJECT_ROOT / "templates"
    if not templates_dir.exists():
        templates_dir.mkdir(parents=True, exist_ok=True)
    templates = Jinja2Templates(directory=str(templates_dir))
    api_xinfadi = f"{_embed_api_root(request)}/api/xinfadi"
    return templates.TemplateResponse(
        request,
        "admin/price.html",
        {
            "default_date": default_date(),
            "api_xinfadi": api_xinfadi,
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@router.get("/api/xinfadi/default_date")
def api_default_date():
    return {"date": default_date()}


@router.get("/api/xinfadi/polite_crawl")
def api_polite_crawl_get():
    return {"polite": xinfadi_crawler.polite_crawl_enabled()}


@router.post("/api/xinfadi/polite_crawl")
async def api_polite_crawl_post(request: Request):
    """支持 JSON 与 form-urlencoded，避免部分代理/环境下 application/json POST 异常。"""
    polite = False
    ct = (request.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        try:
            body = await request.json()
            if isinstance(body, dict):
                polite = bool(body.get("polite"))
        except Exception:
            polite = False
    else:
        form = await request.form()
        v = form.get("polite")
        if isinstance(v, str):
            polite = v.lower() in ("1", "true", "yes", "on")
        else:
            polite = bool(v)
    xinfadi_crawler.set_polite_crawl(polite)
    return {"polite": xinfadi_crawler.polite_crawl_enabled()}


@router.get("/api/xinfadi/data")
def api_data(date: str = Query("")):
    d = date.strip()
    if not d:
        return _json_nocache({"error": "缺少 date 参数"}, status_code=400)
    body, status = store.get_data(d)
    return _json_nocache(body, status_code=status)


@router.post("/api/xinfadi/crawl")
def api_crawl(date: str = Query("")):
    d = date.strip()
    if not d:
        return _json_nocache({"error": "缺少 date 参数"}, status_code=400)
    body, status = store.post_crawl(d)
    return _json_nocache(body, status_code=status)


@router.get("/api/xinfadi/progress")
def api_progress(date: str = Query("")):
    d = date.strip()
    if not d:
        return _json_nocache({"error": "缺少 date 参数"}, status_code=400)
    body, status = store.get_progress(d)
    return _json_nocache(body, status_code=status)


@router.post("/api/xinfadi/backfill")
def api_backfill_start(body: BackfillStartBody):
    """批量补抓区间内「无本地 JSON」的日期；与单行 crawl 互斥。"""
    out, status = store.start_backfill(body.start_date.strip(), body.end_date.strip())
    return _json_nocache(out, status_code=status)


@router.get("/api/xinfadi/backfill/status")
def api_backfill_status():
    return _json_nocache(store.get_backfill_status())


@router.post("/api/xinfadi/backfill/dismiss")
def api_backfill_dismiss():
    """关闭弹窗或开始新一轮前调用，清除服务端已结束的补数状态，避免下次误判。"""
    return _json_nocache(store.dismiss_backfill_state())


@router.get("/api/xinfadi/analytics/dates")
def api_analytics_dates():
    return _json_nocache({"dates": xinfadi_analytics.list_cached_dates()})


@router.get("/api/xinfadi/analytics/sentiment")
def api_analytics_sentiment():
    return _json_nocache(xinfadi_analytics.market_sentiment())


@router.get("/api/xinfadi/analytics/products")
def api_analytics_products(q: str = Query(""), limit: int = Query(120, ge=1, le=3000)):
    return _json_nocache({"names": xinfadi_analytics.product_name_hints(q, limit)})


@router.get("/api/xinfadi/analytics/timeseries")
def api_analytics_timeseries(
    start_date: str = Query(""),
    end_date: str = Query(""),
    prod_names: str = Query("", description="逗号分隔，精确匹配品名"),
    cat1: str = Query("", description="可选，一级分类精确匹配"),
):
    names = [x.strip() for x in (prod_names or "").split(",") if x.strip()]
    body = xinfadi_analytics.timeseries_aggregate(
        start_date.strip(),
        end_date.strip(),
        names,
        cat1.strip() or None,
    )
    if body.get("error"):
        return _json_nocache(body, status_code=400)
    return _json_nocache(body)
