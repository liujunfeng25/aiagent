# 高德 Web 地理编码 +简单文件缓存 + Haversine（可选，无 Key 则全部失败）
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from pathlib import Path
from typing import Any, Optional

import requests

_LOCK = threading.Lock()
_MEM_CACHE: dict[str, Optional[tuple[float, float]]] = {}

_GEO_URL = "https://restapi.amap.com/v3/geocode/geo"
_TIMEOUT = (2.0, 5.0)


def _data_dir() -> Path:
    base = Path(__file__).resolve().parent.parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _cache_path() -> Path:
    return _data_dir() / "amap_geocode_cache.json"


def _load_disk_cache() -> dict[str, list[float]]:
    p = _cache_path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        out: dict[str, list[float]] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, list) and len(v) == 2:
                    out[str(k)] = [float(v[0]), float(v[1])]
        return out
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _save_disk_cache(data: dict[str, list[float]]) -> None:
    try:
        _cache_path().write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def amap_key() -> str:
    return (os.environ.get("AMAP_WEB_KEY") or os.environ.get("GAODE_MAP_KEY") or "").strip()


def geocode_address(address: str, city: Optional[str] = None) -> Optional[tuple[float, float]]:
    """
    地理编码：返回 (lng, lat)。无 Key、空地址、失败时返回 None。
    """
    addr = (address or "").strip()
    if not addr:
        return None
    key = amap_key()
    if not key:
        return None

    ck = hashlib.sha256(f"{city or ''}|{addr}".encode("utf-8")).hexdigest()
    with _LOCK:
        if ck in _MEM_CACHE:
            return _MEM_CACHE[ck]

    disk = _load_disk_cache()
    if ck in disk:
        lng, lat = disk[ck]
        coord = (lng, lat)
        with _LOCK:
            _MEM_CACHE[ck] = coord
        return coord

    params: dict[str, Any] = {"key": key, "address": addr}
    if city and city.strip():
        params["city"] = city.strip()

    coord: Optional[tuple[float, float]] = None
    try:
        r = requests.get(_GEO_URL, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if str(data.get("status")) != "1":
            coord = None
        else:
            geos = data.get("geocodes") or []
            if not geos:
                coord = None
            else:
                loc = str(geos[0].get("location") or "")
                parts = loc.split(",")
                if len(parts) == 2:
                    coord = (float(parts[0]), float(parts[1]))
    except (requests.RequestException, ValueError, TypeError, KeyError):
        coord = None

    with _LOCK:
        _MEM_CACHE[ck] = coord
    if coord is not None:
        disk[ck] = [coord[0], coord[1]]
        _save_disk_cache(disk)
    return coord


def haversine_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return round(r * c, 2)
