"""
票据识别：上传、OCR/表格识别、结构化输出、双单对比。
"""
import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.datastructures import FormData

try:
    from starlette.formparsers import MultiPartException
except ImportError:
    MultiPartException = None

from config import DOCUMENTS_BAIDU_TABLE_API_KEY, DOCUMENTS_OCR_ENGINE, DOCUMENTS_UPLOAD_DIR

from app.services.business_mysql import resolve_business_mysql
from app.services.document_order_compare import (
    DOC_KIND_DELIVERY,
    DOC_KIND_PROCUREMENT,
    DOC_KIND_RECEIPT,
    VALID_DOC_KINDS,
    run_compare,
)

logger = logging.getLogger(__name__)

RECOGNIZE_MAX_PART_SIZE = 20 * 1024 * 1024


async def get_recognize_form(request: Request) -> FormData:
    """解析 /recognize 的表单，允许单文件最大 20MB。"""
    try:
        form = await request.form(max_part_size=RECOGNIZE_MAX_PART_SIZE)
        return form
    except TypeError:
        try:
            return await request.form()
        except Exception as e2:
            logger.exception("get_recognize_form fallback failed: %s", e2)
            raise HTTPException(500, f"解析表单失败: {e2}")
    except Exception as e:
        logger.exception("get_recognize_form failed: %s", e)
        if MultiPartException and isinstance(e, MultiPartException):
            raise HTTPException(413, f"文件过大，请压缩或分张上传: {e}")
        raise HTTPException(500, f"解析上传失败: {type(e).__name__}: {e}")


router = APIRouter()


class CompareRule(BaseModel):
    match_key: str = "name"
    compare_fields: List[str] = ["quantity", "amount"]


class CompareRequest(BaseModel):
    doc_a: dict
    doc_b: dict
    rules: Optional[CompareRule] = None


class CompareItem(BaseModel):
    key: str
    field: str
    value_a: Any
    value_b: Any
    match: bool


class CompareResponse(BaseModel):
    matches: List[dict]
    diffs: List[CompareItem]
    summary: dict


class CompareOrderRequest(BaseModel):
    """OCR 结构化结果与业务库对账。"""

    structured: dict
    order_sn: Optional[str] = Field(
        default=None,
        description="送货/收货可选；若整串为 YYYY-MM-DD 会当作送货日期而非订单号。",
    )
    send_date: Optional[str] = Field(
        default=None,
        description="送货/收货可选 YYYY-MM-DD，与识别结果合并时本字段优先；手机号多条时用于收窄。",
    )
    goods_hints: Optional[List[str]] = Field(
        default=None,
        description="送货/收货可选：品名关键词列表，与识别表格品名合并后与订单明细比对以收窄多条候选。",
    )
    doc_kind: str = DOC_KIND_DELIVERY


@router.get("/engine")
def doc_engine_status():
    """当前 OCR 引擎与密钥是否就绪（便于前端提示「演示数据」与真实百度识别）。"""
    k = (DOCUMENTS_BAIDU_TABLE_API_KEY or "").strip()
    return {
        "ocr_engine": DOCUMENTS_OCR_ENGINE,
        "baidu_key_configured": bool(k),
        "using_mock_data": DOCUMENTS_OCR_ENGINE == "mock",
    }


def _mock_ocr(image_path: Path) -> dict:
    return {
        "tables": [
            {
                "headers": ["品名", "规格", "数量", "单位", "备注"],
                "rows": [
                    ["白菜", "箱", "100", "箱", ""],
                    ["萝卜", "斤", "50", "斤", ""],
                    ["土豆", "袋", "30", "袋", ""],
                ],
            }
        ],
        "key_values": [
            {"key": "单据类型", "value": "发货单"},
            {"key": "日期", "value": "2025-03-13"},
            {"key": "单号", "value": "FH20250313001"},
        ],
    }


def _structured_to_html(structured: dict) -> str:
    html_parts = []
    if structured.get("key_values"):
        html_parts.append("<table border='1' cellpadding='6' style='border-collapse:collapse'><tbody>")
        for kv in structured["key_values"]:
            html_parts.append(f"<tr><td><b>{kv['key']}</b></td><td>{kv['value']}</td></tr>")
        html_parts.append("</tbody></table>")
    if structured.get("tables"):
        for tbl in structured["tables"]:
            headers = tbl.get("headers", [])
            rows = tbl.get("rows", [])
            html_parts.append(
                "<table border='1' cellpadding='6' style='border-collapse:collapse;margin-top:12px'><thead><tr>"
            )
            for h in headers:
                html_parts.append(f"<th>{h}</th>")
            html_parts.append("</tr></thead><tbody>")
            for row in rows:
                html_parts.append("<tr>")
                for cell in row:
                    html_parts.append(f"<td>{cell}</td>")
                html_parts.append("</tr>")
            html_parts.append("</tbody></table>")
    return "\n".join(html_parts) if html_parts else "<p>无识别内容</p>"


