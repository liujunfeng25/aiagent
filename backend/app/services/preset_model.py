# 预置模型注册（vegetable-recognition 集成）
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from config import PRESET_VEGETABLE_MODEL_DIR, CATEGORIES_DIR
from app.database import SessionLocal
from app.models import Dataset, TrainTask, Model


def get_or_create_preset_dataset(db: Session) -> Dataset:
    """预置蔬菜数据指向 CATEGORIES_DIR，与类别管理中的土豆、白菜等一致，便于训练与识别。"""
    name = "预置蔬菜数据"
    ds = db.query(Dataset).filter(Dataset.name == name).first()
    if ds:
        ds.local_path = str(CATEGORIES_DIR.resolve())
        db.commit()
        db.refresh(ds)
        return ds
    ds = Dataset(name=name, source_type="upload", row_count=0, local_path=str(CATEGORIES_DIR.resolve()))
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def register_preset_vegetable_model_if_exists(db: Session | None = None):
    """若 preset_vegetable_model/model.pt 存在且尚未注册，则创建 Dataset、TrainTask、Model 并设为已部署。"""
    model_path = PRESET_VEGETABLE_MODEL_DIR / "model.pt"
    if not model_path.exists():
        return
    path_str = str(model_path.resolve())
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        existing = db.query(Model).filter(Model.path == path_str).first()
        if existing:
            return
        ds = get_or_create_preset_dataset(db)
        task = TrainTask(
            dataset_id=ds.id,
            status="done",
            params_json='{"epochs": 0, "preset": true}',
            metrics_json='{"val_acc": 0}',
            model_path=path_str,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        model = Model(
            task_id=task.id,
            name="蔬菜识别预置模型",
            path=path_str,
            deployed=True,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        for m in db.query(Model).filter(Model.deployed == True).all():
            if m.id != model.id:
                m.deployed = False
        db.commit()
    finally:
        if own_db:
            db.close()
