"""
北斗 GPS18 API 封装（对齐 openapi.18gps.net GetDateServices.asmx）
与食迅 SXW `admin/inc/class/Gps18Api.class.php` + `smart_logistics_bind/ajax.php#get_history_track` 行为对齐：
- 历史轨迹先 getHistoryMByMUtcNew(macid)，空则 getHistoryMByMUtc(userID)，再空则批量列表按 macid 找 user_id 重试
- mapType 空串与 BAIDU 互斥重试（与 PHP alternateHistoryMapTypeForRetry 一致）
登录：GET /GetDateServices.asmx/loginSystem
数据：GET /GetDateServices.asmx/GetDate?method=...&mds=<session>
"""
import json
import os
import math
import re
import time
import requests
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo


_TRACK_JSON_HEAD = re.compile(r"^-?\d+\.\d+,-?\d+\.\d+,\d+")


def _looks_like_gps18_track_json_string(s: str) -> bool:
    """
    getHistoryMByMUtc 等接口有时整段 HTTP body 即一个 JSON 字符串，
    内容为分号分隔轨迹（非 {success,data} 对象）；r.json() 得到 str。
    """
    t = (s or "").strip()
    if len(t) < 24:
        return False
    if not _TRACK_JSON_HEAD.match(t):
        return False
    return ";" in t or bool(re.search(r",-?\d+\.\d+,-?\d+\.\d+,\d+", t))


def _json_response_dict(
    r: requests.Response,
    ctx: str,
    *,
    plain_track_string_ok: bool = False,
) -> dict:
    """GPS18 部分环境会返回非对象 JSON；对 str/list 调用 .get 会触发 'str' object has no attribute 'get'。"""
    try:
        data = r.json()
    except Exception as e:
        snippet = (r.text or "")[:240]
        raise RuntimeError(f"{ctx}: 响应非 JSON（{e}）；片段: {snippet!r}") from e
    # 部分 GetDate/登录接口会把整段 JSON 再序列化成字符串返回（顶层为 JSON string，可达十余 KB）
    for _ in range(6):
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            t = data.strip()
            if not t:
                break
            try:
                data = json.loads(t)
                continue
            except Exception as e:
                if plain_track_string_ok and _looks_like_gps18_track_json_string(t):
                    return {
                        "success": "true",
                        "errorCode": "200",
                        "errorDescribe": "",
                        "data": t,
                    }
                preview = (t[:320] + ("…" if len(t) > 320 else "")).replace("\n", " ")
                raise RuntimeError(
                    f"{ctx}: 期望 JSON 对象，收到 JSON 字符串但二次解析失败（{e}）；片段: {preview!r}"
                ) from e
        break
    preview = repr(data)
    if len(preview) > 400:
        preview = preview[:400] + "…"
    raise RuntimeError(f"{ctx}: 期望 JSON 对象，实际为 {type(data).__name__}: {preview}")


_API_BASE = os.getenv("GPS18_OPENAPI_BASE", "http://openapi.18gps.net").rstrip("/")
_LOGIN_PATH = "/GetDateServices.asmx/loginSystem"
_GETDATE_PATH = "/GetDateServices.asmx/GetDate"
_MDS_CACHE_TTL = int(os.getenv("GPS18_MDS_CACHE_SECONDS", "1020"))  # 17 分钟

# 进程内 session 缓存
_session_cache: dict = {}  # {cache_key: {mds, unit_id, exp}}


def _cache_key(login_name: str) -> str:
    return f"{_API_BASE}|{login_name}"


def _load_session(login_name: str) -> Optional[dict]:
    key = _cache_key(login_name)
    s = _session_cache.get(key)
    if s and time.time() + 90 < s["exp"]:
        return s
    return None


def _save_session(login_name: str, mds: str, unit_id: str):
    key = _cache_key(login_name)
    _session_cache[key] = {"mds": mds, "unit_id": unit_id, "exp": time.time() + _MDS_CACHE_TTL}


def _clear_session(login_name: str):
    _session_cache.pop(_cache_key(login_name), None)


