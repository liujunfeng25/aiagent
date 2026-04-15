"""
京津冀送货场景地理编码（与智能排线 `governance_demo.smart_split_geocode` 同源逻辑）。
坐标须落在京津冀外包矩形内；雄安短地址有专用查询序列。
"""
from __future__ import annotations

from typing import Optional

from app.services.amap_geocode import geocode_address

# 智能排线：历史数据多为京内简写地址，默认按北京限定。
_DEFAULT_ROUTE_AMAP_CITY = "北京"


def delivery_route_geocode_city_hint(addr: str) -> Optional[str]:
    """
    智能排线：按地址前缀选用高德 city 参数。
    - 雄安新区常见「雄安新区…」无前缀「河北」→ 不按北京限定，传 None 全国检索
    - 天津 → 「天津」
    - 河北 / 雄安关键字 → 不传 city
    - 北京 → 「北京」
    - 其余默认「北京」（历史数据多为京内简写地址）
    返回 None 表示 geocode 请求不传 city。
    """
    s = (addr or "").strip()
    if not s:
        return _DEFAULT_ROUTE_AMAP_CITY
    head = s[:36]
    if s.startswith("雄安") or head.startswith("雄安新区"):
        return None
    if s.startswith("天津") or head.startswith("天津市"):
        return "天津"
    if s.startswith("河北") or "河北" in head[:20] or "雄安" in head[:28]:
        return None
    if s.startswith("北京") or head.startswith("北京市"):
        return "北京"
    return _DEFAULT_ROUTE_AMAP_CITY


# 智能排线：坐标须在京津冀外包矩形内，避免误解析到外省仍被采用
_JJJ_LNG_MIN, _JJJ_LNG_MAX = 113.2, 120.6
_JJJ_LAT_MIN, _JJJ_LAT_MAX = 35.5, 43.2


def coord_in_jjj_metro(lng: float, lat: float) -> bool:
    return _JJJ_LNG_MIN <= lng <= _JJJ_LNG_MAX and _JJJ_LAT_MIN <= lat <= _JJJ_LAT_MAX


def _coord_in_xiongan_core(lng: float, lat: float) -> bool:
    """雄安新区—容城、雄县、安新一带，用于过滤冀西晋西同名误匹配。"""
    return 115.55 <= lng <= 116.65 and 38.78 <= lat <= 39.48


def _addr_suggests_xiongan(addr: str) -> bool:
    s = (addr or "").strip()
    if not s:
        return False
    head = s[:56]
    if s.startswith("雄安") or head.startswith("雄安新区"):
        return True
    if "雄安" in head:
        return True
    for k in ("容东", "容西", "容城", "安新", "雄县"):
        if k in head[:36]:
            return True
    return False


def _xiongan_geocode_text_sequence(addr: str) -> list[str]:
    """短地址优先补全省—市—县，减少全国检索命中同名异地（如平山）。"""
    s = (addr or "").strip()
    if not s:
        return []
    base = s
    if base.endswith("学生") and len(base) > 8:
        base = base[:-2].strip()
    rest = base
    for p in ("雄安新区", "雄安"):
        if rest.startswith(p):
            rest = rest[len(p) :].strip(" ··-\t，,")
            break
    if not rest:
        rest = base
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        t = x.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)

    if rest and rest != base:
        add(f"河北省保定市容城县{rest}")
        add(f"保定市容城县{rest}")
        add(f"河北省雄安新区{rest}")
    add(f"河北省保定市容城县{base}")
    add(f"保定市容城县{base}")
    add(f"河北省雄安新区{base}")
    add(base)
    add(f"河北省{base}")
    if rest != base:
        add(rest)
        add(f"河北省{rest}")
    return out


def geocode_single_for_delivery_route(addr: str) -> Optional[tuple[float, float]]:
    """
    京津冀送货：地理编码结果须落在京津冀范围内。
    含雄安关键字的短地址优先尝试「容城县 /雄安新区」等完整表述，并优先采用雄安核心范围内的坐标。
    """
    raw = (addr or "").strip()
    if not raw:
        return None

    pairs: list[tuple[str, Optional[str]]] = []
    seen_pairs: set[tuple[str, str]] = set()

    def add_pair(text: str, cty: Optional[str]) -> None:
        t = (text or "").strip()
        if not t:
            return
        k = (t, cty or "")
        if k in seen_pairs:
            return
        seen_pairs.add(k)
        pairs.append((t, cty))

    if _addr_suggests_xiongan(raw):
        for text in _xiongan_geocode_text_sequence(raw):
            add_pair(text, delivery_route_geocode_city_hint(text))

    add_pair(raw, delivery_route_geocode_city_hint(raw))
    if raw.startswith("雄安") and not raw.startswith("河北"):
        add_pair(f"河北省{raw}", None)
    elif (
        ("雄安" in raw[:40] or "容东" in raw[:24] or "容西" in raw[:24])
        and not raw.startswith("河北")
    ):
        add_pair(f"河北省{raw}", None)

    candidates: list[tuple[float, float]] = []
    for text, cty in pairs:
        c = geocode_address(text, city=cty)
        if not c:
            continue
        lng, lat = float(c[0]), float(c[1])
        if not coord_in_jjj_metro(lng, lat):
            continue
        candidates.append((lng, lat))
        if _addr_suggests_xiongan(raw) and _coord_in_xiongan_core(lng, lat):
            return (lng, lat)

    if not candidates:
        return None
    if not _addr_suggests_xiongan(raw):
        return candidates[0]

    for lng, lat in candidates:
        if lng >= 115.15 and lat >= 38.65:
            return (lng, lat)
    return candidates[0]