def _run_recognize(image_path: Path) -> tuple[dict, str]:
    if DOCUMENTS_OCR_ENGINE == "baidu":
        try:
            from app.services.ocr_baidu import run_baidu_table_ocr

            structured = run_baidu_table_ocr(image_path)
        except Exception as e:
            logger.exception("百度表格识别失败: %s", e)
            raise
    elif DOCUMENTS_OCR_ENGINE == "paddle":
        logger.warning("Paddle 已移除，使用 mock。请设置 DOCUMENTS_OCR_ENGINE=baidu 并配置密钥。")
        structured = _mock_ocr(image_path)
    else:
        structured = _mock_ocr(image_path)
    html_snippet = _structured_to_html(structured)
    return structured, html_snippet


def _compare_docs(doc_a: dict, doc_b: dict, match_key: str, compare_fields: List[str]) -> CompareResponse:
    rows_a = []
    rows_b = []
    if doc_a.get("tables") and doc_a["tables"]:
        headers = doc_a["tables"][0].get("headers", [])
        try:
            name_idx = headers.index(match_key) if match_key in headers else 0
        except ValueError:
            name_idx = 0
        for row in doc_a["tables"][0].get("rows", []):
            key = row[name_idx] if name_idx < len(row) else ""
            rows_a.append({"key": key, "row": row, "headers": headers})
    if doc_b.get("tables") and doc_b["tables"]:
        headers = doc_b["tables"][0].get("headers", [])
        try:
            name_idx = headers.index(match_key) if match_key in headers else 0
        except ValueError:
            name_idx = 0
        for row in doc_b["tables"][0].get("rows", []):
            key = row[name_idx] if name_idx < len(row) else ""
            rows_b.append({"key": key, "row": row, "headers": headers})

    key_to_a = {r["key"]: r for r in rows_a}
    key_to_b = {r["key"]: r for r in rows_b}
    all_keys = sorted(set(key_to_a) | set(key_to_b))
    matches = []
    diffs: List[CompareItem] = []
    for key in all_keys:
        ra = key_to_a.get(key)
        rb = key_to_b.get(key)
        if not ra:
            matches.append(
                {
                    "key": key,
                    "in_a": False,
                    "in_b": True,
                    "row_b": rb["row"] if rb else [],
                    "headers_b": rb["headers"] if rb else [],
                }
            )
            continue
        if not rb:
            matches.append(
                {
                    "key": key,
                    "in_a": True,
                    "in_b": False,
                    "row_a": ra["row"],
                    "headers_a": ra["headers"],
                }
            )
            continue
        headers = ra["headers"]
        for field in compare_fields:
            if field not in headers:
                continue
            idx = headers.index(field)
            va = ra["row"][idx] if idx < len(ra["row"]) else ""
            vb = rb["row"][idx] if idx < len(rb["row"]) else ""
            if str(va).strip() != str(vb).strip():
                diffs.append(CompareItem(key=key, field=field, value_a=va, value_b=vb, match=False))
        matches.append(
            {
                "key": key,
                "in_a": True,
                "in_b": True,
                "row_a": ra["row"],
                "row_b": rb["row"],
                "headers_a": ra["headers"],
                "headers_b": rb["headers"],
            }
        )

    summary = {
        "total_keys": len(all_keys),
        "diff_count": len(diffs),
        "only_in_a": sum(1 for m in matches if m.get("in_a") and not m.get("in_b")),
        "only_in_b": sum(1 for m in matches if m.get("in_b") and not m.get("in_a")),
    }
    return CompareResponse(matches=matches, diffs=diffs, summary=summary)