def _coord_transform_lat(x: float, y: float) -> float:
    """与 sxw Gps18Api::coordTransformLat（入参已为 lng-105、lat-35）。"""
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _coord_transform_lng(x: float, y: float) -> float:
    """与 sxw Gps18Api::coordTransformLng。"""
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def _wgs84_to_gcj02(lng: float, lat: float) -> tuple:
    """WGS84 → GCJ-02，与 sxw `Gps18Api::wgs84ToGcj02` 一致（必须用 lng-105、lat-35 代入多项式）。"""
    lng, lat = float(lng), float(lat)
    if lng < 72.004 or lng > 137.8347 or lat < 0.8293 or lat > 55.8271:
        return lng, lat
    a, ee = 6378245.0, 0.00669342162296594323
    x, y = lng - 105.0, lat - 35.0
    d_lat = _coord_transform_lat(x, y)
    d_lng = _coord_transform_lng(x, y)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - ee * magic * magic
    sqrt_m = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((a * (1 - ee)) / (magic * sqrt_m) * math.pi)
    d_lng = (d_lng * 180.0) / (a / sqrt_m * math.cos(rad_lat) * math.pi)
    return lng + d_lng, lat + d_lat


def _bd09_to_gcj02(lng: float, lat: float) -> tuple:
    """BD-09 → GCJ-02（高德底图），与 sxw `ElitechApi::bd09ToGcj02` 逐项一致。"""
    x_pi = math.pi * 3000.0 / 180.0
    x = float(lng) - 0.0065
    y = float(lat) - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    return z * math.cos(theta), z * math.sin(theta)


def _lng_lat_to_amap_gcj02(lng: float, lat: float, map_type_used: Optional[str]) -> tuple:
    """与 sxw `Gps18Api::lngLatToAmapGcj02`：按 mapType（如 BAIDU）将接口经纬度转为高德 GCJ-02（bd09 分支同 `ElitechApi::bd09ToGcj02`）。"""
    mode = ""
    if map_type_used is not None and str(map_type_used).strip():
        mode = str(map_type_used).strip().lower()
    if not mode:
        mode = os.getenv("GPS18_COORD_FOR_AMAP", "auto").strip().lower()
    if mode in ("", "auto"):
        # 与 mapTypeForLatest 一致；仅设 GPS18_HISTORY_MAP_TYPE 时批量/实时也按历史坐标系推断（.env 常见）
        mt = os.getenv("GPS18_MAP_TYPE", "").strip().lower()
        if not mt:
            mt = os.getenv("GPS18_HISTORY_MAP_TYPE", "").strip().lower()
        if mt == "baidu":
            mode = "bd09"
        elif mt in ("gaode", "amap"):
            mode = "gcj02"
        else:
            mode = "wgs84"
    if mode in ("gcj02", "gcj", "mars", "gaode", "amap"):
        return lng, lat
    if mode in ("bd09", "baidu"):
        return _bd09_to_gcj02(lng, lat)
    return _wgs84_to_gcj02(lng, lat)


def normalize_beidou_macid(s: Optional[str]) -> str:
    """与 Gps18Api::normalizeBeidouMatchString：去空白、全角数字转半角。"""
    if not s:
        return ""
    t = re.sub(r"\s+", "", str(s).strip())
    fw = str.maketrans("０１２３４５６７８９", "0123456789")
    return t.translate(fw)


