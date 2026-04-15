# 智能分单：供货方经营描述与商品名的品类契合度（启发式）
from __future__ import annotations

import re
from functools import lru_cache

# (子串, 标签) 按优先级靠后的规则可覆盖；同一文本可命中多标签
_TAG_RULES: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    (("豆芽", "银芽", "豆苗"), frozenset({"soy_sprout"})),
    (("猪肉", "牛肉", "羊肉", "鸡肉", "鸭肉", "鹅肉", "排骨", "里脊", "五花肉", "火腿", "培根", "腊肠", "肉", "禽"), frozenset({"meat"})),
    (("鱼", "虾", "蟹", "贝", "海鲜", "水产", "鱿", "带鱼", "海参", "鲍"), frozenset({"seafood"})),
    (("西瓜", "苹果", "香蕉", "橙", "梨", "葡萄", "草莓", "芒", "柚", "水果", "国产水果", "进口水果"), frozenset({"fruit"})),
    (("蛋", "鸡蛋", "鸭蛋", "鹌鹑蛋"), frozenset({"egg"})),
    (("米", "面", "粉", "挂面", "面粉", "大米", "小米"), frozenset({"grain"})),
    (("油", "花生", "菜籽", "橄榄", "芝麻"), frozenset({"oil"})),
    (("盐", "糖", "醋", "酱油", "味精", "调料", "香料", "花椒", "八角", "桂皮", "白芷", "胡椒", "孜然"), frozenset({"spice"})),
    (("奶", "乳", "芝士", "奶酪"), frozenset({"dairy"})),
    (("冻", "速冻", "冷鲜"), frozenset({"frozen"})),
    (("白菜", "萝卜", "土豆", "茄", "椒", "葱", "蒜", "姜", "菌", "菇", "笋", "芹菜", "菠菜", "生菜", "蔬菜", "叶菜", "冬瓜", "南瓜", "黄瓜", "番茄", "西红柿"), frozenset({"vegetable"})),
)

# (tag_a, tag_b,契合度上限) 无序；用于明显错配
_LOW_PAIRS: tuple[tuple[str, str, float], ...] = (
    ("meat", "fruit", 0.06),
    ("seafood", "fruit", 0.06),
    ("meat", "soy_sprout", 0.06),
    ("seafood", "soy_sprout", 0.08),
    ("fruit", "soy_sprout", 0.08),
    ("fruit", "spice", 0.12),
)


def _supplier_text_blob(realname: str) -> str:
    """取 realname 中更可能描述经营品类的片段（常见：…|品类）。"""
    s = (realname or "").strip()
    if not s:
        return ""
    parts = [p.strip() for p in re.split(r"\|", s) if p.strip()]
    if len(parts) >= 2:
        return " ".join(parts[1:])
    return s


@lru_cache(maxsize=4096)
def _tags_for_cached(norm: str) -> frozenset[str]:
    tags: set[str] = set()
    for keys, tset in _TAG_RULES:
        for k in keys:
            if k in norm:
                tags |= tset
                break
    return frozenset(tags)


def tags_for_text(text: str) -> frozenset[str]:
    norm = (text or "").strip()
    if not norm:
        return frozenset()
    return _tags_for_cached(norm)


def goods_supplier_fit(goods_name: str, supplier_realname: str) -> float:
    """
    返回 (0,1] 左右：高表示该供货方更适配送该商品。
    """
    g = (goods_name or "").strip() or "（未命名商品）"
    blob = _supplier_text_blob(supplier_realname)
    gtags = tags_for_text(g)
    stags = tags_for_text(blob) if blob else frozenset()
    if not stags:
        stags = tags_for_text(supplier_realname)

    for a, b, low in _LOW_PAIRS:
        if (a in gtags and b in stags) or (b in gtags and a in stags):
            return low

    inter = gtags & stags
    if inter:
        return min(1.0, 0.88 + 0.04 * len(inter))

    if not gtags and not stags:
        return 0.52
    if not gtags or not stags:
        return 0.4
    return 0.2


def fit_by_goods_for_supplier(
    supplier_realname: str, goods_names: list[str]
) -> dict[str, float]:
    return {g: round(goods_supplier_fit(g, supplier_realname), 4) for g in goods_names}
