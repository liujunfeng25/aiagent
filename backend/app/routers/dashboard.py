import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Dataset, TrainTask, Model

router = APIRouter()


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    model_count = db.query(Model).count()
    dataset_count = db.query(Dataset).count()
    task_count = db.query(TrainTask).count()
    return {
        "model_count": model_count,
        "dataset_count": dataset_count,
        "task_count": task_count,
        "inference_today": 0,
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
    from datetime import datetime, timedelta
    tz = _beijing_tz()
    result = []
    for i in range(6, -1, -1):
        d = (datetime.now(tz) - timedelta(days=i)).strftime("%Y-%m-%d")
        tasks = db.query(TrainTask).all()
        count = sum(1 for t in tasks if t.created_at and str(t.created_at)[:10] == d)
        result.append({"date": d, "count": count})
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
