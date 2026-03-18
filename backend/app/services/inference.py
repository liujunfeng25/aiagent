# 图像识别推理模块（集成自 vegetable-recognition）
# 支持多模型：按 (model_path, class_mapping_path) 缓存，LRU 淘汰，供按 model_id 调用的识别 API 使用
import json
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

# 预处理与 vegetable-recognition 一致
_preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# 多模型缓存：key=(model_path, mapping_path), value={"model": nn.Module, "mapping": dict}
# 超过 MAX_CACHE 时淘汰最早加入的（LRU 按加入顺序）
MAX_CACHE = 5
_cache: dict[tuple[str, str], dict] = {}


def _load_class_mapping(path: str | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        m = json.load(f)
    return {str(k): v for k, v in m.items()}


def load_model(model_path: str, class_mapping_path: str | None, device: str = "cpu", top_k: int = 5):
    """加载指定 model.pt 与 class_mapping.json；相同路径时使用缓存，多模型按 key 分别缓存。"""
    global _cache
    mapping_path = class_mapping_path or ""
    key = (model_path, mapping_path)
    if key in _cache:
        return _cache[key]["model"]

    path_obj = Path(model_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    model = torch.load(model_path, map_location=device, weights_only=False)
    if hasattr(model, "eval"):
        model = model.eval()
    mapping = _load_class_mapping(class_mapping_path)
    _cache[key] = {"model": model, "mapping": mapping}
    while len(_cache) > MAX_CACHE:
        first_key = next(iter(_cache))
        del _cache[first_key]
    return model


def _get_cached_mapping(model_path: str, class_mapping_path: str | None) -> dict:
    """取当前缓存中该路径对应的 class_mapping，若未缓存则只读 mapping 文件。"""
    mapping_path = class_mapping_path or ""
    key = (model_path, mapping_path)
    if key in _cache:
        return _cache[key]["mapping"]
    return _load_class_mapping(class_mapping_path)


def recognize(
    image: Image.Image,
    model_path: str,
    class_mapping_path: str | None,
    device: str = "cpu",
    top_k: int = 5,
) -> list[dict]:
    """
    对 PIL 图像进行识别，返回 [{"label": str, "score": float}, ...]。
    class_mapping_path 为 None 或不存在时，标签为 class_0, class_1 等。
    内部使用多模型缓存，按 model_path 区分。
    """
    model = load_model(model_path, class_mapping_path, device=device, top_k=top_k)
    class_mapping = _get_cached_mapping(model_path, class_mapping_path)
    img_tensor = _preprocess(image).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(img_tensor)
        probs = torch.softmax(logits, dim=1)
        num_classes = probs.size(1)
        k = min(top_k, num_classes)
        top_probs, top_indices = probs[0].topk(k)

    results = []
    for idx, prob in zip(top_indices.tolist(), top_probs.tolist()):
        label = class_mapping.get(str(idx), f"class_{idx}")
        results.append({"label": label, "score": round(float(prob), 4)})
    return results
