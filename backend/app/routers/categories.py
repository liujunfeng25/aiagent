# 类别管理（vegetable-recognition 集成：新建类别、按类别上传图片、用类别数据训练）
import json
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import CATEGORIES_DIR
from app.database import get_db
from app.models import Dataset, TrainTask
from app.services.operation_log import add_log
from app.services.train_runner import start_train

router = APIRouter()

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"}


def _validate_name(name: str) -> None:
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="类别名不能为空")
    if re.search(r"[.\\/]", name):
        raise HTTPException(status_code=400, detail="类别名不能包含 . / \\")
    if name.strip() != name:
        raise HTTPException(status_code=400, detail="类别名不能含首尾空格")


def _get_categories() -> list[dict]:
    if not CATEGORIES_DIR.exists():
        return []
    return [
        {"name": d.name, "count": len([f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS])}
        for d in sorted(CATEGORIES_DIR.iterdir())
        if d.is_dir() and not d.name.startswith(".")
    ]


def _count_images(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for d in root.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            total += len([f for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS])
    return total


@router.get("/")
def list_categories():
    cats = _get_categories()
    total_images = _count_images(CATEGORIES_DIR)
    return {"categories": cats, "total_images": total_images}


@router.post("/")
def create_category(body: dict):
    name = (body.get("name") or "").strip()
    _validate_name(name)
    cat_path = CATEGORIES_DIR / name
    if cat_path.exists():
        raise HTTPException(status_code=409, detail="类别已存在")
    cat_path.mkdir(parents=True, exist_ok=True)
    add_log("create_category", f"新增类别：{name}")
    return {"message": "创建成功", "name": name}


@router.delete("/{name}")
def delete_category(name: str):
    _validate_name(name)
    cat_path = CATEGORIES_DIR / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(status_code=404, detail="类别不存在")
    add_log("delete_category", f"删除类别：{name}")
    shutil.rmtree(cat_path)
    return {"message": "删除成功"}


@router.get("/{name}/image/{filename}", include_in_schema=False)
def serve_category_image(name: str, filename: str):
    """供前端展示类别下的图片缩略图"""
    _validate_name(name)
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    cat_path = CATEGORIES_DIR / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(status_code=404, detail="类别不存在")
    img_path = cat_path / filename
    if not img_path.exists() or not img_path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(img_path)


@router.get("/{name}/images")
def list_images(name: str):
    _validate_name(name)
    cat_path = CATEGORIES_DIR / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(status_code=404, detail="类别不存在")
    files = [f.name for f in cat_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
    return {"images": sorted(files)}


@router.post("/{name}/images")
async def upload_image(name: str, file: UploadFile = File(...)):
    _validate_name(name)
    cat_path = CATEGORIES_DIR / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(status_code=404, detail="类别不存在")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    suffix = Path(file.filename or "img.jpg").suffix.lower()
    if suffix not in IMAGE_EXTS:
        suffix = ".jpg"
    base = Path(file.filename or "img").stem
    out_path = cat_path / f"{base}{suffix}"
    n = 0
    while out_path.exists():
        n += 1
        out_path = cat_path / f"{base}_{n}{suffix}"
    contents = await file.read()
    out_path.write_bytes(contents)
    add_log("upload_image", f"在 {name} 中上传图片：{out_path.name}")
    return {"message": "上传成功", "filename": out_path.name}


@router.delete("/{name}/images/{filename}")
def delete_image(name: str, filename: str):
    _validate_name(name)
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    cat_path = CATEGORIES_DIR / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(status_code=404, detail="类别不存在")
    img_path = cat_path / filename
    if not img_path.exists() or not img_path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    add_log("delete_image", f"在 {name} 中删除图片：{filename}")
    img_path.unlink()
    return {"message": "删除成功"}


class TrainFromCategoriesRequest(BaseModel):
    dataset_id: int  # 用选中的数据集（其 local_path 下的类别/图片）训练
    epochs: int = 10


@router.post("/train")
def train_from_categories(body: TrainFromCategoriesRequest, db: Session = Depends(get_db)):
    """用指定数据集下的类别数据训练，目录随选定数据集变化。"""
    ds = db.query(Dataset).filter(Dataset.id == body.dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not ds.local_path or not Path(ds.local_path).exists():
        raise HTTPException(status_code=400, detail="数据集路径无效")
    root = Path(ds.local_path)
    if not root.is_dir():
        raise HTTPException(status_code=400, detail="数据集路径不是有效目录")
    dirs = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]
    n_cats = len(dirs)
    if n_cats < 2:
        raise HTTPException(status_code=400, detail=f"该数据集下至少需要 2 个类别才能训练（当前 {n_cats} 个）")
    total = _count_images(root)
    if total < 10:
        raise HTTPException(status_code=400, detail=f"总图片数至少 10 张，当前仅 {total} 张")
    epochs = max(2, min(50, body.epochs))
    snapshot = {"categories": sorted(d.name for d in dirs), "total_images": total}
    task = TrainTask(
        dataset_id=ds.id,
        status="pending",
        params_json=json.dumps({"epochs": epochs, "batch_size": 16, "model_type": "mobilenet_v2", "snapshot": snapshot}),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    ok = start_train(task.id, ds.local_path, epochs=epochs, batch_size=16)
    if ok:
        task.status = "running"
    else:
        task.status = "error"
    db.commit()
    add_log("train_from_categories", f"用数据集「{ds.name}」启动训练任务 #{task.id}，共 {total} 张图，{epochs} 轮")
    return {"message": "训练已启动", "task_id": task.id, "epochs": epochs}
