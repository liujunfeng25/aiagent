# AI Agent 平台配置
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "ai_agent.db"
DATASETS_DIR = DATA_DIR / "datasets"
TASKS_DIR = DATA_DIR / "tasks"
MODELS_DIR = DATA_DIR / "models"
LOGS_DIR = DATA_DIR / "logs"
CATEGORIES_DIR = DATA_DIR / "categories"
TEST_IMAGES_DIR = DATA_DIR / "test_images"
PRESET_VEGETABLE_MODEL_DIR = PROJECT_ROOT / "preset_vegetable_model"
TOP_K = 5
INFERENCE_DEVICE = "cpu"

# 确保目录存在
for d in (DATA_DIR, DATASETS_DIR, TASKS_DIR, MODELS_DIR, LOGS_DIR, CATEGORIES_DIR, TEST_IMAGES_DIR):
    d.mkdir(parents=True, exist_ok=True)
