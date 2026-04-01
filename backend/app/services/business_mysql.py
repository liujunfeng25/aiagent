from dataclasses import dataclass
from typing import Optional

from app.database import SessionLocal
from app.models import DataSource
from app.services.db_connector import decode_password
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
    source: str  # "env" | "datasource"


def resolve_business_mysql() -> Optional[BusinessMysqlConfig]:
    if INSIGHTS_MYSQL_HOST:
        return BusinessMysqlConfig(
            host=INSIGHTS_MYSQL_HOST,
            port=INSIGHTS_MYSQL_PORT,
            database=INSIGHTS_MYSQL_DATABASE or "agent",
            user=INSIGHTS_MYSQL_USER,
            password=INSIGHTS_MYSQL_PASSWORD or "",
            source="env",
        )
    db = SessionLocal()
    try:
        ds = db.query(DataSource).filter(DataSource.type == "mysql").order_by(DataSource.id.asc()).first()
        if not ds:
            return None
        pwd = decode_password(ds.password_encrypted or "")
        return BusinessMysqlConfig(
            host=ds.host,
            port=int(ds.port or 3306),
            database=ds.database,
            user=ds.username,
            password=pwd,
            source="datasource",
        )
    finally:
        db.close()
