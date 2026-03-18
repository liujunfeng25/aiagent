# 训练任务执行
import json
import subprocess
import sys
from pathlib import Path

from config import PROJECT_ROOT, TASKS_DIR, MODELS_DIR

TRAIN_SCRIPT = PROJECT_ROOT / "train" / "train.py"

_running = {}  # task_id -> process


def start_train(task_id: int, dataset_path: str, epochs: int = 10, batch_size: int = 16) -> bool:
    task_dir = TASKS_DIR / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    status_file = task_dir / "status.json"

    output_dir = MODELS_DIR / str(task_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "model.pt"

    python = sys.executable
    cmd = [
        python,
        str(TRAIN_SCRIPT),
        "--data_dir", dataset_path,
        "--output", str(output_path),
        "--epochs", str(epochs),
        "--batch_size", str(batch_size),
        "--status_file", str(status_file),
    ]
    try:
        proc = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _running[task_id] = proc
        return True
    except Exception:
        status_file.write_text(json.dumps({"status": "error", "message": "启动失败"}, ensure_ascii=False), encoding="utf-8")
        return False


def get_status(task_id: int) -> dict:
    status_file = TASKS_DIR / str(task_id) / "status.json"
    if not status_file.exists():
        proc = _running.get(task_id)
        if proc and proc.poll() is None:
            return {"status": "starting", "message": "训练启动中..."}
        if proc and proc.poll() is not None:
            _running.pop(task_id, None)
        return {"status": "idle", "message": "未开始"}
    try:
        return json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "idle", "message": "未知"}


def cancel_task(task_id: int) -> bool:
    proc = _running.get(task_id)
    if proc and proc.poll() is None:
        proc.terminate()
        _running.pop(task_id, None)
        return True
    return False


def is_running(task_id: int) -> bool:
    proc = _running.get(task_id)
    return proc is not None and proc.poll() is None
