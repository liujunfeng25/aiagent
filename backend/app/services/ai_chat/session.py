"""多轮会话历史（内存 TTLCache）。

- key：前端生成的 session_id（uuid）
- value：list[dict]，每项形如 {"role": "user"|"assistant", "content": str}
- 前端每次请求也会带完整 messages；服务端内存仅做兜底，重启即清空。
"""

from __future__ import annotations

from typing import Any

try:
    from cachetools import TTLCache  # type: ignore
except Exception:  # pragma: no cover - 未装依赖时简单 dict
    class TTLCache(dict):  # type: ignore
        def __init__(self, maxsize: int, ttl: int):
            super().__init__()


_HISTORY: "TTLCache[str, list[dict[str, Any]]]" = TTLCache(maxsize=2048, ttl=2 * 60 * 60)

# 最近 N 轮（一轮 = user + assistant 两条）
MAX_TURNS = 10


def get_history(session_id: str) -> list[dict[str, Any]]:
    if not session_id:
        return []
    return list(_HISTORY.get(session_id, []) or [])


def set_history(session_id: str, messages: list[dict[str, Any]]) -> None:
    if not session_id:
        return
    _HISTORY[session_id] = _trim(messages)


def append(session_id: str, role: str, content: str) -> None:
    if not session_id:
        return
    arr = list(_HISTORY.get(session_id, []) or [])
    arr.append({"role": role, "content": content})
    _HISTORY[session_id] = _trim(arr)


def _trim(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """保留最近 MAX_TURNS 轮 user/assistant（system 不入缓存）。"""
    filtered = [m for m in messages if m.get("role") in ("user", "assistant")]
    keep = MAX_TURNS * 2
    return filtered[-keep:]