def _beidou_device_ids_equal(a: str, b: str) -> bool:
    a = normalize_beidou_macid(a)
    b = normalize_beidou_macid(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if a.isdigit() and b.isdigit():
        aa = a.lstrip("0") or "0"
        bb = b.lstrip("0") or "0"
        return aa == bb
    return False


def _row_beidou_id_candidates(row: dict) -> List[str]:
    keys_interest = {"sim_id", "sim", "macid", "device_id", "imei"}
    out: List[str] = []
    for rk, v in row.items():
        if v is None or (not isinstance(v, (str, int, float))):
            continue
        vs = str(v).strip()
        if not vs:
            continue
        rkl = str(rk).lower()
        if rkl in keys_interest:
            out.append(vs)
    un = row.get("user_name")
    if un is not None and isinstance(un, (str, int, float)):
        un_s = str(un).strip()
        if un_s and re.match(r"^\d{8,}$", un_s):
            out.append(un_s)
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def find_device_by_macid_in_list(macid: str, devices: List[dict]) -> Optional[dict]:
    """与 Gps18Api::findDeviceByMacidInList"""
    mn = normalize_beidou_macid(macid)
    if not mn:
        return None
    for row in devices:
        if not isinstance(row, dict):
            continue
        for cand in _row_beidou_id_candidates(row):
            if _beidou_device_ids_equal(mn, cand):
                return row
    return None


def beidou_row_user_id(row: dict) -> str:
    """与 Gps18Api::beidouRowUserId：列名归一化后为 userId 的字段值。"""
    for rk, v in row.items():
        if v is None or not isinstance(v, (str, int, float)):
            continue
        s = str(v).strip()
        if not s:
            continue
        norm_k = str(rk).lower().replace("_", "").replace("-", "")
        if norm_k == "userid":
            return s
    return ""


def _fill_beidou_location_type_default(row: dict) -> None:
    """与 Gps18Api::fillBeidouLocationTypeDefault"""
    ui = row.get("ui")
    if not isinstance(ui, dict):
        return
    if str(ui.get("location_type") or "").strip():
        return
    jg, wd = row.get("jingdu"), row.get("weidu")
    if jg is None or wd is None or str(jg).strip() == "" or str(wd).strip() == "":
        return
    try:
        float(jg)
        float(wd)
    except (TypeError, ValueError):
        return
    row["ui"]["location_type"] = (os.getenv("GPS18_UI_POSITION_TYPE", "") or "北斗").strip() or "北斗"


def enrich_beidou_device_row(row: dict) -> dict:
    """与 Gps18Api::enrichBeidouDeviceRow 对齐（温度/湿度/电压/ICCID 等 ui 块）。"""
    blob = ""
    for k in ("statenumber", "electric", "describe", "status"):
        if k not in row or row[k] is None or row[k] == "":
            continue
        v = row[k]
        if isinstance(v, (str, int, float, bool)):
            blob += " " + str(v)
    blob = blob.strip()
    ui = {
        "temperature": "",
        "bracket_temp": "",
        "humidity": "",
        "voltage_v": "",
        "iccid": "",
        "status_summary": "",
        "location_type": "",
        "raw_snippet": "",
    }
    if blob:
        ui["raw_snippet"] = (blob[:120] + "…") if len(blob) > 120 else blob
    if not blob:
        row["ui"] = ui
        _fill_beidou_location_type_default(row)
        uid = beidou_row_user_id(row)
        if uid:
            row["user_id"] = uid
        return row

    m_hash = re.findall(r"#([\d.]+)\s*℃", blob)
    if m_hash:
        ui["temperature"] = m_hash[-1] + "℃"
    else:
        m_plain = re.search(r"([\d.]+)\s*℃", blob)
        if m_plain:
            ui["temperature"] = m_plain.group(1) + "℃"
    bracket_temps = []
    for one in re.finditer(r"\b(\d+)#([\d.]+)\s*℃", blob):
        bracket_temps.append(f"{one.group(1)}#{one.group(2)}℃")
    if bracket_temps:
        ui["bracket_temp"] = " ".join(bracket_temps)
    mh = re.findall(r"#([\d.]+)\s*%", blob)
    if mh:
        ui["humidity"] = mh[-1] + "%"
    else:
        mh2 = re.search(r"([\d.]+)\s*%", blob)
        if mh2:
            ui["humidity"] = mh2.group(1) + "%"
    mi = re.search(r"\b(89\d{17}\d?)\b", blob)
    if mi:
        ui["iccid"] = mi.group(1)
    p_y = blob.find("℃")
    if p_y >= 0:
        cut = blob[p_y + 1 :]
        for cand in re.findall(r",([\d.]+)", cut):
            try:
                f = float(cand)
            except ValueError:
                continue
            if 10.0 <= f <= 28.0:
                ui["voltage_v"] = cand
                break
    hints = []
    if re.search(r"停车", blob) or re.search(r"Parking", blob, re.I):
        hints.append("停车")
    if re.search(r"Driving", blob, re.I):
        hints.append("行驶")
    su = row.get("su")
    if su is not None and str(su).strip() != "":
        try:
            if float(su) <= 0.01:
                hints.append("静止")
        except (TypeError, ValueError):
            pass
    if hints:
        ui["status_summary"] = "/".join(dict.fromkeys(hints))
    if re.search(r"北斗", blob, re.I) or re.search(r"\bBD\b", blob, re.I):
        ui["location_type"] = "北斗"
    elif re.search(r"\bGPS\b", blob, re.I):
        ui["location_type"] = "GPS"
    sim = row.get("sim")
    if (
        isinstance(sim, str)
        and re.match(r"^\d{18,20}$", sim.strip())
        and not ui["iccid"]
    ):
        ui["iccid"] = sim.strip()
    row["ui"] = ui
    _fill_beidou_location_type_default(row)
    uid = beidou_row_user_id(row)
    if uid:
        row["user_id"] = uid
    return row


def _coerce_history_points_list(pts) -> List[dict]:
    """
    历史接口偶发将「单点」以 dict 返回；若对 dict 做 list(...) 会得到键名字符串，
    进而在 merge 排序时触发 'str' object has no attribute 'get'。
    """
    if pts is None:
        return []
    if isinstance(pts, dict):
        pts = [pts]
    if not isinstance(pts, list):
        return []
    out: List[dict] = []
    for p in pts:
        if isinstance(p, dict):
            out.append(p)
    return out


def _format_sxw_display_time(dt_raw) -> str:
    """将平台下发的毫秒/秒级数字时间戳格式化为北京时间（与卡片展示一致）。"""
    if dt_raw is None:
        return ""
    s = str(dt_raw).strip()
    if not s:
        return ""
    if re.fullmatch(r"\d+", s):
        try:
            v = int(s)
            if v > 20000000000:
                sec = v / 1000.0
            else:
                sec = float(v)
            tz = ZoneInfo(os.getenv("GPS18_DISPLAY_TZ", "Asia/Shanghai"))
            return datetime.fromtimestamp(sec, tz=tz).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError, OverflowError):
            return s
    return s


