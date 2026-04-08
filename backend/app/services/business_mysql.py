from dataclasses import dataclass
from typing import Optional

from config import (
    INSIGHTS_MYSQL_DATABASE,
    INSIGHTS_MYSQL_HOST,
    INSIGHTS_MYSQL_PASSWORD,
    INSIGHTS_MYSQL_PORT,
    INSIGHTS_MYSQL_USER,
)


@dataclass(frozen=True)
class BusinessMysqlConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    source: str  # 固定为 env（业务洞察库仅支持环境变量 INSIGHTS_MYSQL_*）


def resolve_business_mysql() -> Optional[BusinessMysqlConfig]:
    if not INSIGHTS_MYSQL_HOST:
        return None
    return BusinessMysqlConfig(
        host=INSIGHTS_MYSQL_HOST,
        port=INSIGHTS_MYSQL_PORT,
        database=INSIGHTS_MYSQL_DATABASE or "agent",
        user=INSIGHTS_MYSQL_USER,
        password=INSIGHTS_MYSQL_PASSWORD or "",
        source="env",
    )
