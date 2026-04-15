import json
from datetime import datetime, timedelta, time
from typing import Any, Optional, Type

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Dataset, TrainTask, Model
from app.services.inference_stats import (
    get_image_recognition_today,
    get_image_recognition_yesterday,
)

router = APIRouter()


def _now_naive_shanghai() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    except Exception:
        from datetime import timezone

        return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)


def _week_over_week_new_pct(db: Session, entity: Type[Any], now: datetime) -> Optional[float]:
    """近 7 日新增条数 vs 前 7 日新增条数，环比百分比；两期均为 0 时返回 None（前端不展示假涨幅）。"""
    d7 = now - timedelta(days=7)
    d14 = now - timedelta(days=14)
    this_n = db.query(entity).filter(entity.created_at >= d7).count()
    prev_n = db.query(entity).filter(entity.created_at >= d14, entity.created_at < d7).count()
    if prev_n == 0:
        return None if this_n == 0 else 100.0
    return round((this_n - prev_n) / prev_n * 100, 1)


def _inference_dod_pct() -> Optional[float]:
    """今日识别次数 vs 昨日，日环比。"""
    t = get_image_recognition_today()
    y = get_image_recognition_yesterday()
    if y == 0:
        return None if t == 0 else 100.0
    return round((t - y) / y * 100, 1)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    now = _now_naive_shanghai()
    model_count = db.query(Model).count()
    dataset_count = db.query(Dataset).count()
    task_count = db.query(TrainTask).count()
    inference_today = get_image_recognition_today()
    return {
        "model_count": model_count,
        "dataset_count": dataset_count,
        "task_count": task_count,
        "inference_today": inference_today,
        "model_trend_pct": _week_over_week_new_pct(db, Model, now),
        "dataset_trend_pct": _week_over_week_new_pct(db, Dataset, now),
        "task_trend_pct": _week_over_week_new_pct(db, TrainTask, now),
        "inference_trend_pct": _inference_dod_pct(),
    }


def _beijing_tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Asia/Shanghai")
    except Exception:
        from datetime import timezone, timedelta
        return timezone(timedelta(hours=8))


@router.get("/train_trend")
def get_train_trend(db: Session = Depends(get_db)):
    tz = _beijing_tz()
    end_d = datetime.now(tz).date()
    start_d = end_d - timedelta(days=6)
    start_naive = datetime.combine(start_d, time.min)
    day_expr = func.strftime("%Y-%m-%d", TrainTask.created_at)
    rows = (
        db.query(day_expr.label("day"), func.count(TrainTask.id))
        .filter(TrainTask.created_at >= start_naive)
        .group_by(day_expr)
        .all()
    )
    count_by_day = {str(r[0]): r[1] for r in rows if r[0]}
    result = []
    for i in range(6, -1, -1):
        d = (end_d - timedelta(days=i)).strftime("%Y-%m-%d")
        result.append({"date": d, "count": count_by_day.get(d, 0)})
    return {"data": result}


@router.get("/top_models")
def get_top_models(db: Session = Depends(get_db)):
    models = db.query(Model).order_by(Model.created_at.desc()).limit(5).all()
    result = []
    for m in models:
        try:
            metrics = m.metrics_json and json.loads(m.metrics_json) or {}
            acc = metrics.get("val_acc", 0)
        except Exception:
            acc = 0
        result.append({"id": m.id, "name": m.name, "accuracy": acc})
    return {"data": result}


@router.get("/recent_tasks")
def get_recent_tasks(db: Session = Depends(get_db)):
    tasks = db.query(TrainTask).order_by(TrainTask.created_at.desc()).limit(5).all()
    return {"data": [{"id": t.id, "status": t.status, "created_at": t.created_at.isoformat() if t.created_at else None} for t in tasks]}
