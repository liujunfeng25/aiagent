"""
百度表格文字识别 API：https://ai.baidu.com/ai-doc/OCR/Al1zvpylt
将图片 POST 到百度 rest/2.0/ocr/v1/table，解析为与前端一致的 structured 结构。
"""
import base64
import logging
import time
from pathlib import Path
from typing import Dict, List

import requests

from config import DOCUMENTS_BAIDU_TABLE_API_KEY

logger = logging.getLogger(__name__)

TABLE_API_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/table"
TIMEOUT = 60
# 偶发 SSLEOFError / 连接重置时重试（网络抖动、代理、本机杀软截 HTTPS）
MAX_CONNECT_ATTEMPTS = 4
CONNECT_RETRY_SLEEP_SEC = 0.7


def _build_grid_from_body(body: List[dict]) -> List[List[str]]:
    """根据 body 单元格的 row_start/row_end/col_start/col_end 构建二维表格。"""
    if not body:
        return []
    max_r = max(c.get("row_end", 0) for c in body)
    max_c = max(c.get("col_end", 0) for c in body)
    if max_r <= 0 or max_c <= 0:
        return []
    grid = [["" for _ in range(max_c)] for _ in range(max_r)]
    for c in body:
        words = (c.get("words") or "").strip()
        rs, re = c.get("row_start", 0), c.get("row_end", 0)
        cs, ce = c.get("col_start", 0), c.get("col_end", 0)
        for r in range(rs, min(re, max_r)):
            for col in range(cs, min(ce, max_c)):
                grid[r][col] = words
    return grid


def _table_result_to_structured(table: dict) -> dict:
    """单张表 tables_result 项 -> { headers, rows }。"""
    header_list = table.get("header") or []
    headers = [str(h.get("words") or "").strip() for h in header_list]
    body = table.get("body") or []
    grid = _build_grid_from_body(body)
    if not headers and grid:
        headers = [str(i) for i in range(len(grid[0]))]
    if headers and grid and len(grid[0]) != len(headers):
        nc = max(len(headers), len(grid[0]) if grid else 0)
        headers = (headers + [""] * nc)[:nc]
        grid = [list(row) + [""] * (nc - len(row)) for row in grid]
    return {"headers": headers, "rows": grid}


def run_baidu_table_ocr(image_path: Path) -> dict:
    """
    调用百度表格识别 API，返回 structured：
    { "tables": [ { "headers": [...], "rows": [[...], ...] } ], "key_values": [] }
    """
    if not DOCUMENTS_BAIDU_TABLE_API_KEY:
        raise ValueError(
            "未配置 DOCUMENTS_BAIDU_TABLE_API_KEY，请在环境变量或 .env 中设置百度 API Key（Bearer token）"
        )

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    body = {"image": img_b64}
    key = DOCUMENTS_BAIDU_TABLE_API_KEY.strip()
    headers_req: Dict[str, str] = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": key if key.lower().startswith("bearer ") else f"Bearer {key}",
    }

    resp: requests.Response | None = None
    for attempt in range(MAX_CONNECT_ATTEMPTS):
        try:
            resp = requests.post(TABLE_API_URL, data=body, headers=headers_req, timeout=TIMEOUT)
            resp.raise_for_status()
            break
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            last_err = e
            logger.warning(
                "百度表格 OCR 连接失败 (%s/%s): %s",
                attempt + 1,
                MAX_CONNECT_ATTEMPTS,
                e,
            )
            if attempt + 1 >= MAX_CONNECT_ATTEMPTS:
                raise RuntimeError(
                    "连接百度 OCR 失败（SSL 或网络中断）。请检查：本机网络与系统时间；是否需配置系统/"
                    "Python 代理；防火墙或杀毒是否拦截 HTTPS；稍后再试。原始错误："
                    + str(e)
                ) from e
            time.sleep(CONNECT_RETRY_SLEEP_SEC * (attempt + 1))
    assert resp is not None
    data = resp.json()
    if "error_code" in data and data.get("error_code"):
        raise RuntimeError(data.get("error_msg", "百度表格识别接口返回错误"))

    tables_result = data.get("tables_result") or []
    tables = []
    for t in tables_result:
        st = _table_result_to_structured(t)
        if st["headers"] or st["rows"]:
            tables.append(st)
    return {"tables": tables, "key_values": []}
