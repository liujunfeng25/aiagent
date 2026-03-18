import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query
from sqlalchemy.orm import Session
from PIL import Image

from config import TOP_K, INFERENCE_DEVICE, TEST_IMAGES_DIR, PRESET_VEGETABLE_MODEL_DIR
from app.database import get_db
from app.models import Model
from app.services.inference import recognize

router = APIRouter()


def _get_deployed_model(db: Session) -> Model | None:
    return db.query(Model).filter(Model.deployed == True).first()


@router.get("/preset-available")
def preset_available():
    """检查是否存在可用的预置蔬菜模型（vegetable-recognition 集成）。"""
    model_pt = PRESET_VEGETABLE_MODEL_DIR / "model.pt"
    return {"available": model_pt.exists()}


@router.post("/deploy-preset")
def deploy_preset(db: Session = Depends(get_db)):
    """一键部署预置蔬菜模型，无需先训练。"""
    from app.services.preset_model import register_preset_vegetable_model_if_exists
    register_preset_vegetable_model_if_exists(db)
    m = _get_deployed_model(db)
    if m:
        return {"success": True, "message": f"已部署模型：{m.name}"}
    model_pt = PRESET_VEGETABLE_MODEL_DIR / "model.pt"
    if not model_pt.exists():
        raise HTTPException(status_code=404, detail="预置模型文件不存在，请确保 data/preset_vegetable_model/model.pt 存在")
    return {"success": False, "message": "部署失败，请查看后端日志"}


@router.get("/test-images")
def list_test_images():
    """返回集成自 vegetable-recognition 的测试图片文件名列表，用于识别中心示例。"""
    if not TEST_IMAGES_DIR.exists():
        return {"files": []}
    exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    files = [f.name for f in TEST_IMAGES_DIR.iterdir() if f.is_file() and f.suffix.lower() in exts]
    return {"files": sorted(files)}


@router.get("/status")
def recognition_status(db: Session = Depends(get_db)):
    """返回当前是否已部署模型及模型名称，供前端展示。"""
    m = _get_deployed_model(db)
    if not m:
        return {"deployed": False, "model_name": None, "message": "请先在模型库部署模型"}
    return {
        "deployed": True,
        "model_name": m.name,
        "model_id": m.id,
    }


@router.post(
    "/recognize",
    description="上传图片，返回 Top-K 识别结果。可选 model_id 指定模型，不传则使用当前已部署模型，便于多客户端按场景调用不同模型。",
)
async def recognize_image(
    file: UploadFile = File(...),
    model_id: int | None = Query(None, description="指定使用的模型 ID，不传则使用当前已部署模型"),
    db: Session = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件（如 jpg、png）")

    if model_id is not None:
        m = db.query(Model).filter(Model.id == model_id).first()
        if not m:
            raise HTTPException(status_code=404, detail=f"模型不存在: id={model_id}")
    else:
        m = _get_deployed_model(db)
        if not m or not m.path:
            raise HTTPException(
                status_code=503,
                detail="未传 model_id 且当前没有已部署的模型，请传 model_id 或在模型库中部署一个模型",
            )

    if not m.path:
        raise HTTPException(status_code=503, detail="该模型未关联模型文件")

    model_path = Path(m.path)
    if not model_path.exists():
        raise HTTPException(status_code=503, detail="模型文件不存在，请检查路径或重新训练")

    class_mapping_path = model_path.parent / "class_mapping.json"
    if not class_mapping_path.exists():
        class_mapping_path = None

    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片解析失败: {str(e)}")

    results = recognize(
        image,
        model_path=str(model_path),
        class_mapping_path=str(class_mapping_path) if class_mapping_path else None,
        device=INFERENCE_DEVICE,
        top_k=TOP_K,
    )
    return {
        "results": results,
        "model_id": m.id,
        "model_name": m.name,
    }
