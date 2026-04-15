# 图像分类识别次数按日统计（供工作台展示，数据存 data/inference_daily.json）
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DATA_DIR

STATS_FILE = DATA_DIR / "inference_daily.json"
_LOCK = threading.Lock()
_MAX_DAYS_KEPT = 120


def _today_str() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")


def increment_image_recognition() -> None:
    """成功完成一次识别中心推理后调用。"""
    day = _today_str()
    with _LOCK:
        try:
            data = json.loads(STATS_FILE.read_text(encoding="utf-8")) if STATS_FILE.exists() else {}
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if day not in data or not isinstance(data.get(day), dict):
            data[day] = {"image_recognition": 0}
        data[day]["image_recognition"] = int(data[day].get("image_recognition") or 0) + 1
        keys = sorted(data.keys())
        if len(keys) > _MAX_DAYS_KEPT:
            for k in keys[: len(keys) - _MAX_DAYS_KEPT]:
                del data[k]
        try:
            STATS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def _read_daily_counts() -> dict:
    with _LOCK:
        try:
            data = json.loads(STATS_FILE.read_text(encoding="utf-8")) if STATS_FILE.exists() else {}
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}


def get_image_recognition_for_date(date_str: str) -> int:
    """指定日期（YYYY-MM-DD，东八区）的识别次数。"""
    entry = _read_daily_counts().get(date_str) or {}
    if isinstance(entry, dict):
        return int(entry.get("image_recognition") or 0)
    return 0


def get_image_recognition_yesterday() -> int:
    try:
        from zoneinfo import ZoneInfo

        d = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
    except Exception:
        d = datetime.now(timezone(timedelta(hours=8))).date() - timedelta(days=1)
    return get_image_recognition_for_date(d.strftime("%Y-%m-%d"))


def get_image_recognition_today() -> int:
    return get_image_recognition_for_date(_today_str())
