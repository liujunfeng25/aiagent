from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.business_mysql import resolve_business_mysql
from app.services.db_connector import execute_query

router = APIRouter()


class QueryRequest(BaseModel):
    sql: str


@router.post("/query")
def run_query(body: QueryRequest):
    """对业务库执行只读 SELECT（与数据洞察同源：环境变量 INSIGHTS_MYSQL_*）。"""
    cfg = resolve_business_mysql()
    if not cfg:
        raise HTTPException(
            503,
            "未配置业务库：请设置 INSIGHTS_MYSQL_HOST（及 PORT/USER/PASSWORD/DATABASE）。",
        )
    sql = body.sql.strip()
    if not sql.lower().startswith("select"):
        raise HTTPException(400, "仅支持 SELECT 查询")
    try:
        rows, columns = execute_query(
            cfg.host, cfg.port, cfg.database, cfg.user, cfg.password, sql
        )
        return {"columns": columns, "rows": rows}
    except Exception as e:
        raise HTTPException(500, str(e)) from e
