# 组合数据集合并服务
"""将多个数据集按类别文件夹合并为一个"""
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Dataset

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif")


def _is_image_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS


def _count_images_in_dir(d: Path) -> int:
    return sum(1 for f in d.iterdir() if _is_image_file(f))


def _get_class_folders(path: Path) -> list[Path]:
    """获取图片分类结构的类别文件夹（至少含一张图）"""
    if not path.exists() or not path.is_dir():
        return []
    return [d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".") and _count_images_in_dir(d) > 0]


def merge_datasets(source_dataset_ids: list[int], target_path: Path, db: Session) -> int:
    """
    将多个数据集按类别合并到 target_path，返回总图片数。
    同名类别合并到同一文件夹；文件名冲突时使用 {src_id}_{原名} 保证唯一。
    """
    target_path = Path(target_path)
    target_path.mkdir(parents=True, exist_ok=True)
    total = 0

    for src_id in source_dataset_ids:
        ds = db.query(Dataset).filter(Dataset.id == src_id).first()
        if not ds or not ds.local_path:
            raise ValueError(f"数据集 {src_id} 不存在或路径无效")
        src_path = Path(ds.local_path)
        if not src_path.exists():
            raise ValueError(f"数据集 {src_id} 路径不存在: {src_path}")

        class_dirs = _get_class_folders(src_path)
        if not class_dirs:
            continue

        for class_dir in class_dirs:
            class_name = class_dir.name
            out_dir = target_path / class_name
            out_dir.mkdir(parents=True, exist_ok=True)

            for img in class_dir.iterdir():
                if not _is_image_file(img):
                    continue
                base = img.stem
                suffix = img.suffix.lower()
                out_file = out_dir / f"{src_id}_{base}{suffix}"
                n = 0
                while out_file.exists():
                    n += 1
                    out_file = out_dir / f"{src_id}_{base}_{n}{suffix}"
                shutil.copy2(img, out_file)
                total += 1

    class_count = len(_get_class_folders(target_path))
    if class_count < 2:
        raise ValueError(f"合并后仅 {class_count} 个类别，训练至少需要 2 个类别")
    return total
