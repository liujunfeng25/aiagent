from fastapi import APIRouter

from app.services.operation_log import get_logs

router = APIRouter()


@router.get("/logs")
def list_logs(limit: int = 100):
    return {"data": get_logs(limit=limit)}


@router.get("/config")
def get_config():
    return {"data": {"version": "1.0.0"}}