async def _recognize_stream_gen(content: bytes, save_path: Path, image_id: str):
    def sse(event: str, data: Any):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {data}\n\n"

    try:
        yield sse("progress", "1/3 正在接收并保存文件…")
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(content)
        yield sse("progress", "2/3 正在识别票据内容（首次约 1～3 分钟，请勿刷新）…")

        loop = asyncio.get_event_loop()
        done = asyncio.Event()
        result_holder: List[tuple] = []
        exc_holder: List[Exception] = []

        def run_sync():
            try:
                out = _run_recognize(save_path)
                result_holder.append(out)
            except Exception as e:
                exc_holder.append(e)
            finally:
                done.set()

        task = loop.run_in_executor(None, run_sync)
        progress_interval = 15
        elapsed = 0
        while not done.is_set():
            await asyncio.wait(
                [asyncio.create_task(done.wait()), asyncio.create_task(asyncio.sleep(progress_interval))],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if done.is_set():
                break
            elapsed += progress_interval
            yield sse("progress", f"2/3 识别进行中… 已用时 {elapsed} 秒（请勿刷新）")
        await task
        if exc_holder:
            raise exc_holder[0]
        structured, html_snippet = result_holder[0]
        yield sse("progress", "3/3 识别完成")
        yield sse("result", {"structured": structured, "html_snippet": html_snippet, "image_id": image_id})
    except Exception as e:
        logger.exception("recognize stream error")
        yield sse("error", str(e))


@router.post("/recognize")
async def recognize(
    form_data: FormData = Depends(get_recognize_form),
    stream: bool = Query(False, description="流式返回进度（SSE）"),
):
    """上传票据图片，返回结构化数据与 HTML 片段。支持 stream=1。"""
    try:
        return await _do_recognize(form_data, stream)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("recognize unhandled: %s", e)
        raise HTTPException(500, f"识别异常: {type(e).__name__}: {e}")


async def _do_recognize(form_data: FormData, stream: bool):
    file = form_data.get("file")
    if isinstance(file, list):
        file = file[0] if file else None
    if not file or not getattr(file, "read", None):
        raise HTTPException(400, "请上传图片文件（字段名须为 file）")
    fn = (file.filename or "").lower()
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件（如 jpg、png）")
    if not fn or not any(fn.endswith(s) for s in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
        if file.content_type:
            raise HTTPException(400, "请上传图片文件（如 jpg、png）")
    ext = Path(file.filename or "img").suffix or ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    try:
        DOCUMENTS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        save_path = DOCUMENTS_UPLOAD_DIR / name
    except Exception as e:
        logger.exception("mkdir upload dir")
        raise HTTPException(500, f"创建上传目录失败: {e}")

    if stream:
        try:
            content = await file.read()
        except Exception as e:
            logger.exception("read upload file")
            raise HTTPException(500, f"读取上传文件失败: {e}")
        return StreamingResponse(
            _recognize_stream_gen(content, save_path, name),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        content = await file.read()
        save_path.write_bytes(content)
    except Exception as e:
        logger.exception("save file: %s", e)
        raise HTTPException(500, f"保存文件失败: {e}")
    try:
        structured, html_snippet = _run_recognize(save_path)
        return {"structured": structured, "html_snippet": html_snippet, "image_id": name}
    except Exception as e:
        logger.exception("recognize: %s", e)
        raise HTTPException(500, f"识别失败: {type(e).__name__}: {e}")


@router.post("/compare", response_model=CompareResponse)
async def compare(body: CompareRequest):
    """发货单 vs 收货单对比。"""
    rules = body.rules or CompareRule()
    return _compare_docs(
        body.doc_a,
        body.doc_b,
        match_key=rules.match_key,
        compare_fields=rules.compare_fields,
    )


@router.get("/compare-order/doc-kinds")
def compare_order_doc_kinds():
    """前端下拉：单据类型与对应业务表说明。"""
    return {
        "kinds": [
            {
                "value": DOC_KIND_DELIVERY,
                "label": "送货单（销售出货）",
                "table": "orders + orders_items",
            },
            {
                "value": DOC_KIND_RECEIPT,
                "label": "收货单（客户签收回单）",
                "table": "orders + orders_items（与送货同源）",
            },
            {
                "value": DOC_KIND_PROCUREMENT,
                "label": "采购/入库单",
                "table": "procurement_orders + procurement_orders_items",
            },
        ]
    }


@router.post("/compare-order")
def compare_order_with_db(body: CompareOrderRequest):
    """
    将百度/识别得到的 structured 与业务库对账。
    未配置业务库时仍返回 200，ok=false，便于前端仅提示不报错。
    """
    kind = (body.doc_kind or DOC_KIND_DELIVERY).strip().lower()
    if kind not in VALID_DOC_KINDS:
        raise HTTPException(400, f"doc_kind 无效，可选：{', '.join(sorted(VALID_DOC_KINDS))}")
    cfg = resolve_business_mysql()
    return run_compare(cfg, body.structured, body.order_sn, kind, body.send_date, body.goods_hints)