def _extract_history_data_string(resp: dict, depth: int = 0) -> str:
    """与 Gps18Api::extractHistoryDataString 等价的 Python 实现（尽量从嵌套 data 中抽出轨迹串）。"""
    if depth > 14 or not isinstance(resp, dict) or "data" not in resp:
        return ""
    d = resp["data"]
    if isinstance(d, str):
        t = d.strip()
        return t if t else ""
    if not isinstance(d, list) and not isinstance(d, dict):
        return ""
    if isinstance(d, dict):
        if isinstance(d.get("point"), str) and d["point"].strip():
            return d["point"].strip()
        for k in ("Point", "points", "data", "track", "result", "rows", "list"):
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        if isinstance(d.get(0), str):
            t = d[0].strip()
            if t:
                if t[0] in "{[" and len(t) > 4:
                    try:
                        j = json.loads(t)
                        if isinstance(j, (dict, list)):
                            nested = _extract_history_data_string({"data": j}, depth + 1)
                            if nested:
                                return nested
                    except Exception:
                        pass
                if ";" in t or re.match(r"^-?\d+\.?\d*,-?\d+\.?\d*,\d+", t):
                    return t
        for v in d.values():
            if isinstance(v, str) and len(v) >= 8:
                if ";" in v or re.match(r"^-?\d+\.?\d*,-?\d+\.?\d*,\d+", v):
                    return v
        for v in d.values():
            if isinstance(v, dict):
                nested = _extract_history_data_string({"data": v}, depth + 1)
                if nested:
                    return nested
        return ""
    # list：与 PHP foreach 一致（勿只取 d[0]，否则错过后续元素里的轨迹串）
    if not d:
        return ""
    if isinstance(d[0], str) and d[0].strip():
        nested = _extract_history_data_string({"data": d[0]}, depth + 1)
        if nested:
            return nested
    coord_pat = re.compile(r"^-?\d+\.?\d*,-?\d+\.?\d*,\d+")
    for v in d:
        if isinstance(v, str) and len(v) >= 8:
            if ";" in v or coord_pat.match(v.strip()):
                return v.strip()
    for v in d:
        if isinstance(v, dict):
            nested = _extract_history_data_string({"data": v}, depth + 1)
            if nested:
                return nested
    if isinstance(d[0], dict):
        return _extract_history_data_string({"data": d[0]}, depth + 1)
    return ""


