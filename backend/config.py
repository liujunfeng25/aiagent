# AI Agent 平台配置
import importlib.util
import os
import warnings
from pathlib import Path
from typing import Optional

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

# 数据洞察：直连业务 MySQL。未设置 INSIGHTS_MYSQL_HOST 时**不**臆造 127.0.0.1（否则本机未起库会到处 500），
# 改走「数据源」里第一条 MySQL；Docker 见 aiagent/docker-compose.yml 已设 HOST=mysql。
_INSIGHTS_HOST = os.environ.get("INSIGHTS_MYSQL_HOST", "").strip()
INSIGHTS_MYSQL_HOST = _INSIGHTS_HOST
INSIGHTS_MYSQL_PORT = int(os.environ.get("INSIGHTS_MYSQL_PORT", "3307"))
INSIGHTS_MYSQL_USER = os.environ.get("INSIGHTS_MYSQL_USER", "root").strip()
INSIGHTS_MYSQL_PASSWORD = os.environ.get("INSIGHTS_MYSQL_PASSWORD", "116165")
INSIGHTS_MYSQL_DATABASE = os.environ.get("INSIGHTS_MYSQL_DATABASE", "agent").strip()

# SXW 业务数据库（物流模块直连）
SXW_MYSQL_HOST = os.environ.get("SXW_MYSQL_HOST", "1.92.102.228").strip()
SXW_MYSQL_PORT = int(os.environ.get("SXW_MYSQL_PORT", "3306"))
SXW_MYSQL_USER = os.environ.get("SXW_MYSQL_USER", "edu_std_supp").strip()
SXW_MYSQL_PASSWORD = os.environ.get("SXW_MYSQL_PASSWORD", "THwnkTSQbcCCrsey")
SXW_MYSQL_DATABASE = os.environ.get("SXW_MYSQL_DATABASE", "edu_std_supp").strip()
# 与食迅后台 admin/init.php 一致：登录后按 supp_code 切到 supp_{数字} 库。未登录时 PHP 使用库名来自配置（常为 edu_std_supp）。
SXW_MYSQL_SUPP_CODE = os.environ.get("SXW_MYSQL_SUPP_CODE", "10133").strip()


def process_supp_code(supp_code: str) -> str:
    """与 education_industry_allocation/common/function.php 中 processSuppCode 同逻辑。"""
    supp_code = (supp_code or "").strip()
    if not supp_code:
        return ""
    if supp_code == "edu_std_supp":
        return supp_code
    if supp_code.startswith("supp_"):
        code = supp_code[5:]
    else:
        code = supp_code
    code = code.strip()
    if not code.isdigit():
        return ""
    return f"supp_{code}"


def resolve_sxw_mysql_database(supp_override: Optional[str] = None) -> str:
    """请求级 supp_code优先，其次环境变量 SXW_MYSQL_SUPP_CODE，最后 SXW_MYSQL_DATABASE。"""
    for raw in ((supp_override or "").strip(), SXW_MYSQL_SUPP_CODE):
        if not raw:
            continue
        name = process_supp_code(raw)
        if name:
            return name
    return SXW_MYSQL_DATABASE

# 票据识别（百度表格 OCR）：上传目录与引擎
DOCUMENTS_PREPROCESS_ENABLED = True
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


def _load_config_fuben_py() -> None:
    """若存在 config_副本.py，则用其中与 config 同名的「大写常量」覆盖当前模块全局变量（在 .env 之后生效）。"""
    path = PROJECT_ROOT / "config_副本.py"
    if not path.is_file():
        return
    spec = importlib.util.spec_from_file_location("_aiagent_config_fuben", path)
    if not spec or not spec.loader:
        return
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        warnings.warn(f"跳过 config_副本.py：加载失败 ({e})", stacklevel=2)
        return
    g = globals()
    for name in dir(mod):
        if name.startswith("_") or not name.isupper():
            continue
        g[name] = getattr(mod, name)


_load_config_fuben_py()

# 副本可能把 DOCUMENTS_OCR_ENGINE 设为任意大小写，与上文规则对齐
_doc_ocr = (
    str(DOCUMENTS_OCR_ENGINE).strip().lower()
    if isinstance(DOCUMENTS_OCR_ENGINE, str)
    else ""
)
if _doc_ocr in ("baidu", "mock"):
    DOCUMENTS_OCR_ENGINE = _doc_ocr
elif _doc_ocr == "paddle":
    DOCUMENTS_OCR_ENGINE = "mock"
elif not _doc_ocr:
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
