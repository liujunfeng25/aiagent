from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import DataSource
from app.services.db_connector import test_connection, list_tables, decode_password, encode_password
from app.services.operation_log import add_log

router = APIRouter()


class DataSourceCreate(BaseModel):
    name: str
    type: str = "mysql"
    host: str
    port: int = 3306
    database: str
    username: str
    password: str


class DataSourceUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None


@router.get("/")
def list_datasources(db: Session = Depends(get_db)):
    items = db.query(DataSource).all()
    return {"data": [{"id": d.id, "name": d.name, "type": d.type, "host": d.host, "database": d.database} for d in items]}


@router.post("/")
def create_datasource(body: DataSourceCreate, db: Session = Depends(get_db)):
    enc = encode_password(body.password)
    ds = DataSource(
        name=body.name,
        type=body.type,
        host=body.host,
        port=body.port,
        database=body.database,
        username=body.username,
        password_encrypted=enc,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    add_log("create_datasource", f"新增数据源：{body.name}")
    return {"id": ds.id, "message": "创建成功"}


@router.put("/{id}")
def update_datasource(id: int, body: DataSourceUpdate, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == id).first()
    if not ds:
        raise HTTPException(404, "数据源不存在")
    if body.name is not None:
        ds.name = body.name
    if body.host is not None:
        ds.host = body.host
    if body.port is not None:
        ds.port = body.port
    if body.database is not None:
        ds.database = body.database
    if body.username is not None:
        ds.username = body.username
    if body.password and body.password.strip():
        ds.password_encrypted = encode_password(body.password)
    db.commit()
    add_log("update_datasource", f"更新数据源：{ds.name}")
    return {"message": "更新成功"}


@router.delete("/{id}")
def delete_datasource(id: int, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == id).first()
    if not ds:
        raise HTTPException(404, "数据源不存在")
    db.delete(ds)
    db.commit()
    add_log("delete_datasource", f"删除数据源：{ds.name}")
    return {"message": "删除成功"}


@router.post("/{id}/test")
def test_datasource(id: int, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == id).first()
    if not ds:
        raise HTTPException(404, "数据源不存在")
    pwd = decode_password(ds.password_encrypted)
    ok, msg = test_connection(ds.host, ds.port, ds.database, ds.username, pwd)
    return {"success": ok, "message": msg}


@router.get("/{id}/tables")
def get_tables(id: int, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == id).first()
    if not ds:
        raise HTTPException(404, "数据源不存在")
    pwd = decode_password(ds.password_encrypted)
    try:
        tables = list_tables(ds.host, ds.port, ds.database, ds.username, pwd)
        return {"data": tables}
    except Exception as e:
        raise HTTPException(500, str(e))
