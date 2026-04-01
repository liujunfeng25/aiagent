import re
from pathlib import Path

from sqlalchemy.orm import Session

from config import MODELS_DIR, TASKS_DIR, DATASETS_DIR
from app.models import Model, TrainTask, Dataset


_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_MODEL_PT_RE = re.compile(r"(?:^|[\\/])models[\\/](\d+)[\\/]model\.pt$", re.IGNORECASE)
_STATUS_JSON_RE = re.compile(r"(?:^|[\\/])tasks[\\/](\d+)[\\/]status\.json$", re.IGNORECASE)
_DATASET_DIR_RE = re.compile(r"(?:^|[\\/])datasets[\\/](\d+)(?:$|[\\/])", re.IGNORECASE)


def _looks_like_windows_abs(p: str) -> bool:
    return bool(_WIN_DRIVE_RE.match(p or ""))


def _maybe_fix_model_pt_path(raw: str) -> tuple[bool, str | None]:
    """
    尝试把 Windows 绝对路径（或包含 models/<id>/model.pt 的路径）修复为当前环境可用的路径。
    返回 (changed, new_path_or_none)。
    """
    if not raw:
        return False, None
    s = str(raw).strip()

    # 仅在明显是 Windows 路径时尝试修复，避免误改正常 Linux 路径
    if not _looks_like_windows_abs(s) and "/models/" not in s.replace("\\", "/"):
        return False, None

    m = _MODEL_PT_RE.search(s)
    if not m:
        return False, None
    task_id = m.group(1)
    target = MODELS_DIR / str(task_id) / "model.pt"
    if not target.exists():
        return False, None
    return True, str(target.resolve())


def _maybe_fix_status_file_path(raw: str) -> tuple[bool, str | None]:
    if not raw:
        return False, None
    s = str(raw).strip()
    if not _looks_like_windows_abs(s) and "/tasks/" not in s.replace("\\", "/"):
        return False, None
    m = _STATUS_JSON_RE.search(s)
    if not m:
        return False, None
    task_id = m.group(1)
    target = TASKS_DIR / str(task_id) / "status.json"
    if not target.exists():
        return False, None
    return True, str(target.resolve())


def _maybe_fix_dataset_dir_path(raw: str) -> tuple[bool, str | None]:
    if not raw:
        return False, None
    s = str(raw).strip()
    if not _looks_like_windows_abs(s) and "/datasets/" not in s.replace("\\", "/"):
        return False, None
    m = _DATASET_DIR_RE.search(s)
    if not m:
        return False, None
    ds_id = m.group(1)
    target = DATASETS_DIR / str(ds_id)
    if not target.exists():
        return False, None
    return True, str(target.resolve())


def migrate_windows_paths(db: Session) -> dict:
    """
    迁移旧的 Windows 绝对路径为当前运行环境可用的路径。
    仅在目标文件实际存在时才写回。
    """
    changed_models = 0
    changed_tasks = 0
    changed_datasets = 0

    # TrainTask.model_path / TrainTask.status_file
    for t in db.query(TrainTask).all():
        changed = False
        if t.model_path:
            ok, newp = _maybe_fix_model_pt_path(t.model_path)
            if ok and newp and newp != t.model_path:
                t.model_path = newp
                changed = True
        if t.status_file:
            ok, newp = _maybe_fix_status_file_path(t.status_file)
            if ok and newp and newp != t.status_file:
                t.status_file = newp
                changed = True
        if changed:
            changed_tasks += 1

    # Model.path
    for m in db.query(Model).all():
        if not m.path:
            continue
        ok, newp = _maybe_fix_model_pt_path(m.path)
        if ok and newp and newp != m.path:
            m.path = newp
            changed_models += 1

    # Dataset.local_path
    for d in db.query(Dataset).all():
        if not d.local_path:
            continue
        ok, newp = _maybe_fix_dataset_dir_path(d.local_path)
        if ok and newp and newp != d.local_path:
            d.local_path = newp
            changed_datasets += 1

    if changed_models or changed_tasks or changed_datasets:
        db.commit()

    return {
        "models_updated": changed_models,
        "train_tasks_updated": changed_tasks,
        "datasets_updated": changed_datasets,
    }

