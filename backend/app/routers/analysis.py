from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import DataSource
from app.services.db_connector import execute_query, decode_password

router = APIRouter()


class QueryRequest(BaseModel):
    data_source_id: int
    sql: str


@router.post("/query")
def run_query(body: QueryRequest, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == body.data_source_id).first()
    if not ds:
        raise HTTPException(404, "数据源不存在")
    sql = body.sql.strip()
    if not sql.lower().startswith("select"):
        raise HTTPException(400, "仅支持 SELECT 查询")
    pwd = decode_password(ds.password_encrypted)
    try:
        rows, columns = execute_query(ds.host, ds.port, ds.database, ds.username, pwd, sql)
        return {"columns": columns, "rows": rows}
    except Exception as e:
        raise HTTPException(500, str(e))
