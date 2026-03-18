# 操作日志（时间统一为北京时间 UTC+8）
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import LOGS_DIR

LOG_FILE = LOGS_DIR / "operation_log.json"
MAX_ENTRIES = 500
_BEIJING = timezone(timedelta(hours=8))


def _now_iso():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return datetime.now(_BEIJING).strftime("%Y-%m-%dT%H:%M:%S")


def add_log(action: str, detail: str):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"time": _now_iso(), "action": action, "detail": detail}
    try:
        if LOG_FILE.exists():
            data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        else:
            data = []
        data.insert(0, entry)
        data = data[:MAX_ENTRIES]
        LOG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_logs(limit: int = 100):
    if not LOG_FILE.exists():
        return []
    try:
        data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        return data[:limit]
    except Exception:
        return []
