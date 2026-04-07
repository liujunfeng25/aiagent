from typing import Generator, Optional

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_sxw_sessionmaker
from config import SXW_MYSQL_HOST, SXW_MYSQL_PORT, resolve_sxw_mysql_database


def sxw_supp_code_dep(
    x_supp_code: Optional[str] = Header(default=None, alias="X-Supp-Code"),
    supp_code: Optional[str] = Query(default=None),
) -> Optional[str]:
    v = (x_supp_code or supp_code or "").strip()
    return v if v else None


def get_sxw_db(
    supp_key: Optional[str] = Depends(sxw_supp_code_dep),
) -> Generator[Session, None, None]:
    db_name = resolve_sxw_mysql_database(supp_key)
    SessionLocal = get_sxw_sessionmaker(db_name)
    db = SessionLocal()
    try:
        yield db
    except (OperationalError, SQLAlchemyError) as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"业务库暂时不可用（{SXW_MYSQL_HOST}:{SXW_MYSQL_PORT}/{db_name}）：{exc.orig or exc}。"
                "请确认 SXW MySQL 服务正常，或检查防火墙/网络是否放行。"
            ),
        ) from exc
    finally:
        db.close()
