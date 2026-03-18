import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from config import MODELS_DIR
from app.database import get_db
from app.models import TrainTask, Dataset, Model
from app.services.train_runner import start_train, get_status, cancel_task, is_running
from app.services.operation_log import add_log
from app.routers.models import ensure_model_from_task

router = APIRouter()

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _dataset_snapshot(local_path: str) -> dict:
    """返回数据集当前类别名列表与总图片数，用于训练快照。"""
    path = Path(local_path)
    if not path.is_dir():
        return {"categories": [], "total_images": 0}
    dirs = [d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")]
    categories = sorted(d.name for d in dirs)
    total = 0
    for d in dirs:
        total += len([f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS])
    return {"categories": categories, "total_images": total}


class TrainTaskCreate(BaseModel):
    dataset_id: int
    epochs: int = 10
    batch_size: int = 16
    model_type: str = "mobilenet_v2"


@router.get("/dataset/{dataset_id}/since-last")
def dataset_since_last(dataset_id: int, db: Session = Depends(get_db)):
    """返回该数据集自上次训练以来的新增类别数、新增图片数；用于训练页提示。"""
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds or not ds.local_path or not Path(ds.local_path).exists():
        return {"last_trained_at": None, "new_categories": 0, "new_images": 0, "new_category_names": [], "message": "数据集不存在或路径无效"}
    current = _dataset_snapshot(ds.local_path)
    # 该数据集当前对应的模型所关联的任务 = 上次训练
    last_task = (
        db.query(TrainTask)
        .join(Model, Model.task_id == TrainTask.id)
        .join(Dataset, Dataset.id == TrainTask.dataset_id)
        .filter(TrainTask.dataset_id == dataset_id, TrainTask.status == "done")
        .order_by(TrainTask.id.desc())
        .first()
    )
    if not last_task or not last_task.params_json:
        return {
            "last_trained_at": None,
            "new_categories": len(current["categories"]),
            "new_images": current["total_images"],
            "new_category_names": current["categories"],
            "message": "尚未训练过",
        }
    try:
        params = json.loads(last_task.params_json)
        snapshot = params.get("snapshot") or {}
    except Exception:
        snapshot = {}
    snap_cats = set(snapshot.get("categories") or [])
    snap_total = snapshot.get("total_images") or 0
    cur_cats = set(current["categories"])
    cur_total = current["total_images"]
    new_category_names = sorted(cur_cats - snap_cats)
    new_categories = len(new_category_names)
    new_images = max(0, cur_total - snap_total)
    return {
        "last_trained_at": last_task.created_at.isoformat() if last_task.created_at else None,
        "new_categories": new_categories,
        "new_images": new_images,
        "new_category_names": new_category_names,
        "message": None,
    }


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(TrainTask).order_by(TrainTask.created_at.desc()).all()
    result = []
    for t in tasks:
        ds = db.query(Dataset).filter(Dataset.id == t.dataset_id).first()
        ds_name = ds.name if ds else "-"
        result.append({
            "id": t.id,
            "dataset_id": t.dataset_id,
            "dataset_name": ds_name,
            "status": t.status,
            "params_json": t.params_json,
            "metrics_json": t.metrics_json,
            "model_path": t.model_path,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return {"data": result}


@router.post("/tasks")
def create_task(body: TrainTaskCreate, db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == body.dataset_id).first()
    if not ds:
        raise HTTPException(404, "数据集不存在")
    if not ds.local_path or not Path(ds.local_path).exists():
        raise HTTPException(400, "数据集路径无效，请确保已上传数据")
    path = Path(ds.local_path)
    if not path.is_dir():
        raise HTTPException(400, "数据集路径不是有效目录")
    # 检查该数据集下是否有至少 2 个类别（子文件夹即类别）
    dirs = [d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")]
    n = len(dirs)
    if n < 2:
        raise HTTPException(400, f"该数据集下至少需要 2 个类别（当前 {n} 个）")
    snapshot = _dataset_snapshot(ds.local_path)
    params = {"epochs": body.epochs, "batch_size": body.batch_size, "model_type": body.model_type, "snapshot": snapshot}
    task = TrainTask(
        dataset_id=body.dataset_id,
        status="pending",
        params_json=json.dumps(params),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    ok = start_train(task.id, ds.local_path, epochs=body.epochs, batch_size=body.batch_size)
    if ok:
        task.status = "running"
    else:
        task.status = "error"
    db.commit()
    add_log("create_train_task", f"创建训练任务 #{task.id}，数据集：{ds.name}")
    return {"id": task.id, "status": task.status, "message": "任务已创建"}


@router.get("/tasks/{id}/status")
def task_status(id: int, db: Session = Depends(get_db)):
    task = db.query(TrainTask).filter(TrainTask.id == id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    status = get_status(id)
    if status.get("status") == "done":
        task.status = "done"
        try:
            metrics = status
            task.metrics_json = json.dumps({"val_acc": metrics.get("val_acc", 0), "loss": metrics.get("loss", 0)})
            model_dir = MODELS_DIR / str(id)
            model_path = model_dir / "model.pt"
            if model_path.exists():
                task.model_path = str(model_path)
            db.commit()
            ensure_model_from_task(id, db)
        except Exception:
            pass
    elif status.get("status") == "error":
        task.status = "error"
        db.commit()
    return status


@router.delete("/tasks/{id}")
def delete_task(id: int, db: Session = Depends(get_db)):
    task = db.query(TrainTask).filter(TrainTask.id == id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    if is_running(id):
        cancel_task(id)
    db.delete(task)
    db.commit()
    add_log("delete_train_task", f"删除训练任务 #{id}")
    return {"message": "已删除"}