def _alternate_history_map_type(used: str) -> Optional[str]:
    """与 Gps18Api::alternateHistoryMapTypeForRetry"""
    if os.getenv("GPS18_HISTORY_MAPTYPE_FALLBACK", "1") == "0":
        return None
    u = (used or "").strip().upper()
    if u == "":
        return "BAIDU"
    if u == "BAIDU":
        return ""
    return None


def _parse_history_points(raw: str, map_type_used: Optional[str] = None) -> list:
    """解析分号分隔轨迹串；坐标按本次请求实际 mapType_used 转高德（与 PHP parseHistoryPoint + lngLatToAmapGcj02 一致）。"""
    points = []
    for seg in raw.split(";"):
        seg = seg.strip()
        if not seg:
            continue
        head = seg.split("bool#")[0].rstrip(",")
        parts = head.split(",", 5)
        if len(parts) < 3:
            continue
        try:
            lng, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        time_ms = int(parts[2]) if str(parts[2]).isdigit() else 0
        speed = parts[3] if len(parts) > 3 else ""
        course = parts[4] if len(parts) > 4 else ""
        gcj_lng, gcj_lat = _lng_lat_to_amap_gcj02(lng, lat, map_type_used)
        points.append({
            "lng": round(gcj_lng, 6),
            "lat": round(gcj_lat, 6),
            "time_ms": time_ms,
            "speed": speed,
            "course": course,
        })
    return points


def _history_norm_empty(norm: Optional[dict]) -> bool:
    if not norm:
        return True
    if norm.get("error"):
        return True
    return len(_coerce_history_points_list(norm.get("points"))) == 0


