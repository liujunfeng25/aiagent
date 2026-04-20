"""高德影像瓦片代理：Key 仅服务端使用，避免暴露给前端与规避浏览器跨域。"""
from __future__ import annotations

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.amap_geocode import amap_key

router = APIRouter()

_TIMEOUT = (2.0, 12.0)


@router.get("/tiles/amap")
def proxy_amap_satellite_tile(
    z: int = Query(..., ge=0, le=18),
    x: int = Query(..., ge=0),
    y: int = Query(..., ge=0),
) -> Response:
    key = amap_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="未配置 AMAP_WEB_KEY / GAODE_MAP_KEY，无法代理高德影像瓦片。",
        )
    n = 1 << z
    if x >= n or y >= n:
        raise HTTPException(status_code=400, detail="瓦片坐标超出当前级别范围")
    host = 1 + ((x + y + z) % 4)
    url = (
        f"https://webst0{host}.is.autonavi.com/appmaptile?"
        f"style=6&x={x}&y={y}&z={z}&lang=zh_cn&size=1&scale=1&key={key}"
    )
    try:
        r = requests.get(url, timeout=_TIMEOUT)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"高德瓦片请求失败: {e!s}") from e
    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"高德瓦片 HTTP {r.status_code}",
        )
    ct = r.headers.get("content-type", "image/png")
    if not ct.startswith("image/"):
        ct = "image/png"
    return Response(content=r.content, media_type=ct)
