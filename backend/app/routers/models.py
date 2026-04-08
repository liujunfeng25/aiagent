from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Dataset, Model, TrainTask
from app.services.operation_log import add_log

router = APIRouter()


class RenameBody(BaseModel):
    name: str


def default_model_display_name(dataset_name: Optional[str], task_id: int) -> str:
    """训练完成写入 Model.name 的默认规则（与 ensure_model_from_task 一致）。"""
    if dataset_name:
        return f"{dataset_name}模型"
    return f"模型-{task_id}"


def _metrics_val_acc(metrics_json: Optional[str]) -> float:
    if not metrics_json:
        return 0.0
    try:
        metrics = json.loads(metrics_json)
        return float(metrics.get("val_acc", 0))
    except Exception:
        return 0.0


def _enriched_model_fields(m: Model, task: Optional[TrainTask], ds: Optional[Dataset]) -> dict:
    dataset_id = task.dataset_id if task else None
    dataset_name = ds.name if ds and ds.name else "-"
    default_name = default_model_display_name(ds.name if ds else None, m.task_id)
    name_is_custom = m.name != default_name
    return {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "task_id": m.task_id,
        "name_is_custom": name_is_custom,
    }


@router.post("/sync-display-names")
def sync_display_names(db: Session = Depends(get_db)):
    """将各模型显示名重置为「当前数据集名+模型」规则（覆盖自定义名称）。须放在 /{id} 之前注册。"""
    n = sync_model_display_names_from_datasets(db)
    return {"message": "已同步", "updated": n}


@router.get("/")
def list_models(db: Session = Depends(get_db)):
    rows = (
        db.query(Model, TrainTask, Dataset)
        .join(TrainTask, Model.task_id == TrainTask.id)
        .outerjoin(Dataset, TrainTask.dataset_id == Dataset.id)
        .order_by(Model.created_at.desc())
        .all()
    )
    result = []
    for m, task, ds in rows:
        meta = _enriched_model_fields(m, task, ds)
        result.append({
            "id": m.id,
            "name": m.name,
            "val_acc": _metrics_val_acc(m.metrics_json),
            "path": m.path,
            "deployed": m.deployed,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            **meta,
        })
    return {"data": result}


@router.get("/{id}")
def get_model(id: int, db: Session = Depends(get_db)):
    row = (
        db.query(Model, TrainTask, Dataset)
        .join(TrainTask, Model.task_id == TrainTask.id)
        .outerjoin(Dataset, TrainTask.dataset_id == Dataset.id)
        .filter(Model.id == id)
        .first()
    )
    if not row:
        raise HTTPException(404, "模型不存在")
    m, task, ds = row
    metrics = {}
    if m.metrics_json:
        try:
            metrics = json.loads(m.metrics_json)
        except Exception:
            pass
    meta = _enriched_model_fields(m, task, ds)
    return {
        "id": m.id,
        "name": m.name,
        "metrics_json": m.metrics_json,
        "val_acc": metrics.get("val_acc", 0),
        "path": m.path,
        "deployed": m.deployed,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        **meta,
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
    model_name = default_model_display_name(ds.name if ds else None, task_id)
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


def sync_model_display_names_from_datasets(db: Session) -> int:
    """按当前数据集名称批量重置 Model.name，返回实际修改条数。"""
    rows = (
        db.query(Model, TrainTask, Dataset)
        .join(TrainTask, Model.task_id == TrainTask.id)
        .outerjoin(Dataset, TrainTask.dataset_id == Dataset.id)
        .all()
    )
    updated = 0
    for m, _task, ds in rows:
        new_name = default_model_display_name(ds.name if ds else None, m.task_id)
        if m.name != new_name:
            m.name = new_name
            updated += 1
    if updated:
        db.commit()
        add_log("sync_model_display_names", f"按数据集同步模型显示名，更新 {updated} 条")
    return updated


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
