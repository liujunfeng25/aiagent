import json
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from config import DATASETS_DIR
from app.database import get_db
from app.models import Dataset
from app.services.operation_log import add_log
from app.services.dataset_merge import merge_datasets

router = APIRouter()

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"}


class DatasetCreate(BaseModel):
    name: str
    source_type: str = "upload"  # upload, from_source, composite
    source_id: int | None = None
    config_json: str | None = None


class DatasetRenameBody(BaseModel):
    name: str


@router.get("/")
def list_datasets(db: Session = Depends(get_db)):
    items = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    result = []
    for d in items:
        row_count = d.row_count
        root = _dataset_categories_path(d)
        if root:
            subdirs = [x for x in root.iterdir() if x.is_dir() and not x.name.startswith(".")]
            if subdirs:
                row_count = _count_images_in_dataset(root)
        item = {
            "id": d.id,
            "name": d.name,
            "source_type": d.source_type,
            "row_count": row_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        if d.source_type == "composite" and d.config_json:
            try:
                cfg = json.loads(d.config_json)
                item["source_ids"] = cfg.get("source_ids", [])
            except (json.JSONDecodeError, TypeError):
                item["source_ids"] = []
        result.append(item)
    return {"data": result}


@router.post("/")
def create_dataset(body: DatasetCreate, db: Session = Depends(get_db)):
    if body.source_type == "composite":
        if not body.config_json:
            raise HTTPException(400, "组合数据集需要 config_json 包含 source_ids")
        try:
            cfg = json.loads(body.config_json)
            source_ids = cfg.get("source_ids", [])
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(400, "config_json 格式无效")
        source_ids = [int(x) for x in source_ids]
        if len(source_ids) < 2:
            raise HTTPException(400, "组合数据集至少需要 2 个源")
        if len(source_ids) != len(set(source_ids)):
            raise HTTPException(400, "source_ids 不能重复")
        for sid in source_ids:
            src = db.query(Dataset).filter(Dataset.id == sid).first()
            if not src or not src.local_path or not Path(src.local_path).exists():
                raise HTTPException(400, f"源数据集 {sid} 不存在或路径无效")
            if src.source_type not in ("upload", "composite"):
                raise HTTPException(400, f"源数据集 {sid} 需为 upload 或 composite 类型")

    ds = Dataset(
        name=body.name,
        source_type=body.source_type,
        source_id=body.source_id,
        config_json=body.config_json,
        row_count=0,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    path = DATASETS_DIR / str(ds.id)

    if body.source_type == "composite":
        path.mkdir(parents=True, exist_ok=True)
        try:
            count = merge_datasets(source_ids, path, db)
        except ValueError as e:
            db.delete(ds)
            db.commit()
            raise HTTPException(400, str(e))
        ds.local_path = str(path)
        ds.row_count = count
    else:
        path.mkdir(parents=True, exist_ok=True)
        ds.local_path = str(path)

    db.commit()
    add_log("create_dataset", f"创建数据集：{body.name}" + (" (组合)" if body.source_type == "composite" else ""))
    return {"id": ds.id, "message": "创建成功"}


@router.post("/upload")
async def upload_dataset(name: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    ds = Dataset(name=name, source_type="upload", row_count=0)
    db.add(ds)
    db.commit()
    db.refresh(ds)
    path = DATASETS_DIR / str(ds.id)
    path.mkdir(parents=True, exist_ok=True)
    out = path / (file.filename or "data.csv")
    content = await file.read()
    out.write_bytes(content)
    ds.local_path = str(path)
    ds.row_count = len(content.split(b"\n")) - 1 if content else 0
    db.commit()
    add_log("upload_dataset", f"上传数据集：{name}")
    return {"id": ds.id, "message": "上传成功"}


@router.get("/{id}")
def get_dataset(id: int, db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    if not ds:
        raise HTTPException(404, "数据集不存在")
    return {
        "id": ds.id,
        "name": ds.name,
        "source_type": ds.source_type,
        "source_id": ds.source_id,
        "config_json": ds.config_json,
        "row_count": ds.row_count,
        "local_path": ds.local_path,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
    }


@router.patch("/{id}")
def rename_dataset(id: int, body: DatasetRenameBody, db: Session = Depends(get_db)):
    """重命名数据集（兼容所有已存在的数据集）"""
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    if not ds:
        raise HTTPException(404, "数据集不存在")
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    if len(name) > 200:
        raise HTTPException(400, "名称过长")
    ds.name = name
    db.commit()
    add_log("rename_dataset", f"重命名数据集 #{id} 为：{name}")
    return {"message": "已修改", "name": name}


@router.get("/{id}/preview")
def preview_dataset(id: int, limit: int = 20, db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    if not ds or not ds.local_path:
        raise HTTPException(404, "数据集不存在")
    path = Path(ds.local_path)
    files = list(path.glob("*.csv")) + list(path.glob("*.txt"))
    if not files:
        # 检查是否是图片目录结构（类别/图片）
        dirs = [d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if dirs:
            total = sum(sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS) for d in dirs)
            return {"type": "image_folders", "classes": [d.name for d in dirs], "total": total, "rows": []}
        return {"type": "empty", "rows": []}
    f = files[0]
    lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()[: limit + 1]
    header = lines[0].split(",") if lines else []
    rows = [line.split(",") for line in lines[1:]]
    return {"type": "csv", "columns": header, "rows": rows}


def _dataset_categories_path(ds: Dataset | None) -> Path | None:
    if not ds or not ds.local_path:
        return None
    p = Path(ds.local_path)
    return p if p.exists() and p.is_dir() else None


def _count_images_in_dataset(root: Path) -> int:
    """统计图片分类目录下的总图片数（子文件夹=类别）"""
    total = 0
    for d in root.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            total += sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS)
    return total


def _count_images_in_dir(d: Path) -> int:
    return sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS)


@router.get("/{id}/categories")
def list_dataset_categories(id: int, db: Session = Depends(get_db)):
    """返回该数据集下的类别列表（子文件夹=类别）"""
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    root = _dataset_categories_path(ds)
    if not root:
        raise HTTPException(404, "数据集不存在或路径无效")
    cats = []
    total = 0
    for d in sorted(root.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            c = _count_images_in_dir(d)
            cats.append({"name": d.name, "count": c})
            total += c
    return {"categories": cats, "total_images": total}


class CreateCategoryBody(BaseModel):
    name: str


@router.post("/{id}/categories")
def create_dataset_category(id: int, body: CreateCategoryBody, db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    root = _dataset_categories_path(ds)
    if not root:
        raise HTTPException(404, "数据集不存在或路径无效")
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(400, "类别名不能为空")
    if "/" in name or "\\" in name or "." in name:
        raise HTTPException(400, "类别名不能包含 . / \\")
    cat_path = root / name
    if cat_path.exists():
        raise HTTPException(409, "类别已存在")
    cat_path.mkdir(parents=True, exist_ok=True)
    add_log("create_dataset_category", f"数据集 {id} 新增类别：{name}")
    return {"message": "创建成功", "name": name}


@router.delete("/{id}/categories/{name}")
def delete_dataset_category(id: int, name: str, db: Session = Depends(get_db)):
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(400, "非法类别名")
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    root = _dataset_categories_path(ds)
    if not root:
        raise HTTPException(404, "数据集不存在或路径无效")
    cat_path = root / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(404, "类别不存在")
    shutil.rmtree(cat_path)
    add_log("delete_dataset_category", f"数据集 {id} 删除类别：{name}")
    return {"message": "删除成功"}


@router.get("/{id}/categories/{name}/image/{filename}", include_in_schema=False)
def serve_dataset_category_image(id: int, name: str, filename: str, db: Session = Depends(get_db)):
    """供前端展示类别下的图片缩略图"""
    if ".." in name or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "非法路径")
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    root = _dataset_categories_path(ds)
    if not root:
        raise HTTPException(404, "数据集不存在或路径无效")
    cat_path = root / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(404, "类别不存在")
    img_path = cat_path / filename
    if not img_path.exists() or not img_path.is_file():
        raise HTTPException(404, "图片不存在")
    return FileResponse(img_path)


@router.get("/{id}/categories/{name}/images")
def list_dataset_category_images(id: int, name: str, db: Session = Depends(get_db)):
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(400, "非法类别名")
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    root = _dataset_categories_path(ds)
    if not root:
        raise HTTPException(404, "数据集不存在或路径无效")
    cat_path = root / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(404, "类别不存在")
    files = [f.name for f in cat_path.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
    return {"images": sorted(files)}


@router.post("/{id}/categories/{name}/images")
async def upload_dataset_category_image(
    id: int, name: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(400, "非法类别名")
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    root = _dataset_categories_path(ds)
    if not root:
        raise HTTPException(404, "数据集不存在或路径无效")
    cat_path = root / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(404, "类别不存在")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")
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
    add_log("upload_dataset_category_image", f"数据集 {id} 类别 {name} 上传：{out_path.name}")
    return {"message": "上传成功", "filename": out_path.name}


@router.delete("/{id}/categories/{name}/images/{filename}")
def delete_dataset_category_image(
    id: int, name: str, filename: str, db: Session = Depends(get_db)
):
    if ".." in name or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "非法路径")
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    root = _dataset_categories_path(ds)
    if not root:
        raise HTTPException(404, "数据集不存在或路径无效")
    cat_path = root / name
    if not cat_path.exists() or not cat_path.is_dir():
        raise HTTPException(404, "类别不存在")
    img_path = cat_path / filename
    if not img_path.exists() or not img_path.is_file():
        raise HTTPException(404, "图片不存在")
    img_path.unlink()
    add_log("delete_dataset_category_image", f"数据集 {id} 类别 {name} 删除：{filename}")
    return {"message": "删除成功"}


@router.delete("/{id}")
def delete_dataset(id: int, db: Session = Depends(get_db)):
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    if not ds:
        raise HTTPException(404, "数据集不存在")
    if ds.local_path and Path(ds.local_path).exists():
        shutil.rmtree(ds.local_path, ignore_errors=True)
    db.delete(ds)
    db.commit()
    add_log("delete_dataset", f"删除数据集：{ds.name}")
    return {"message": "删除成功"}
