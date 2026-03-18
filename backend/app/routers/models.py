import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db


class RenameBody(BaseModel):
    name: str
from app.models import Dataset, Model, TrainTask
from app.services.operation_log import add_log

router = APIRouter()


@router.get("/")
def list_models(db: Session = Depends(get_db)):
    items = db.query(Model).order_by(Model.created_at.desc()).all()
    result = []
    for m in items:
        task = db.query(TrainTask).filter(TrainTask.id == m.task_id).first()
        metrics = {}
        if m.metrics_json:
            try:
                metrics = json.loads(m.metrics_json)
            except Exception:
                pass
        result.append({
            "id": m.id,
            "task_id": m.task_id,
            "name": m.name,
            "val_acc": metrics.get("val_acc", 0),
            "path": m.path,
            "deployed": m.deployed,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return {"data": result}


@router.get("/{id}")
def get_model(id: int, db: Session = Depends(get_db)):
    m = db.query(Model).filter(Model.id == id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    metrics = {}
    if m.metrics_json:
        try:
            metrics = json.loads(m.metrics_json)
        except Exception:
            pass
    return {
        "id": m.id,
        "task_id": m.task_id,
        "name": m.name,
        "metrics_json": m.metrics_json,
        "path": m.path,
        "deployed": m.deployed,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.patch("/{id}")
def rename_model(id: int, body: RenameBody, db: Session = Depends(get_db)):
    """重命名模型"""
    m = db.query(Model).filter(Model.id == id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    if len(name) > 200:
        raise HTTPException(400, "名称过长")
    m.name = name
    db.commit()
    add_log("rename_model", f"重命名模型 #{id} 为：{name}")
    return {"message": "已修改", "name": name}


@router.post("/{id}/deploy")
def deploy_model(id: int, db: Session = Depends(get_db)):
    m = db.query(Model).filter(Model.id == id).first()
    if not m:
        raise HTTPException(404, "模型不存在")
    # 取消其他已部署
    db.query(Model).filter(Model.deployed == True).update({"deployed": False})
    m.deployed = True
    db.commit()
    add_log("deploy_model", f"部署模型：{m.name}")
    return {"message": "部署成功"}


def ensure_model_from_task(task_id: int, db: Session):
    """训练完成后调用。同一数据集只保留一个模型：若该数据集已有模型则更新为本次任务，否则新建。"""
    task = db.query(TrainTask).filter(TrainTask.id == task_id, TrainTask.status == "done").first()
    if not task or not task.model_path:
        return
    ds = db.query(Dataset).filter(Dataset.id == task.dataset_id).first()
    model_name = f"{ds.name}模型" if ds and ds.name else f"模型-{task_id}"
    # 该数据集是否已有模型（通过 task_id -> TrainTask.dataset_id 关联）
    existing = (
        db.query(Model)
        .join(TrainTask, Model.task_id == TrainTask.id)
        .filter(TrainTask.dataset_id == task.dataset_id)
        .first()
    )
    if existing:
        existing.task_id = task_id
        existing.path = task.model_path
        existing.metrics_json = task.metrics_json
        existing.name = model_name
        db.commit()
        return
    m = Model(
        task_id=task_id,
        name=model_name,
        metrics_json=task.metrics_json,
        path=task.model_path,
    )
    db.add(m)
    db.commit()


def dedupe_models_by_dataset(db: Session) -> int:
    """按数据集去重：每个 dataset_id 只保留一个模型（优先保留已部署，否则保留 task_id 最大的），删除其余。返回删除条数。"""
    # 每个 dataset_id 下有哪些 model_id，以及是否 deployed、task_id
    subq = (
        db.query(Model.id, TrainTask.dataset_id, Model.deployed, Model.task_id)
        .join(TrainTask, Model.task_id == TrainTask.id)
        .all()
    )
    by_ds = {}
    for mid, ds_id, deployed, tid in subq:
        if ds_id not in by_ds:
            by_ds[ds_id] = []
        by_ds[ds_id].append((mid, deployed, tid))
    to_delete = []
    for ds_id, rows in by_ds.items():
        if len(rows) <= 1:
            continue
        # 优先保留已部署的，否则保留 task_id 最大的
        rows.sort(key=lambda x: (x[1], x[2]), reverse=True)  # deployed True first, then by task_id desc
        keep_id = rows[0][0]
        to_delete.extend(mid for mid, _, _ in rows[1:])
    for mid in to_delete:
        db.query(Model).filter(Model.id == mid).delete()
    if to_delete:
        db.commit()
    return len(to_delete)
