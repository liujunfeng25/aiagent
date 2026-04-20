# AI 训练与数据智能平台
from pathlib import Path

# 放宽 multipart 单 part 大小，避免票据大图上传触发 Part exceeded maximum size
try:
    from starlette.formparsers import MultiPartParser

    MultiPartParser.max_part_size = 20 * 1024 * 1024
except Exception:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import TEST_IMAGES_DIR
from app.database import init_db
from app.routers import (
    dashboard,
    datasets,
    training,
    models,
    analysis,
    system,
    recognition,
    categories,
    documents,
    insights_business,
    logistics,
    governance_demo,
    map_tiles,
)
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
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(training.router, prefix="/api/training", tags=["training"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(insights_business.router, prefix="/api/insights/business", tags=["insights_business"])
app.include_router(map_tiles.router, prefix="/api/map", tags=["map_tiles"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(recognition.router, prefix="/api/recognition", tags=["recognition"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(documents.router, prefix="/api/doc", tags=["documents"])
app.include_router(xinfadi_router)
app.include_router(logistics.router, prefix="/api/logistics", tags=["logistics"])
app.include_router(governance_demo.router, prefix="/api/governance", tags=["governance_demo"])

# 测试图片静态文件（vegetable-recognition 集成）
if TEST_IMAGES_DIR.exists():
    app.mount("/api/recognition/test_images", StaticFiles(directory=str(TEST_IMAGES_DIR)), name="recognition_test_images")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 前端 SPA：Vite 产物在 frontend/dist；深链刷新须回退 index.html（html=True 仅对目录有效，不能直接解决 /logistics/...）
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    _assets = frontend_dist / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="frontend_assets")

    @app.get("/")
    async def spa_index():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        base = frontend_dist.resolve()
        target = (base / full_path).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not Found")
        if target.is_file():
            return FileResponse(target)
        return FileResponse(base / "index.html")


@app.on_event("startup")
async def startup():
    init_db()
    try:
        from app.database import SessionLocal
        from app.services.path_migration import migrate_windows_paths
        db = SessionLocal()
        r = migrate_windows_paths(db)
        db.close()
        if r.get("models_updated") or r.get("train_tasks_updated") or r.get("datasets_updated"):
            print(
                f"[startup] 修复路径：models={r.get('models_updated', 0)} "
                f"train_tasks={r.get('train_tasks_updated', 0)} "
                f"datasets={r.get('datasets_updated', 0)}"
            )
    except Exception:
        pass
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
    try:
        from app.services.live_gmv_poller import start_live_gmv_background

        await start_live_gmv_background()
    except Exception:
        pass
