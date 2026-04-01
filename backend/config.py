# AI Agent 平台配置
import importlib.util
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.resolve()
# 先加载本后端 .env，再尝试同级 puaojuchuli 的 .env（不覆盖已有变量）
load_dotenv(PROJECT_ROOT / ".env")
_pua_backend = PROJECT_ROOT.parent.parent / "puaojuchuli" / "backend"
_pua_env = _pua_backend / ".env"
if _pua_env.is_file():
    load_dotenv(_pua_env, override=False)
_pua_env2 = PROJECT_ROOT.parent / "puaojuchuli" / "backend" / ".env"
if _pua_env2.is_file():
    load_dotenv(_pua_env2, override=False)
load_dotenv(override=False)
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "ai_agent.db"
DATASETS_DIR = DATA_DIR / "datasets"
TASKS_DIR = DATA_DIR / "tasks"
MODELS_DIR = DATA_DIR / "models"
LOGS_DIR = DATA_DIR / "logs"
CATEGORIES_DIR = DATA_DIR / "categories"
TEST_IMAGES_DIR = DATA_DIR / "test_images"
# 新发地报价：按日 JSON 磁盘缓存（演示时避免重启后冷启动；命中则秒开）
XINFADI_PRICE_CACHE_DIR = DATA_DIR / "xinfadi_price"
PRESET_VEGETABLE_MODEL_DIR = PROJECT_ROOT / "preset_vegetable_model"
TOP_K = 5
INFERENCE_DEVICE = "cpu"

# 数据洞察：直连业务 MySQL。默认连本机 Docker 映射（compose 中 mysql 3307:3306，与 MYSQL_ROOT_PASSWORD 一致）；
# 在容器内请用环境变量覆盖为 INSIGHTS_MYSQL_HOST=mysql、PORT=3306。
_INSIGHTS_HOST = os.environ.get("INSIGHTS_MYSQL_HOST", "").strip()
INSIGHTS_MYSQL_HOST = _INSIGHTS_HOST or "127.0.0.1"
INSIGHTS_MYSQL_PORT = int(os.environ.get("INSIGHTS_MYSQL_PORT", "3307"))
INSIGHTS_MYSQL_USER = os.environ.get("INSIGHTS_MYSQL_USER", "root").strip()
INSIGHTS_MYSQL_PASSWORD = os.environ.get("INSIGHTS_MYSQL_PASSWORD", "116165")
INSIGHTS_MYSQL_DATABASE = os.environ.get("INSIGHTS_MYSQL_DATABASE", "agent").strip()

# 票据识别（百度表格 OCR）：上传目录与引擎
DOCUMENTS_UPLOAD_DIR = DATA_DIR / "documents" / "uploads"
DOCUMENTS_BAIDU_TABLE_API_KEY = os.environ.get("DOCUMENTS_BAIDU_TABLE_API_KEY", "").strip()


def _baidu_key_from_puaojuchuli_config_py() -> str:
    """与独立项目 puaojuchuli 对齐：若未配环境变量，则尝试加载其 backend/config.py 中的默认密钥。"""
    explicit = os.environ.get("DOCUMENTS_BAIDU_CONFIG_PATH", "").strip()
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            PROJECT_ROOT.parent.parent / "puaojuchuli" / "backend" / "config.py",
            PROJECT_ROOT.parent / "puaojuchuli" / "backend" / "config.py",
        ]
    )
    for cfg_path in candidates:
        if not cfg_path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("_pua_documents_cfg", cfg_path)
        if not spec or not spec.loader:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
        key = getattr(mod, "DOCUMENTS_BAIDU_TABLE_API_KEY", None)
        if key and str(key).strip():
            return str(key).strip()
    return ""


if not DOCUMENTS_BAIDU_TABLE_API_KEY:
    DOCUMENTS_BAIDU_TABLE_API_KEY = _baidu_key_from_puaojuchuli_config_py()

_env_doc_engine = os.environ.get("DOCUMENTS_OCR_ENGINE", "").strip().lower()
if _env_doc_engine in ("baidu", "mock"):
    DOCUMENTS_OCR_ENGINE = _env_doc_engine
elif _env_doc_engine == "paddle":
    DOCUMENTS_OCR_ENGINE = "mock"
else:
    # 与 puaojuchuli 一致：有密钥时默认走百度，否则演示用 mock
    DOCUMENTS_OCR_ENGINE = "baidu" if DOCUMENTS_BAIDU_TABLE_API_KEY else "mock"

# 确保目录存在
for d in (
    DATA_DIR,
    DATASETS_DIR,
    TASKS_DIR,
    MODELS_DIR,
    LOGS_DIR,
    CATEGORIES_DIR,
    TEST_IMAGES_DIR,
    DOCUMENTS_UPLOAD_DIR,
):
    d.mkdir(parents=True, exist_ok=True)