class Gps18Client:
    """GPS18 HTTP API 客户端（账号密码登录，session mds 自动缓存刷新）"""

    def __init__(self, login_name: Optional[str] = None, login_password: Optional[str] = None):
        self.login_name = (login_name or os.getenv("GPS18_LOGIN_NAME", "")).strip()
        self.login_password = login_password or os.getenv("GPS18_LOGIN_PASSWORD", "")

    def _login(self) -> dict:
        """调用 loginSystem，返回 {mds, unit_id}"""
        url = _API_BASE + _LOGIN_PATH
        params = {
            "LoginName": self.login_name,
            "LoginPassword": self.login_password,
            "LoginType": "ENTERPRISE",
            "language": "cn",
            "ISMD5": "0",
            "timeZone": "8",
            "apply": "APP",
        }
        r = requests.get(url, params=params, timeout=20)
        data = _json_response_dict(r, "GPS18 loginSystem")
        if not data.get("success") in (True, "true"):
            raise RuntimeError(f"GPS18 登录失败: {data.get('errorDescribe') or data}")
        mds = data.get("mds", "").strip()
        unit_id = str(data.get("id", "")).strip()
        uid_override = os.getenv("GPS18_UNIT_ID", "").strip()
        if uid_override:
            unit_id = uid_override
        if not mds or not unit_id:
            raise RuntimeError(f"GPS18 登录成功但缺少 mds/id: {data}")
        return {"mds": mds, "unit_id": unit_id}

    def _ensure_session(self) -> dict:
        s = _load_session(self.login_name)
        if s:
            return s
        tok = self._login()
        _save_session(self.login_name, tok["mds"], tok["unit_id"])
        return tok

    def _getdate(self, params: dict, retry: bool = True) -> dict:
        """调用 GetDate，遇 token 过期自动重登重试一次"""
        sess = self._ensure_session()
        params["mds"] = sess["mds"]
        url = _API_BASE + _GETDATE_PATH
        r = requests.get(url, params=params, timeout=30)
        data = _json_response_dict(
            r,
            f"GPS18 GetDate {params.get('method')}",
            plain_track_string_ok=True,
        )
        # 403/401 = token 过期
        if str(data.get("errorCode", "")) in ("403", "401") and retry:
            _clear_session(self.login_name)
            return self._getdate(params, retry=False)
        return data

    def get_device_list(self) -> list:
        """批量最新位置，返回所有设备行（已 enrich）"""
        sess = self._ensure_session()
        data = self._getdate({
            "method": "getDeviceListByCustomId",
            "id": sess["unit_id"],
            "mapType": os.getenv("GPS18_MAP_TYPE", ""),
        })
        if not data.get("success") in (True, "true"):
            raise RuntimeError(f"getDeviceListByCustomId 失败: {data.get('errorDescribe') or data}")
        raw_blk = data.get("data")
        if not isinstance(raw_blk, list) or not raw_blk:
            raise RuntimeError(f"getDeviceListByCustomId data 格式异常: {type(raw_blk).__name__}")
        block = raw_blk[0]
        if not isinstance(block, dict):
            raise RuntimeError(f"getDeviceListByCustomId data[0] 非对象: {type(block).__name__}")
        key_map = block.get("key")
        if not isinstance(key_map, dict):
            raise RuntimeError(f"getDeviceListByCustomId 缺少 key 映射: {type(key_map).__name__}")
        records = block.get("records") or []
        if not isinstance(records, list):
            raise RuntimeError(f"getDeviceListByCustomId records 非数组: {type(records).__name__}")
        devices = []
        for row in records:
            if not isinstance(row, list):
                continue
            item = {}
            for name, idx in key_map.items():
                try:
                    i = int(idx)
                except (TypeError, ValueError):
                    continue
                if i < len(row):
                    item[name] = row[i]
            devices.append(enrich_beidou_device_row(item))
        return devices

    def get_realtime(self, imei: str) -> dict:
        """按 IMEI 从批量列表中找到该设备的实时位置"""
        imei = imei.strip().lstrip("0") or imei.strip()
        devices = self.get_device_list()
        imei_norm = imei.lstrip("0") or imei
        matched = None
        for d in devices:
            for field in ("sim_id", "sim", "macid", "device_id", "imei", "user_name"):
                val = str(d.get(field, "")).strip()
                if val and (val == imei or val.lstrip("0") == imei_norm):
                    matched = d
                    break
            if matched:
                break
        # 账号下只有 1 台设备时直接返回（平台 sim_id 与 vehicle.imei 可能不同）
        if not matched and len(devices) == 1:
            matched = devices[0]
            matched["_imei_mismatch"] = True
        if not matched:
            return {"error": f"未找到 IMEI={imei} 的设备", "total_devices": len(devices)}

        lng_raw = float(matched.get("jingdu") or 0)
        lat_raw = float(matched.get("weidu") or 0)
        # 与 sxw get_realtime_data：`lngLatToAmapGcj02($jg, $wd, null)`，含 BAIDU→GCJ 与 WGS 多项式
        gcj_lng, gcj_lat = _lng_lat_to_amap_gcj02(lng_raw, lat_raw, None)

        return {
            "lng": round(gcj_lng, 6),
            "lat": round(gcj_lat, 6),
            "speed": matched.get("su"),
            "course": matched.get("fx"),
            "gps_time": matched.get("gpstime") or matched.get("time"),
            "address": matched.get("address") or matched.get("addr"),
            "imei": imei,
            "raw": matched,
        }

    def get_device_row_by_macid(self, macid: str) -> Optional[dict]:
        """与 Gps18Api::findDeviceByMacidInList + getDeviceListByCustomIdNormalized"""
        devices = self.get_device_list()
        return find_device_by_macid_in_list(macid, devices)

    @staticmethod
    def _parse_device_ui(dev: dict) -> dict:
        u = dev.get("ui")
        if isinstance(u, dict):
            return u
        if isinstance(u, str) and u.strip().startswith("{"):
            try:
                return json.loads(u)
            except Exception:
                return {}
        return {}

    def build_realtime_sxw_payload(self, macid: str) -> Optional[dict]:
        """与 smart_logistics_bind/ajax.php#get_realtime_data 单条 data[0] 结构一致（GCJ-02）。"""
        macid = normalize_beidou_macid(macid)
        if not macid:
            return None
        dev = self.get_device_row_by_macid(macid)
        if not dev:
            return None
        jg_raw = float(dev.get("jingdu") or 0)
        wd_raw = float(dev.get("weidu") or 0)
        gcj_lng, gcj_lat = _lng_lat_to_amap_gcj02(jg_raw, wd_raw, None)
        ui = self._parse_device_ui(dev)
        temp_str = (
            str(ui.get("bracket_temp") or "").strip()
            or str(ui.get("temperature") or "").strip()
        )
        humi_str = str(ui.get("humidity") or "").strip()
        temp_num = None
        if temp_str:
            m = re.search(r"([\d.]+)", temp_str)
            if m:
                temp_num = float(m.group(1))
        humi_num = None
        if humi_str:
            mh = re.search(r"([\d.]+)", humi_str)
            if mh:
                humi_num = float(mh.group(1))
        su = dev.get("su", "")
        dt = dev.get("datetime") or dev.get("gpstime") or dev.get("time") or ""
        dt_show = _format_sxw_display_time(dt) or str(dt)
        volt = ui.get("voltage_v")
        power = f"{volt}V" if volt is not None and str(volt).strip() != "" else "--"
        return {
            "deviceName": "北斗 · " + macid,
            "device_name": "北斗 · " + macid,
            "longitude": str(round(gcj_lng, 6)),
            "latitude": str(round(gcj_lat, 6)),
            "temperature": str(temp_num) if temp_num is not None else temp_str,
            "humidity": str(humi_num) if humi_num is not None else humi_str,
            "hum1": str(humi_num) if humi_num is not None else "",
            "tmp1": str(temp_num) if temp_num is not None else "",
            "speed": str(su) if su is not None else "",
            "signalStrength": "--",
            "power": power,
            "lastSessionTime": dt_show,
            "lastDataTime": dt_show,
            "address": "--",
            "position": f"{round(gcj_lng, 6)},{round(gcj_lat, 6)}",
        }

    def _map_type_for_history(self) -> str:
        """与 Gps18Api::mapTypeForHistory"""
        h = os.getenv("GPS18_HISTORY_MAP_TYPE", "").strip()
        if h:
            return h
        return os.getenv("GPS18_MAP_TYPE", "").strip()

    def _history_play_lbs(self) -> str:
        return "true" if os.getenv("GPS18_HISTORY_PLAY_LBS", "0") == "1" else "false"

    @staticmethod
    def _normalize_ms_pair(from_ms: int, to_ms: int) -> tuple:
        """与 PHP：误传 Unix 秒时转为毫秒"""
        if from_ms > 0 and to_ms > 0 and max(from_ms, to_ms) < 20000000000:
            from_ms = int(round(from_ms * 1000))
            to_ms = int(round(to_ms * 1000))
        return from_ms, to_ms

    def _preferred_macid_for_history_new(self, macid_norm: str) -> str:
        """
        getHistoryMByMUtcNew 按平台侧 sim_id/user_name 精确匹配；
        绑定表常为 16031004066，而列表为 016031004066，仅数字等价仍会报「设备号不存在」。
        """
        if not macid_norm:
            return macid_norm
        try:
            dev = self.get_device_row_by_macid(macid_norm)
        except Exception:
            return macid_norm
        if not dev:
            return macid_norm
        for key in ("sim_id", "sim", "macid", "user_name"):
            cand = dev.get(key)
            if cand is None:
                continue
            s = str(cand).strip()
            if not s:
                continue
            if _beidou_device_ids_equal(macid_norm, s):
                return s
        return macid_norm

    def _history_normalized_internal(self, params: dict) -> dict:
        """与 Gps18Api::getHistoryNormalizedInternal，含 mapType 互斥重试"""
        base = dict(params)
        map_used = (base.get("mapType") or "").strip()
        data = self._getdate(base)
        if not data.get("success") in (True, "true"):
            return {
                "points": [],
                "error": str(data.get("errorDescribe") or data),
                "raw": data,
                "map_type_used": map_used,
            }
        raw = _extract_history_data_string(data)
        if raw:
            return {
                "points": _parse_history_points(raw, map_used or None),
                "map_type_used": map_used,
            }
        alt = _alternate_history_map_type(map_used)
        if alt is not None:
            p2 = dict(params)
            p2["mapType"] = alt
            data2 = self._getdate(p2)
            if data2.get("success") in (True, "true"):
                raw2 = _extract_history_data_string(data2)
                if raw2:
                    return {
                        "points": _parse_history_points(raw2, alt or None),
                        "map_type_used": alt,
                    }
        return {"points": [], "map_type_used": map_used}

    def _history_new_normalized(self, macid: str, from_ms: int, to_ms: int) -> dict:
        macid = normalize_beidou_macid(macid)
        if not macid:
            return {"points": [], "error": "macid 为空"}
        from_ms, to_ms = self._normalize_ms_pair(from_ms, to_ms)
        if to_ms <= from_ms:
            return {"points": [], "error": "结束时间须大于开始时间"}
        method = os.getenv("GPS18_HISTORY_METHOD", "").strip() or "getHistoryMByMUtcNew"
        macid_for_api = self._preferred_macid_for_history_new(macid)
        return self._history_normalized_internal({
            "method": method,
            "macid": macid_for_api,
            "mapType": self._map_type_for_history(),
            "from": str(int(from_ms)),
            "to": str(int(to_ms)),
            "playLBS": self._history_play_lbs(),
        })

    def _history_by_user_normalized(self, user_id: str, from_ms: int, to_ms: int) -> dict:
        user_id = (user_id or "").strip()
        if not user_id:
            return {"points": [], "error": "user_id 为空"}
        from_ms, to_ms = self._normalize_ms_pair(from_ms, to_ms)
        if to_ms <= from_ms:
            return {"points": [], "error": "结束时间须大于开始时间"}
        method = os.getenv("GPS18_HISTORY_METHOD_USER", "").strip() or "getHistoryMByMUtc"
        return self._history_normalized_internal({
            "method": method,
            "userID": user_id,
            "mapType": self._map_type_for_history(),
            "from": str(int(from_ms)),
            "to": str(int(to_ms)),
            "playLBS": self._history_play_lbs(),
        })

    def fetch_history_track_ms(
        self,
        macid_api: str,
        uid_bound: str,
        from_ms: int,
        to_ms: int,
    ) -> list:
        """
        与 smart_logistics_bind/ajax.php#get_history_track 一致：macid → user_id → 批量列表反查 userID。
        """
        macid_api = normalize_beidou_macid(macid_api)
        uid_bound = (uid_bound or "").strip()
        norm = None
        if macid_api:
            norm = self._history_new_normalized(macid_api, from_ms, to_ms)
        if _history_norm_empty(norm) and uid_bound:
            norm = self._history_by_user_normalized(uid_bound, from_ms, to_ms)
        if _history_norm_empty(norm) and macid_api:
            try:
                devices = self.get_device_list()
            except Exception:
                devices = []
            if devices:
                dev = find_device_by_macid_in_list(macid_api, devices)
                if dev:
                    uid_list = beidou_row_user_id(dev)
                    if uid_list and (not uid_bound or uid_list != uid_bound):
                        norm = self._history_by_user_normalized(uid_list, from_ms, to_ms)
        if _history_norm_empty(norm):
            return []
        return _coerce_history_points_list(norm.get("points"))

    def get_history_track_ms(
        self, imei: str, from_ms: int, to_ms: int, bind_user_id: Optional[str] = None
    ) -> list:
        """单段 UTC 毫秒区间；bind_user_id 为绑定表 sl_vehicle_bind_beidou.user_id 时可触发与 SXW 一致回退链。"""
        return self.fetch_history_track_ms(imei, bind_user_id or "", from_ms, to_ms)

    def get_history_track(self, imei: str, start_time: str, end_time: str) -> list:
        """历史轨迹，start/end_time 为北京时间 YYYY-MM-DD HH:MM:SS（Asia/Shanghai）。"""
        fmt = "%Y-%m-%d %H:%M:%S"
        tz = ZoneInfo(os.getenv("GPS18_HISTORY_TZ", "Asia/Shanghai"))
        st = datetime.strptime(start_time, fmt).replace(tzinfo=tz)
        et = datetime.strptime(end_time, fmt).replace(tzinfo=tz)
        from_ms = int(st.timestamp() * 1000)
        to_ms = int(et.timestamp() * 1000)
        return self.get_history_track_ms(imei, from_ms, to_ms, None)
