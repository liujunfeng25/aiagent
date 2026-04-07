"""与 smart_logistics_bind/ajax.php 历史轨迹后处理对齐。"""
import math
import os
from typing import List

HISTORY_MAX_SPAN_SEC = 864000  # 10 天
HISTORY_MAX_POINTS = 5000
JITTER_MAX_SEC = 120


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def monitor_time_from_time_ms(time_ms: int) -> int:
    mt = int(time_ms or 0)
    if mt > 20000000000:
        mt = int(mt / 1000)
    return mt


def raw_points_to_sxw_points(raw: List[dict]) -> List[dict]:
    """将 Gps18 解析结果转为带 monitorTime（秒）的轨迹点。"""
    out = []
    for p in raw:
        lng = float(p.get("lng") or 0)
        lat = float(p.get("lat") or 0)
        if lng == 0.0 and lat == 0.0:
            continue
        tms = int(p.get("time_ms") or 0)
        mt = monitor_time_from_time_ms(tms)
        if mt <= 0:
            continue
        spd = p.get("speed", "")
        out.append({
            "lng": round(lng, 6),
            "lat": round(lat, 6),
            "monitorTime": mt,
            "speed": str(spd) if spd is not None and str(spd) != "" else "",
            "address": "",
            "tmp1": "",
            "hum1": "",
        })
    out.sort(key=lambda x: x["monitorTime"])
    return out


def history_dedupe_positions(points: List[dict]) -> List[dict]:
    """_history_dedupe_positions"""
    out = []
    prev = None
    for p in points:
        if prev is not None:
            if (
                abs(p["lng"] - prev["lng"]) < 1e-5
                and abs(p["lat"] - prev["lat"]) < 1e-5
                and abs(int(p["monitorTime"]) - int(prev["monitorTime"])) <= JITTER_MAX_SEC
            ):
                continue
        out.append(p)
        prev = p
    return out


def history_merge_chain_by_distance(points: List[dict], max_meters: float) -> List[dict]:
    """_history_merge_chain_by_distance"""
    if max_meters <= 0 or len(points) < 2:
        return points
    out = []
    last = None
    for p in points:
        if last is None:
            out.append(p)
            last = p
            continue
        m = _haversine_m(last["lat"], last["lng"], p["lat"], p["lng"])
        if m < max_meters:
            continue
        out.append(p)
        last = p
    return out if out else points


def history_truncate_points(points: List[dict], max_n: int) -> List[dict]:
    n = len(points)
    if n <= max_n:
        return points
    step = int(math.ceil(n / max_n))
    return [points[i] for i in range(0, n, step)]


def history_demo_points(start_ts: int, end_ts: int) -> List[dict]:
    """_history_demo_points"""
    n = 40
    base_lng, base_lat = 116.383, 39.901
    pts = []
    for i in range(n):
        t = 0.0 if n <= 1 else i / (n - 1)
        ts = int(round(start_ts + (end_ts - start_ts) * t))
        lng = base_lng + 0.022 * math.sin(t * math.pi * 2)
        lat = base_lat + 0.012 * math.cos(t * math.pi * 2)
        pts.append({
            "lng": round(lng, 6),
            "lat": round(lat, 6),
            "monitorTime": ts,
            "speed": str(round(15.0 + math.sin(i * 0.3) * 8.0, 1)),
            "address": f"演示轨迹点 {i + 1}（非真实北斗定位数据）",
            "tmp1": f"{round(16.0 + math.sin(i * 0.2) * 2.0, 1)}℃",
            "hum1": f"{round(45.0 + math.cos(i * 0.15) * 5.0, 1)}%RH",
        })
    return pts


def apply_history_post_chain(points: List[dict]) -> List[dict]:
    pts = history_dedupe_positions(points)
    merge_m = float(os.getenv("ELITECH_HISTORY_STATIONARY_MERGE_METERS", "0") or 0)
    if merge_m > 0 and len(pts) > 1:
        pts = history_merge_chain_by_distance(pts, merge_m)
    return history_truncate_points(pts, HISTORY_MAX_POINTS)
