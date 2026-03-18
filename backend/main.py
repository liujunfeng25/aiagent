# AI 训练与数据智能平台
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import TEST_IMAGES_DIR
from app.database import init_db
from app.routers import dashboard, datasources, datasets, training, models, analysis, system, recognition, categories
from app.xinfadi.routes import router as xinfadi_router

app = FastAPI(title="AI Agent 平台", description="AI 训练与数据智能平台 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(datasources.router, prefix="/api/datasources", tags=["datasources"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(recognition.router, prefix="/api/recognition", tags=["recognition"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(xinfadi_router)

# 测试图片静态文件（vegetable-recognition 集成）
if TEST_IMAGES_DIR.exists():
    app.mount("/api/recognition/test_images", StaticFiles(directory=str(TEST_IMAGES_DIR)), name="recognition_test_images")

# 静态文件（生产环境挂载前端构建产物）
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


@app.on_event("startup")
def startup():
    init_db()
    try:
        from app.services.preset_model import register_preset_vegetable_model_if_exists
        register_preset_vegetable_model_if_exists()
    except Exception:
        pass
    try:
        from app.database import SessionLocal
        from app.routers.models import dedupe_models_by_dataset
        db = SessionLocal()
        n = dedupe_models_by_dataset(db)
        db.close()
        if n:
            print(f"[startup] 按数据集去重模型，已删除 {n} 条多余记录")
    except Exception:
        pass


@app.get("/api/health")
def health():
    return {"status": "ok"}
