"""业务日口径：与 insights_business 一致，统一使用 Asia/Shanghai 的日历日。

避免 Docker/服务器默认 UTC 时 `date.today()` 比国内「今天」晚一天的问题。
"""

from __future__ import annotations

from datetime import date, datetime

from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Asia/Shanghai")


def business_today() -> date:
    """当前业务「今天」对应的日期（上海时区）。"""
    return datetime.now(_TZ).date()
