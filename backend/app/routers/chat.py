"""AI 业务分析助手路由。

- POST /api/chat                 主对话（两阶段：planner → answerer with tools）
- POST /api/chat/report/export   Markdown → .docx 下载
- GET  /api/chat/catalog         查看缓存摘要
- POST /api/chat/catalog/refresh 连得上真实业务库时抓一次样例落盘
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import timedelta
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.ai_chat import llm_client
from app.services.ai_chat.business_date import business_today
from app.services.ai_chat.prompt import build_system_prompt, planner_prompt
from app.services.ai_chat.report import (
    markdown_to_docx_bytes,
    markdown_to_md_bytes,
    markdown_to_pptx_bytes,
)
from app.services.ai_chat.schema_catalog import (
    get_catalog_summary,
    refresh_catalog,
)
from app.services.ai_chat.session import MAX_TURNS, append, get_history, set_history
from app.services.ai_chat.tools import TOOLS, dispatch_tool_call, tool_result_content

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str = ""


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    session_id: Optional[str] = None


class ExportRequest(BaseModel):
    title: Optional[str] = None
    markdown: str
    filename: Optional[str] = None
    format: Optional[str] = None  # docx | pptx | md（缺省 docx）


# ---------------------------------------------------------------------------
# 解析 data_card / report_content
# ---------------------------------------------------------------------------

_DATA_CARD_RE = re.compile(r"<data_card>\s*(\{.*?\})\s*</data_card>", re.DOTALL)
_REPORT_RE = re.compile(r"<report_content>\s*([\s\S]*?)\s*</report_content>", re.DOTALL)


def _extract_artifacts(text: str) -> tuple[str, Optional[dict[str, Any]], Optional[str]]:
    """剥离 <data_card>/<report_content>；返回 (可读文本, data_card_dict, report_md)。

    前端会单独渲染卡片，因此 reply 文本中保留标签没问题；
    同时也给一份结构化字段方便直接用。
    """
    data_card = None
    m = _DATA_CARD_RE.search(text or "")
    if m:
        try:
            data_card = json.loads(m.group(1))
        except Exception:
            data_card = None
    report_md = None
    m2 = _REPORT_RE.search(text or "")
    if m2:
        report_md = m2.group(1).strip()
    return text or "", data_card, report_md


def _requested_export_formats_from_text(text: str) -> list[str]:
    """默认仅 docx；仅当用户明确提到格式时，返回对应格式。"""
    t = str(text or "").lower()
    formats: list[str] = []
    if any(k in t for k in ("pptx", "ppt", "powerpoint")):
        formats.append("pptx")
    if any(k in t for k in ("markdown", ".md", " md ")):
        formats.append("md")
    if any(k in t for k in ("docx", "word", "文档", "word版")):
        formats.append("docx")
    # 未明确指定时，默认仅 Word
    return formats or ["docx"]


def _fast_report_args_from_text(text: str) -> Optional[dict[str, Any]]:
    """日报/周报/月报快速直达：减少模型绕路和误判。"""
    t = str(text or "").strip()
    if not t:
        return None
    # 仅覆盖高频结构化报表；企划案/简报仍走 LLM 深度分析链路
    report_type = None
    if "周报" in t:
        report_type = "weekly"
    elif "月报" in t:
        report_type = "monthly"
    elif "日报" in t:
        report_type = "daily"
    if not report_type:
        return None

    today = business_today()
    base = today
    if any(k in t for k in ("前天",)):
        base = today - timedelta(days=2)
    elif any(k in t for k in ("昨天", "昨日", "昨")):
        base = today - timedelta(days=1)
    elif any(k in t for k in ("上周",)):
        base = today - timedelta(days=7)

    return {"report_type": report_type, "date": base.isoformat()}


def _fast_chart_query_from_text(text: str) -> Optional[tuple[str, dict[str, Any]]]:
    """折线图快速通道：避免模型输出 JSON 文本而不出图。"""
    t = str(text or "").strip()
    if not t:
        return None
    low = t.lower()
    wants_line = any(k in t for k in ("折线图", "曲线", "走势", "趋势图")) or "line chart" in low
    wants_gmv = any(k in low for k in ("gmv", "销售额", "成交额"))
    if not (wants_line and wants_gmv):
        return None

    # 最近N天（含今天）
    m = re.search(r"最近\s*(\d{1,3})\s*天", t)
    days = 7
    if m:
        try:
            days = max(2, min(60, int(m.group(1))))
        except Exception:
            days = 7
    today = business_today()
    start = today - timedelta(days=days - 1)
    return (
        "get_daily_trend",
        {
            "start_date": start.isoformat(),
            "end_date": today.isoformat(),
        },
    )


def _fast_schema_query_from_text(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return False
    return any(k in t for k in ("能查什么", "查哪些", "数据覆盖", "有哪些表", "schema", "表结构", "数据范围"))


def _infer_range_from_text(text: str) -> tuple[str, str]:
    """从自然语言推断时间窗口（含今天）。"""
    t = str(text or "")
    today = business_today()
    if any(k in t for k in ("今天", "今日", "当日")):
        return today.isoformat(), today.isoformat()
    if any(k in t for k in ("昨天", "昨日", "昨")):
        d = today - timedelta(days=1)
        return d.isoformat(), d.isoformat()
    if "前天" in t:
        d = today - timedelta(days=2)
        return d.isoformat(), d.isoformat()
    if any(k in t for k in ("本周", "近7天", "近 7 天", "最近一周")):
        return (today - timedelta(days=6)).isoformat(), today.isoformat()
    if any(k in t for k in ("本月", "这个月", "月度")):
        return today.replace(day=1).isoformat(), today.isoformat()
    if any(k in t for k in ("今年", "本年", "本年度")):
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    # 默认近30天
    return (today - timedelta(days=29)).isoformat(), today.isoformat()


def _fast_pie_query_from_text(text: str) -> Optional[tuple[str, dict[str, Any], int]]:
    """TopN 饼图分布快速通道。"""
    t = str(text or "")
    low = t.lower()
    wants_pie = any(k in t for k in ("饼图", "占比图", "分布图", "占比", "分布")) or "pie" in low
    wants_top = bool(re.search(r"top\s*\d+", low)) or "topn" in low or "前" in t
    if not wants_pie:
        return None
    # topn 默认 10
    n = 10
    m = re.search(r"top\s*(\d{1,2})", low)
    if m:
        try:
            n = max(3, min(20, int(m.group(1))))
        except Exception:
            n = 10
    m2 = re.search(r"前\s*(\d{1,2})", t)
    if m2:
        try:
            n = max(3, min(20, int(m2.group(1))))
        except Exception:
            n = n
    if not wants_top and "排行" not in t and "排名" not in t:
        # 没提 top/排行，默认也给 top10 分布
        n = 10

    start, end = _infer_range_from_text(t)
    # 维度识别：区域 or 品类
    if any(k in t for k in ("区域", "区县", "城区", "地区")):
        return ("get_region_rank", {"start_date": start, "end_date": end, "limit": n}, n)
    # 默认走品类分布（最常见“topn饼图分布”）
    return ("get_category_distribution", {"start_date": start, "end_date": end, "limit": n}, n)


def _eta_bounds() -> dict[str, tuple[int, int]]:
    """启发式预计耗时区间（秒），可通过环境变量微调。"""
    return {
        "fast": (
            int(os.environ.get("ASSISTANT_ETA_FAST_MIN", "5")),
            int(os.environ.get("ASSISTANT_ETA_FAST_MAX", "20")),
        ),
        "report": (
            int(os.environ.get("ASSISTANT_ETA_REPORT_MIN", "15")),
            int(os.environ.get("ASSISTANT_ETA_REPORT_MAX", "60")),
        ),
        "normal": (
            int(os.environ.get("ASSISTANT_ETA_NORMAL_MIN", "20")),
            int(os.environ.get("ASSISTANT_ETA_NORMAL_MAX", "90")),
        ),
        "deep": (
            int(os.environ.get("ASSISTANT_ETA_DEEP_MIN", "45")),
            int(os.environ.get("ASSISTANT_ETA_DEEP_MAX", "120")),
        ),
    }


def _estimate_run_profile(
    user_text: str,
    *,
    fast_chart: bool = False,
    fast_pie: bool = False,
    fast_schema: bool = False,
    fast_report_args: Optional[dict[str, Any]] = None,
    intent: Optional[dict[str, Any]] = None,
    already_clarifying: bool = False,
) -> dict[str, Any]:
    """根据快速通道 / Planner 意图给出档位与 ETA 区间（仅供参考）。"""
    b = _eta_bounds()
    t = str(user_text or "")

    if intent is not None:
        it = str((intent or {}).get("intent") or "")
        if (
            (intent or {}).get("needClarify")
            and (intent or {}).get("clarifyQuestion")
            and not already_clarifying
        ):
            mn, mx = 3, 15
            return {
                "tier": "fast",
                "eta_sec_min": mn,
                "eta_sec_max": mx,
                "hint": f"预计约 {mn}–{mx} 秒（仅供参考），待确认维度后很快返回。",
            }
        if it in ("proposal_report", "insight_brief"):
            mn, mx = b["deep"]
            return {
                "tier": "deep",
                "eta_sec_min": mn,
                "eta_sec_max": mx,
                "hint": f"预计约 {mn}–{mx} 秒（仅供参考），长文分析需多源取数与整理。",
            }
        if it in ("daily_report", "weekly_report", "monthly_report"):
            mn, mx = b["report"]
            return {
                "tier": "report",
                "eta_sec_min": mn,
                "eta_sec_max": mx,
                "hint": f"预计约 {mn}–{mx} 秒（仅供参考），报表类查询与拼装。",
            }
        mn, mx = b["normal"]
        return {
            "tier": "normal",
            "eta_sec_min": mn,
            "eta_sec_max": mx,
            "hint": f"预计约 {mn}–{mx} 秒（仅供参考），正在查询与组织回答。",
        }

    if fast_chart or fast_pie or fast_schema:
        mn, mx = b["fast"]
        return {
            "tier": "fast",
            "eta_sec_min": mn,
            "eta_sec_max": mx,
            "hint": f"预计约 {mn}–{mx} 秒（仅供参考），结构化查询较快。",
        }
    if fast_report_args:
        mn, mx = b["report"]
        return {
            "tier": "report",
            "eta_sec_min": mn,
            "eta_sec_max": mx,
            "hint": f"预计约 {mn}–{mx} 秒（仅供参考），正在生成报表数据。",
        }
    deep_kw = ("企划案", "策划案", "营销方案", "提案", "经营简报", "复盘", "经营分析", "月度总结", "总结一下")
    if any(k in t for k in deep_kw):
        mn, mx = b["deep"]
        return {
            "tier": "deep",
            "eta_sec_min": mn,
            "eta_sec_max": mx,
            "hint": f"预计约 {mn}–{mx} 秒（仅供参考），综合分析与取数。",
        }
    mn, mx = b["normal"]
    return {
        "tier": "normal",
        "eta_sec_min": mn,
        "eta_sec_max": mx,
        "hint": f"预计约 {mn}–{mx} 秒（仅供参考），正在识别意图并查询数据。",
    }


def _attach_server_elapsed(payload: dict[str, Any], t0: float) -> dict[str, Any]:
    out = dict(payload)
    out["server_elapsed_ms"] = max(0, int((time.perf_counter() - t0) * 1000))
    return out


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

@router.post("")
async def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    t_req = time.perf_counter()
    cfg = llm_client.get_config()
    session_id = req.session_id or uuid.uuid4().hex
    in_msgs = [m.model_dump() for m in req.messages if m.content or m.role == "tool"]
    if not in_msgs:
        raise HTTPException(400, "messages 不能为空")

    # 合并内存里的历史（前端断线时兜底）
    history = get_history(session_id)
    merged_user_assistant = (history + in_msgs)[-(MAX_TURNS * 2):]
    # 把最后一条用户消息单独留存历史
    last_user = next((m for m in reversed(in_msgs) if m.get("role") == "user"), None)
    user_text = str((last_user or {}).get("content") or "")
    export_formats = _requested_export_formats_from_text((last_user or {}).get("content") or "")
    fast_report_args = _fast_report_args_from_text(user_text)
    fast_chart = _fast_chart_query_from_text(user_text)
    fast_schema = _fast_schema_query_from_text(user_text)
    fast_pie = _fast_pie_query_from_text(user_text)

    system_prompt = build_system_prompt()
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    msgs.extend(merged_user_assistant)

    # 图表高频指令直达：直接返回可视化 data_card，避免“只吐 JSON 文本”
    if fast_chart:
        tool_name, tool_args = fast_chart
        tool_result = await dispatch_tool_call(tool_name, tool_args)
        reply_text, data_card, report_md = _direct_data_card_reply(
            tool_name, tool_result if isinstance(tool_result, dict) else {}
        )
        if reply_text:
            _persist_turn(session_id, last_user, reply_text)
            debug = {
                "mock": cfg.is_mock,
                "intent": {"intent": "trend_chart", "fast_path": True},
                "already_clarifying": False,
                "tool_calls": [{"name": tool_name, "args": tool_args, "result_preview": _preview(tool_result)}],
            }
            return _attach_server_elapsed(
                {
                    "reply": reply_text,
                    "data_card": data_card,
                    "report_content": report_md,
                    "export_formats": export_formats,
                    "session_id": session_id,
                    "debug": debug,
                },
                t_req,
            )

    if fast_pie:
        tool_name, tool_args, topn = fast_pie
        tool_result = await dispatch_tool_call(tool_name, tool_args)
        reply_text, data_card, report_md = _direct_pie_card_reply(
            tool_name, tool_result if isinstance(tool_result, dict) else {}, topn
        )
        if reply_text:
            _persist_turn(session_id, last_user, reply_text)
            debug = {
                "mock": cfg.is_mock,
                "intent": {"intent": "topn_pie", "fast_path": True},
                "already_clarifying": False,
                "tool_calls": [{"name": tool_name, "args": tool_args, "result_preview": _preview(tool_result)}],
            }
            return _attach_server_elapsed(
                {
                    "reply": reply_text,
                    "data_card": data_card,
                    "report_content": report_md,
                    "export_formats": export_formats,
                    "session_id": session_id,
                    "debug": debug,
                },
                t_req,
            )

    if fast_schema:
        tool_result = await dispatch_tool_call("get_schema_overview", {})
        reply_text, data_card, report_md = _direct_schema_reply(tool_result if isinstance(tool_result, dict) else {})
        _persist_turn(session_id, last_user, reply_text)
        debug = {
            "mock": cfg.is_mock,
            "intent": {"intent": "schema_overview", "fast_path": True},
            "already_clarifying": False,
            "tool_calls": [{"name": "get_schema_overview", "args": {}, "result_preview": _preview(tool_result)}],
        }
        return _attach_server_elapsed(
            {
                "reply": reply_text,
                "data_card": data_card,
                "report_content": report_md,
                "export_formats": export_formats,
                "session_id": session_id,
                "debug": debug,
            },
            t_req,
        )

    # 报表高频指令直达（日报/周报/月报）：跳过 planner/answerer，稳定且更快
    if fast_report_args:
        tool_result = await dispatch_tool_call("generate_report", fast_report_args)
        reply_text, data_card, report_md = _direct_report_reply(tool_result if isinstance(tool_result, dict) else {})
        if reply_text:
            _persist_turn(session_id, last_user, reply_text)
            debug = {
                "mock": cfg.is_mock,
                "intent": {"intent": f"{fast_report_args.get('report_type')}_report", "fast_path": True},
                "already_clarifying": False,
                "tool_calls": [{"name": "generate_report", "args": fast_report_args, "result_preview": _preview(tool_result)}],
            }
            return _attach_server_elapsed(
                {
                    "reply": reply_text,
                    "data_card": data_card,
                    "report_content": report_md,
                    "export_formats": export_formats,
                    "session_id": session_id,
                    "debug": debug,
                },
                t_req,
            )

    # 两段式：planner → answer with tools
    debug: dict[str, Any] = {"mock": cfg.is_mock, "tool_calls": []}
    intent = await _run_planner(merged_user_assistant)
    debug["intent"] = intent

    # 二次反问熔断：若上一条 assistant 已经是反问（问号结尾），当前用户消息一律视作答复，
    # 强制跳过 planner 的 clarifyBranch，直接让 answerer 带 tools 接手多轮推进。
    last_assistant = next(
        (m for m in reversed(merged_user_assistant) if m.get("role") == "assistant"),
        None,
    )
    already_clarifying = bool(last_assistant and _is_clarifying_question(last_assistant))
    debug["already_clarifying"] = already_clarifying

    if intent.get("needClarify") and intent.get("clarifyQuestion") and not already_clarifying:
        clarify = str(intent.get("clarifyQuestion")).strip() or "为了更准确回答，请明确时间/区域/品类。"
        _persist_turn(session_id, last_user, clarify)
        return _attach_server_elapsed(
            {
                "reply": clarify,
                "data_card": None,
                "report_content": None,
                "export_formats": export_formats,
                "session_id": session_id,
                "debug": debug,
            },
            t_req,
        )

    reply_text, data_card, report_md, tool_trace = await _run_with_tools(msgs)
    debug["tool_calls"] = tool_trace

    _persist_turn(session_id, last_user, reply_text)
    return _attach_server_elapsed(
        {
            "reply": reply_text,
            "data_card": data_card,
            "report_content": report_md,
            "export_formats": export_formats,
            "session_id": session_id,
            "debug": debug,
        },
        t_req,
    )


def _persist_turn(session_id: str, last_user: Optional[dict[str, Any]], reply_text: str) -> None:
    if not session_id:
        return
    if last_user and last_user.get("content"):
        append(session_id, "user", str(last_user.get("content")))
    if reply_text:
        append(session_id, "assistant", reply_text)


def _is_clarifying_question(msg: dict[str, Any]) -> bool:
    """判断 assistant 这条是否以问号结尾（代表在等用户澄清）。"""
    c = str(msg.get("content") or "").rstrip()
    return c.endswith(("?", "？"))


def _history_for_planner(history: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    """裁剪给 planner 的上下文：只取 user/assistant，最多 limit 条，过滤 tool_calls 字段。"""
    flat = [m for m in history if m.get("role") in ("user", "assistant")]
    pruned: list[dict[str, Any]] = []
    for m in flat[-limit:]:
        pruned.append({"role": m.get("role"), "content": str(m.get("content") or "")})
    return pruned


async def _run_planner(history: list[dict[str, Any]]) -> dict[str, Any]:
    """让 planner 产出 intent JSON。会吃最近 6 条 user/assistant 历史，解决「合并的」这种
    回指性极强的短句被当成孤零零新问题的问题。失败时返回一个默认 intent。"""
    plan_history = _history_for_planner(history, limit=6)
    if not plan_history:
        return {"intent": "unknown", "needClarify": False}
    cfg = llm_client.get_config()
    plan_msgs: list[dict[str, Any]] = [
        {"role": "system", "content": planner_prompt()}
    ]
    plan_msgs.extend(plan_history)
    try:
        resp = llm_client.chat_completion(
            messages=plan_msgs,
            model=cfg.model_planner,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
        intent = json.loads(content)
        if isinstance(intent, dict):
            return intent
    except Exception as e:
        logger.warning("planner 解析失败：%s", e)
    return {"intent": "unknown", "needClarify": False}


MAX_TOOL_ROUNDS = 5


async def _run_with_tools(msgs: list[dict[str, Any]]) -> tuple[str, Optional[dict], Optional[str], list[dict[str, Any]]]:
    """answerer：带 tools 的多轮 FC；回到 finish_reason=stop 或达到上限后结束。"""
    cfg = llm_client.get_config()
    tool_trace: list[dict[str, Any]] = []

    round_i = 0
    while round_i < MAX_TOOL_ROUNDS:
        round_i += 1
        resp = llm_client.chat_completion(
            messages=msgs,
            model=cfg.model_answer,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )
        choices = resp.get("choices") or []
        if not choices:
            break
        message = choices[0].get("message") or {}
        finish_reason = choices[0].get("finish_reason")
        tool_calls = message.get("tool_calls")

        if tool_calls:
            # 把 assistant 的 tool_calls 消息入历史
            msgs.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )
            for tc in tool_calls:
                fn = (tc.get("function") or {})
                name = fn.get("name") or ""
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                result = await dispatch_tool_call(name, args)
                tool_trace.append({"name": name, "args": args, "result_preview": _preview(result)})
                if name == "generate_report":
                    reply, card, report_md = _direct_report_reply(result if isinstance(result, dict) else {})
                    if reply:
                        return reply, card, report_md, tool_trace
                # 高频单工具查询直出卡片，提升美观和速度
                if len(tool_calls) == 1:
                    reply, card, report_md = _direct_data_card_reply(
                        name,
                        result if isinstance(result, dict) else {},
                    )
                    if reply:
                        return reply, card, report_md, tool_trace
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id") or "",
                        "name": name,
                        "content": tool_result_content(result),
                    }
                )
            continue

        text = message.get("content") or ""
        reply, card, report_md = _extract_artifacts(text)
        return reply, card, report_md, tool_trace

    return ("抱歉，工具调用超过次数上限。", None, None, tool_trace)


def _preview(obj: Any) -> Any:
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    return s if len(s) <= 300 else s[:300] + "…"


def _direct_report_reply(tool_result: dict[str, Any]) -> tuple[str, Optional[dict], Optional[str]]:
    """对 generate_report 走快速直出：拿到 markdown 后直接返回，跳过二次 answerer 长生成。"""
    if not isinstance(tool_result, dict):
        return ("", None, None)
    md = str(tool_result.get("markdown") or "").strip()
    if not md and str(tool_result.get("report_type") or "") in ("proposal", "insight_brief"):
        md = _build_analytical_markdown(tool_result)
    if not md:
        return ("", None, None)
    title = str(tool_result.get("title") or "业务报告").strip() or "业务报告"
    prefix = f"已为您生成 {title}，可在右上角下载报告文件。"
    reply = f"{prefix}\n<report_content>{md}</report_content>"
    return reply, None, md


def _build_analytical_markdown(report_result: dict[str, Any]) -> str:
    """proposal/insight_brief 快速成稿（基于 data_pack），避免分钟级等待。"""
    rt = str(report_result.get("report_type") or "")
    title = str(report_result.get("title") or "经营分析报告").strip() or "经营分析报告"
    dp = report_result.get("data_pack") or {}
    kpi = dp.get("kpi") or {}
    regions = (dp.get("regions") or {}).get("key_districts") or []
    cat = (dp.get("category_distribution") or {}).get("rows") or []
    trend = (dp.get("trend_daily") or {}).get("series") or []
    alerts = dp.get("ops_alerts") or {}
    xinfadi = dp.get("xinfadi_price") or {}

    top_region = regions[0] if isinstance(regions, list) and regions else {}
    top_cat = cat[0] if isinstance(cat, list) and cat else {}
    latest_trend = trend[-1] if isinstance(trend, list) and trend else {}
    latest_price = (xinfadi.get("series") or [])
    latest_price = latest_price[-1] if isinstance(latest_price, list) and latest_price else {}
    ret_pending = (alerts.get("return_pending") or {}).get("count")
    pending_dis = (alerts.get("supplement_today") or {}).get("pending_disorder_count")

    lines: list[str] = [f"# {title}", ""]
    lines.append("## 一、经营摘要")
    lines.append(
        f"- GMV：{_fmt_money(kpi.get('gmv'))}，订单数：{_to_int(kpi.get('order_count')):,}，客单价：{_fmt_money(kpi.get('avg_ticket'))}。"
    )
    if top_region:
        lines.append(
            f"- 区域表现：榜首为 **{top_region.get('district_name', '—')}**，GMV {_fmt_money(top_region.get('gmv'))}。"
        )
    if top_cat:
        lines.append(
            f"- 品类表现：当前头部品类为 **{top_cat.get('category_name', '—')}**，金额 {_fmt_money(top_cat.get('line_gmv') or top_cat.get('gmv'))}。"
        )
    if latest_trend:
        lines.append(
            f"- 最近交易日（{latest_trend.get('day', '—')}）：GMV {_fmt_money(latest_trend.get('gmv'))}，订单 {_to_int(latest_trend.get('order_count')):,}。"
        )
    lines.append("")

    lines.append("## 二、关键风险与机会")
    lines.append(
        f"- 运营风险：待处理退货 **{_to_int(ret_pending):,}** 笔，待补单/分拣 **{_to_int(pending_dis):,}** 笔。"
    )
    if latest_price:
        lines.append(
            f"- 外部行情：最新均价约 ¥{_to_float(latest_price.get('avg_price')):,.0f}/吨（区间 ¥{_to_float(latest_price.get('min_price')):,.0f}~¥{_to_float(latest_price.get('max_price')):,.0f}）。"
        )
    lines.append("- 机会点：继续放大头部区域与头部品类，同时监控退货与补单链路。")
    lines.append("")

    if rt == "proposal":
        lines.append("## 三、策略动作（企划案）")
        lines.append("- 动作1：围绕头部区域拓展重点单位客户（机关/学校/医院），提升稳定采购规模。")
        lines.append("- 动作2：针对头部品类优化集采清单与档口供给组合，提高履约稳定性与品类覆盖。")
        lines.append("- 动作3：对高退货品项建立履约预警阈值，联动仓配与质控降低异常损耗。")
        lines.append("")
        lines.append("## 四、资源与排期")
        lines.append("- 周期：建议 2-4 周；第1周准备，第2-3周执行，第4周复盘。")
        lines.append("- 资源：运营、供应链、区域政企BD与履约团队协同推进。")
    else:
        lines.append("## 三、行动建议（经营简报）")
        lines.append("- 短期（本周）：聚焦高潜区域单位客户，压降退货与补单，保障履约稳定。")
        lines.append("- 中期（本月）：围绕头部品类优化集采结构，稳定毛利与采购频次。")
        lines.append("- 复盘：按周跟踪 GMV、退货率、补单率。")

    return "\n".join(lines)


def _direct_schema_reply(tool_result: dict[str, Any]) -> tuple[str, Optional[dict], Optional[str]]:
    rows = tool_result.get("rows") if isinstance(tool_result, dict) else None
    if not isinstance(rows, list):
        rows = []
    if not rows:
        return ("当前数据目录暂不可用，我已记录你的需求；你可以先问销售/区域/品类/趋势/报告类问题。", None, None)
    names = []
    for r in rows[:12]:
        if isinstance(r, dict):
            n = r.get("table_name") or r.get("name") or r.get("table")
            if n:
                names.append(str(n))
    covered = "、".join(names[:8]) if names else "订单/品类/区域/趋势等"
    reply = f"我当前已接入的业务数据覆盖表包括：{covered} 等。你可以继续问：KPI、TOP排行、趋势图、日报/周报/月报、企划案。"
    return (reply, None, None)


def _direct_pie_card_reply(
    tool_name: str,
    tool_result: dict[str, Any],
    topn: int,
) -> tuple[str, Optional[dict], Optional[str]]:
    rows_src = tool_result.get("rows") or tool_result.get("key_districts") or []
    if not isinstance(rows_src, list) or not rows_src:
        return ("", None, None)

    def _name_of(r: dict[str, Any]) -> str:
        for k in ("category_name", "district_name", "goods_name", "name"):
            if r.get(k):
                return str(r.get(k))
        return "—"

    def _value_of(r: dict[str, Any]) -> float:
        for k in ("line_gmv", "gmv", "total_amount", "amount", "amount_sum"):
            if r.get(k) is not None:
                return _to_float(r.get(k))
        return 0.0

    picked = rows_src[: max(3, min(20, topn))]
    vals = [_value_of(r if isinstance(r, dict) else {}) for r in picked]
    total = sum(vals) if vals else 0.0
    maxv = max(vals) if vals else 1.0
    maxv = maxv if maxv > 0 else 1.0

    rows = []
    pie_data = []
    for i, r in enumerate(picked, start=1):
        rr = r if isinstance(r, dict) else {}
        n = _name_of(rr)
        v = _value_of(rr)
        pie_data.append({"name": n, "value": round(v, 2)})
        rows.append(
            {
                "rank": i,
                "name": n,
                "value": _fmt_money(v),
                "bar": round(100.0 * v / maxv, 1),
            }
        )

    title = "TOP分布饼图"
    if tool_name == "get_category_distribution":
        title = f"品类TOP{len(rows)}占比"
    elif tool_name == "get_region_rank":
        title = f"区域TOP{len(rows)}占比"

    card = {
        "type": "chart",
        "title": title,
        "kpis": [
            {"label": "上榜数量", "value": str(len(rows))},
            {"label": "合计金额", "value": _fmt_money(total)},
            {"label": "榜首", "value": rows[0]["name"] if rows else "—"},
        ],
        "chart": {
            "kind": "pie",
            "series": [{"name": "金额占比", "data": pie_data}],
        },
        "rows": rows,
    }
    reply = f"已为你整理 {title}。"
    return (f"{reply}\n<data_card>{json.dumps(card, ensure_ascii=False)}</data_card>", card, None)


def _to_float(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _to_int(v: Any) -> int:
    try:
        return int(float(v or 0))
    except Exception:
        return 0


def _fmt_money(v: Any) -> str:
    n = _to_float(v)
    if n >= 100000000:
        return f"¥{n/100000000:.2f}亿"
    if n >= 10000:
        return f"¥{n/10000:.1f}万"
    return f"¥{n:,.0f}"


def _direct_data_card_reply(
    tool_name: str, tool_result: dict[str, Any]
) -> tuple[str, Optional[dict], Optional[str]]:
    """常见单工具问答直出 data_card，避免模型把结果吐成原始表格。"""
    if not isinstance(tool_result, dict):
        return ("", None, None)

    if tool_name in ("get_kpi_summary", "get_intraday_gmv"):
        gmv = tool_result.get("gmv")
        if gmv is None:
            gmv = ((tool_result.get("summary") or {}) if isinstance(tool_result.get("summary"), dict) else {}).get("gmv")
        order_count = tool_result.get("order_count")
        if order_count is None:
            order_count = ((tool_result.get("summary") or {}) if isinstance(tool_result.get("summary"), dict) else {}).get("order_count")
        avg_ticket = tool_result.get("avg_ticket")
        card = {
            "type": "kpi",
            "title": "核心指标",
            "kpis": [
                {"label": "GMV", "value": _fmt_money(gmv)},
                {"label": "订单数", "value": f"{_to_int(order_count):,}"},
                {"label": "客单价", "value": _fmt_money(avg_ticket)},
            ],
            "rows": [],
        }
        reply = "已为你整理核心指标。"
        return (
            f"{reply}\n<data_card>{json.dumps(card, ensure_ascii=False)}</data_card>",
            card,
            None,
        )

    if tool_name in ("get_top_goods", "get_top_members", "get_region_rank", "get_category_distribution"):
        src_rows = tool_result.get("rows") or tool_result.get("key_districts") or []
        if not isinstance(src_rows, list) or not src_rows:
            return ("", None, None)

        def _name_of(r: dict[str, Any]) -> str:
            for k in ("goods_name", "member_name", "district_name", "category_name", "name"):
                if r.get(k):
                    return str(r.get(k))
            return "—"

        def _value_of(r: dict[str, Any]) -> float:
            for k in (
                "line_gmv",
                "total_amount",
                "gmv",
                "amount",
                "amount_sum",
                "sales_amount",
                "line_amount",
            ):
                if r.get(k) is not None:
                    return _to_float(r.get(k))
            return 0.0

        vals = [_value_of(r if isinstance(r, dict) else {}) for r in src_rows[:10]]
        maxv = max(vals) if vals else 1.0
        maxv = maxv if maxv > 0 else 1.0
        rows = []
        for i, r in enumerate(src_rows[:10], start=1):
            rr = r if isinstance(r, dict) else {}
            v = _value_of(rr)
            trend = rr.get("mom_pct")
            rows.append(
                {
                    "rank": i,
                    "name": _name_of(rr),
                    "value": _fmt_money(v),
                    "trend": (f"{_to_float(trend):+,.1f}%") if trend is not None else "",
                    "bar": round(100.0 * v / maxv, 1),
                }
            )
        total = sum(vals)
        title = {
            "get_top_goods": "品类销售 TOP10",
            "get_top_members": "客户成交 TOP10",
            "get_region_rank": "区域销售 TOP10",
            "get_category_distribution": "品类分布 TOP10",
        }.get(tool_name, "排行结果")
        card = {
            "type": "rank",
            "title": title,
            "kpis": [
                {"label": "上榜数量", "value": str(len(rows))},
                {"label": "合计金额", "value": _fmt_money(total)},
                {"label": "榜首", "value": rows[0]["name"] if rows else "—"},
            ],
            "rows": rows,
        }
        return (
            f"已为你整理 {title}。\n<data_card>{json.dumps(card, ensure_ascii=False)}</data_card>",
            card,
            None,
        )

    if tool_name == "get_daily_trend":
        series = tool_result.get("series") or []
        if not isinstance(series, list) or not series:
            return ("", None, None)
        window = series[-min(60, len(series)) :]
        x = []
        y = []
        rows = []
        maxv = 1.0
        for r in window:
            rr = r if isinstance(r, dict) else {}
            day = str(rr.get("day") or rr.get("date") or "")
            gmv = _to_float(rr.get("gmv"))
            x.append(day)
            y.append(round(gmv / 10000.0, 2))
            maxv = max(maxv, gmv)
        for i, r in enumerate(window[-10:], start=1):
            rr = r if isinstance(r, dict) else {}
            gmv = _to_float(rr.get("gmv"))
            rows.append(
                {
                    "rank": i,
                    "name": str(rr.get("day") or rr.get("date") or "—"),
                    "value": _fmt_money(gmv),
                    "bar": round(100.0 * gmv / maxv, 1),
                }
            )
        card = {
            "type": "trend",
            "title": "销售趋势",
            "kpis": [
                {"label": "窗口", "value": f"{tool_result.get('start_date', '')} ~ {tool_result.get('end_date', '')}"},
                {"label": "总GMV", "value": _fmt_money(((tool_result.get('summary') or {}) if isinstance(tool_result.get('summary'), dict) else {}).get('gmv'))},
                {"label": "总订单", "value": f"{_to_int(((tool_result.get('summary') or {}) if isinstance(tool_result.get('summary'), dict) else {}).get('order_count')):,}"},
            ],
            "chart": {
                "kind": "line",
                "x": x,
                "series": [{"name": "GMV(万元)", "data": y}],
                "y_label": "万元",
            },
            "rows": rows,
        }
        return (
            "已为你整理近期开单趋势。\n"
            f"<data_card>{json.dumps(card, ensure_ascii=False)}</data_card>",
            card,
            None,
        )

    if tool_name == "get_ops_alerts":
        s = tool_result.get("summary") or {}
        ret = tool_result.get("return_pending") or {}
        sup = tool_result.get("supplement_today") or {}
        mix = tool_result.get("today_order_mix") or {}
        rows = []
        total = max(_to_int(mix.get("total")), 1)
        for i, (name, v) in enumerate(
            [
                ("正常订单", _to_int(mix.get("n_normal"))),
                ("补单订单", _to_int(mix.get("n_supplement"))),
                ("退单订单", _to_int(mix.get("n_return"))),
            ],
            start=1,
        ):
            rows.append(
                {
                    "rank": i,
                    "name": name,
                    "value": f"{v:,}",
                    "bar": round(100.0 * v / total, 1),
                }
            )
        card = {
            "type": "rank",
            "title": "今日运营告警",
            "kpis": [
                {"label": "待处理退货", "value": f"{_to_int(ret.get('count')):,} 笔"},
                {"label": "退货金额", "value": _fmt_money(ret.get("amount"))},
                {"label": "待补单/分拣", "value": f"{_to_int(sup.get('pending_disorder_count')):,} 笔"},
            ],
            "rows": rows,
        }
        return (
            f"已为你整理今日运营异常摘要。\n<data_card>{json.dumps(card, ensure_ascii=False)}</data_card>",
            card,
            None,
        )

    if tool_name == "get_xinfadi_price":
        series = tool_result.get("series") or []
        if not isinstance(series, list) or not series:
            return ("", None, None)
        x = []
        avg = []
        rows = []
        maxv = 1.0
        for r in series[-14:]:
            rr = r if isinstance(r, dict) else {}
            day = str(rr.get("day") or "")
            av = _to_float(rr.get("avg_price"))
            x.append(day)
            avg.append(round(av, 2))
            maxv = max(maxv, av)
        for i, r in enumerate(series[-10:], start=1):
            rr = r if isinstance(r, dict) else {}
            v = _to_float(rr.get("avg_price"))
            rows.append(
                {
                    "rank": i,
                    "name": str(rr.get("day") or "—"),
                    "value": f"¥{v:,.0f}/吨",
                    "bar": round(100.0 * v / maxv, 1),
                }
            )
        latest = series[-1] if isinstance(series[-1], dict) else {}
        card = {
            "type": "trend",
            "title": "新发地价格趋势",
            "kpis": [
                {"label": "最新均价", "value": f"¥{_to_float(latest.get('avg_price')):,.0f}/吨"},
                {"label": "最新最低", "value": f"¥{_to_float(latest.get('min_price')):,.0f}/吨"},
                {"label": "最新最高", "value": f"¥{_to_float(latest.get('max_price')):,.0f}/吨"},
            ],
            "chart": {
                "kind": "line",
                "x": x,
                "series": [{"name": "均价(元/吨)", "data": avg}],
                "y_label": "元/吨",
            },
            "rows": rows,
        }
        return (
            f"已为你整理近期新发地价格走势。\n<data_card>{json.dumps(card, ensure_ascii=False)}</data_card>",
            card,
            None,
        )

    if tool_name == "get_today_orders":
        src_rows = tool_result.get("rows") or []
        if not isinstance(src_rows, list) or not src_rows:
            return ("", None, None)
        vals = [_to_float((r if isinstance(r, dict) else {}).get("total_amount")) for r in src_rows[:10]]
        maxv = max(vals) if vals else 1.0
        maxv = maxv if maxv > 0 else 1.0
        rows = []
        for i, r in enumerate(src_rows[:10], start=1):
            rr = r if isinstance(r, dict) else {}
            amt = _to_float(rr.get("total_amount"))
            rows.append(
                {
                    "rank": i,
                    "name": str(rr.get("customer_name") or rr.get("member_name") or rr.get("order_sn") or "—"),
                    "value": _fmt_money(amt),
                    "bar": round(100.0 * amt / maxv, 1),
                }
            )
        total_amt = sum(vals)
        card = {
            "type": "rank",
            "title": "今日订单概览",
            "kpis": [
                {"label": "返回条数", "value": f"{len(src_rows):,}"},
                {"label": "前10金额", "value": _fmt_money(total_amt)},
                {"label": "最高单", "value": rows[0]["name"] if rows else "—"},
            ],
            "rows": rows,
        }
        return (
            f"已为你整理今日订单概览。\n<data_card>{json.dumps(card, ensure_ascii=False)}</data_card>",
            card,
            None,
        )

    return ("", None, None)


# ---------------------------------------------------------------------------
# 流式进度文案（通用于日报 / 周报 / 月报 / 企划案 / 简报 / 普通查询）
# ---------------------------------------------------------------------------

_TOOL_LABELS = {
    "get_kpi_summary": "核心指标",
    "get_top_goods": "商品排行",
    "get_top_members": "客户排行",
    "get_daily_trend": "销售趋势",
    "get_intraday_gmv": "今日分时",
    "get_region_rank": "区域排行",
    "get_category_distribution": "品类分布",
    "get_backorder_trend": "退货趋势",
    "get_xinfadi_price": "新发地行情",
    "get_ops_alerts": "运营告警",
    "get_member_orders": "会员下钻",
    "get_order_detail": "订单详情",
    "get_today_orders": "今日订单",
    "get_calendar_heatmap": "日历热力",
    "get_schema_overview": "数据范围",
    "generate_report": "报告生成",
}


def _report_type_zh(rt: str) -> str:
    return {
        "daily": "日报",
        "weekly": "周报",
        "monthly": "月报",
        "proposal": "企划案",
        "insight_brief": "经营简报",
    }.get(rt, "报告")


def _stream_hint_for_tool_call(name: str, args: dict[str, Any]) -> str:
    """把工具调用转成对用户友好的流式提示。"""
    if name == "generate_report":
        rt = str(args.get("report_type") or "daily")
        topic = str(args.get("topic") or "").strip()
        district = str(args.get("district_name") or "").strip()
        window = ""
        if args.get("start_date") and args.get("date"):
            window = f"（{args.get('start_date')} ~ {args.get('date')}）"
        elif args.get("date"):
            window = f"（基准日 {args.get('date')}）"
        tail = []
        if topic:
            tail.append(f"主题：{topic}")
        if district:
            tail.append(f"区域：{district}")
        suffix = f"，{'；'.join(tail)}" if tail else ""
        return f"- 正在生成{_report_type_zh(rt)}{window}{suffix}\n"
    if name == "get_schema_overview":
        return "- 正在核对当前已接入的数据范围与表结构\n"
    label = _TOOL_LABELS.get(name, name or "数据工具")
    return f"- 正在查询：{label}\n"


def _stream_hint_for_tool_done(name: str, args: dict[str, Any]) -> str:
    if name == "generate_report":
        rt = str(args.get("report_type") or "daily")
        return f"- {_report_type_zh(rt)}数据已齐，开始组织正文\n"
    label = _TOOL_LABELS.get(name, name or "数据工具")
    return f"- 查询完成：{label}\n"


def _draft_preview_text(intent: dict[str, Any], user_text: str) -> str:
    """首屏先导草稿：在工具未完成前给用户连续自然语言反馈。"""
    it = str((intent or {}).get("intent") or "unknown")
    base = "以下是先导草稿（数据仍在实时核对）：\n"
    if it == "daily_report":
        return base + "我会先按“日报”框架组织：核心指标、区域表现、品类与趋势，随后给出正式结论。"
    if it == "weekly_report":
        return base + "我会按“周报”结构先整理周内波动与环比，再补齐区域/品类/趋势的正式数据结论。"
    if it == "monthly_report":
        return base + "我会按“月报”结构先给经营概览，再补充关键归因与下月动作建议。"
    if it == "proposal_report":
        return base + "我先搭建企划案骨架：背景、机会点、风险、动作与资源排期，待数据包齐全后输出正式版本。"
    if it == "insight_brief":
        return base + "我先给经营分析简报框架：经营摘要、结构变化、异常归因、行动建议，随后补全真实数字。"
    if it in ("region_trend", "sales_rank", "product_rank", "kpi"):
        return base + "我先给你方向性判断，正在同步核对关键指标与排名，稍后给出可落地结论。"
    # 未识别意图也保持温和反馈，避免“无输出感”
    if user_text.strip():
        return base + "我已理解你的问题，正在并行核对相关数据源，马上给出正式回答。"
    return ""


# ---------------------------------------------------------------------------
# POST /api/chat/stream  —— 打字机流式输出（SSE）
# ---------------------------------------------------------------------------
#
# 本项目的 LLM 调用走两段式 + 多轮 FC，天然不适合纯前台 SSE 直通（原因：工具
# 调用轮中的 delta 里掺着 tool_calls，前端拼半天文本会看到字段穿插）。
# 这里采用「后端聚合 + 节流重播」的折中方案：
#   - 后端正常跑 planner → tools → answerer；
#   - 拿到最终文本后，以 phase/tool/delta/done 事件流式 replay 给前端；
#   - delta 控制 ~22ms / 字，整体视觉与真正流式基本一致，且 data_card 能一次稳拿。

SSE_CHAR_DELAY_MS = int(os.environ.get("ASSISTANT_STREAM_DELAY_MS", "22"))
SSE_PHASE_DELAY_MS = int(os.environ.get("ASSISTANT_STREAM_PHASE_DELAY_MS", "120"))


def _sse(event: str, data: Any) -> bytes:
    try:
        payload = json.dumps(data, ensure_ascii=False)
    except Exception:
        payload = json.dumps({"error": "serialize_failed"})
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


async def _stream_text_by_char(text: str) -> AsyncIterator[bytes]:
    """按字符 / 中文断点切块，模拟打字机效果。"""
    if not text:
        return
    delay = SSE_CHAR_DELAY_MS / 1000.0
    # 一次发 2 个 code point，避免过多 event 压垮浏览器但仍保留流畅感
    step = 2
    buf: list[str] = []
    for ch in text:
        buf.append(ch)
        if len(buf) >= step:
            yield _sse("delta", {"text": "".join(buf)})
            buf = []
            await asyncio.sleep(delay)
    if buf:
        yield _sse("delta", {"text": "".join(buf)})


async def _run_with_tools_stream(
    msgs: list[dict[str, Any]]
) -> AsyncIterator[tuple[str, Any]]:
    """answerer：带 tools 多轮 FC。以 yield (kind, payload) 形式回调进度。

    kind:
      - "tool_call":  {"name", "args"}
      - "tool_done":  {"name", "preview"}
      - "final":      {"reply", "data_card", "report_content", "tool_trace"}
    """
    cfg = llm_client.get_config()
    tool_trace: list[dict[str, Any]] = []
    round_i = 0
    while round_i < MAX_TOOL_ROUNDS:
        round_i += 1
        resp = llm_client.chat_completion(
            messages=msgs,
            model=cfg.model_answer,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )
        choices = resp.get("choices") or []
        if not choices:
            break
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls")

        if tool_calls:
            msgs.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )
            for tc in tool_calls:
                fn = (tc.get("function") or {})
                name = fn.get("name") or ""
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                yield ("tool_call", {"name": name, "args": args})
                result = await dispatch_tool_call(name, args)
                preview = _preview(result)
                tool_trace.append({"name": name, "args": args, "result_preview": preview})
                if name == "generate_report":
                    reply, card, report_md = _direct_report_reply(result if isinstance(result, dict) else {})
                    yield ("tool_done", {"name": name, "args": args, "preview": preview})
                    if reply:
                        yield (
                            "final",
                            {
                                "reply": reply,
                                "data_card": card,
                                "report_content": report_md,
                                "tool_trace": tool_trace,
                            },
                        )
                        return
                if len(tool_calls) == 1:
                    reply, card, report_md = _direct_data_card_reply(
                        name,
                        result if isinstance(result, dict) else {},
                    )
                    yield ("tool_done", {"name": name, "args": args, "preview": preview})
                    if reply:
                        yield (
                            "final",
                            {
                                "reply": reply,
                                "data_card": card,
                                "report_content": report_md,
                                "tool_trace": tool_trace,
                            },
                        )
                        return
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id") or "",
                        "name": name,
                        "content": tool_result_content(result),
                    }
                )
                yield ("tool_done", {"name": name, "args": args, "preview": preview})
            continue

        text = message.get("content") or ""
        reply, card, report_md = _extract_artifacts(text)
        yield (
            "final",
            {
                "reply": reply,
                "data_card": card,
                "report_content": report_md,
                "tool_trace": tool_trace,
            },
        )
        return

    yield (
        "final",
        {
            "reply": "抱歉，工具调用超过次数上限。",
            "data_card": None,
            "report_content": None,
            "tool_trace": tool_trace,
        },
    )


async def _chat_stream_generator(req: "ChatRequest") -> AsyncIterator[bytes]:
    cfg = llm_client.get_config()
    session_id = req.session_id or uuid.uuid4().hex

    in_msgs = [m.model_dump() for m in req.messages if m.content or m.role == "tool"]
    if not in_msgs:
        yield _sse("error", {"message": "messages 不能为空"})
        yield _sse("done", {"session_id": session_id, "server_elapsed_ms": 0})
        return

    t0 = time.perf_counter()
    history = get_history(session_id)
    merged_user_assistant = (history + in_msgs)[-(MAX_TURNS * 2):]
    last_user = next((m for m in reversed(in_msgs) if m.get("role") == "user"), None)
    user_text = str((last_user or {}).get("content") or "")
    export_formats = _requested_export_formats_from_text(user_text)
    fast_chart = _fast_chart_query_from_text(user_text)
    fast_schema = _fast_schema_query_from_text(user_text)
    fast_pie = _fast_pie_query_from_text(user_text)
    fast_report_args = _fast_report_args_from_text(user_text)

    yield _sse(
        "meta",
        _estimate_run_profile(
            user_text,
            fast_chart=bool(fast_chart),
            fast_pie=bool(fast_pie),
            fast_schema=fast_schema,
            fast_report_args=fast_report_args,
            intent=None,
        ),
    )

    system_prompt = build_system_prompt()
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    msgs.extend(merged_user_assistant)

    if fast_chart:
        tool_name, tool_args = fast_chart
        yield _sse("phase", {"phase": "planning", "label": "识别到图表指令，走快速通道…"})
        yield _sse("tool", {"name": tool_name, "args": tool_args, "status": "calling"})
        tool_result = await dispatch_tool_call(tool_name, tool_args)
        yield _sse("tool", {"name": tool_name, "status": "done"})
        reply_text, data_card, report_md = _direct_data_card_reply(
            tool_name, tool_result if isinstance(tool_result, dict) else {}
        )
        if reply_text:
            visible = _DATA_CARD_RE.sub("", reply_text).strip()
            yield _sse("phase", {"phase": "answering", "label": "整理回答…"})
            async for chunk in _stream_text_by_char(visible):
                yield chunk
            _persist_turn(session_id, last_user, reply_text)
            yield _sse(
                "done",
                _attach_server_elapsed(
                    {
                        "reply": reply_text,
                        "data_card": data_card,
                        "report_content": report_md,
                        "export_formats": export_formats,
                        "session_id": session_id,
                        "debug": {
                            "mock": cfg.is_mock,
                            "intent": {"intent": "trend_chart", "fast_path": True},
                            "already_clarifying": False,
                            "tool_calls": [{"name": tool_name, "args": tool_args, "result_preview": _preview(tool_result)}],
                        },
                    },
                    t0,
                ),
            )
            return

    if fast_pie:
        tool_name, tool_args, topn = fast_pie
        yield _sse("phase", {"phase": "planning", "label": "识别到TopN饼图需求，走快速通道…"})
        yield _sse("tool", {"name": tool_name, "args": tool_args, "status": "calling"})
        tool_result = await dispatch_tool_call(tool_name, tool_args)
        yield _sse("tool", {"name": tool_name, "status": "done"})
        reply_text, data_card, report_md = _direct_pie_card_reply(
            tool_name, tool_result if isinstance(tool_result, dict) else {}, topn
        )
        if reply_text:
            visible = _DATA_CARD_RE.sub("", reply_text).strip()
            yield _sse("phase", {"phase": "answering", "label": "整理回答…"})
            async for chunk in _stream_text_by_char(visible):
                yield chunk
            _persist_turn(session_id, last_user, reply_text)
            yield _sse(
                "done",
                _attach_server_elapsed(
                    {
                        "reply": reply_text,
                        "data_card": data_card,
                        "report_content": report_md,
                        "export_formats": export_formats,
                        "session_id": session_id,
                        "debug": {
                            "mock": cfg.is_mock,
                            "intent": {"intent": "topn_pie", "fast_path": True},
                            "already_clarifying": False,
                            "tool_calls": [{"name": tool_name, "args": tool_args, "result_preview": _preview(tool_result)}],
                        },
                    },
                    t0,
                ),
            )
            return

    if fast_schema:
        yield _sse("phase", {"phase": "planning", "label": "识别到数据范围查询，走快速通道…"})
        yield _sse("tool", {"name": "get_schema_overview", "args": {}, "status": "calling"})
        tool_result = await dispatch_tool_call("get_schema_overview", {})
        yield _sse("tool", {"name": "get_schema_overview", "status": "done"})
        reply_text, data_card, report_md = _direct_schema_reply(tool_result if isinstance(tool_result, dict) else {})
        yield _sse("phase", {"phase": "answering", "label": "整理回答…"})
        async for chunk in _stream_text_by_char(reply_text):
            yield chunk
        _persist_turn(session_id, last_user, reply_text)
        yield _sse(
            "done",
            _attach_server_elapsed(
                {
                    "reply": reply_text,
                    "data_card": data_card,
                    "report_content": report_md,
                    "export_formats": export_formats,
                    "session_id": session_id,
                    "debug": {
                        "mock": cfg.is_mock,
                        "intent": {"intent": "schema_overview", "fast_path": True},
                        "already_clarifying": False,
                        "tool_calls": [{"name": "get_schema_overview", "args": {}, "result_preview": _preview(tool_result)}],
                    },
                },
                t0,
            ),
        )
        return

    if fast_report_args:
        yield _sse("phase", {"phase": "planning", "label": "识别到报表指令，走快速通道…"})
        yield _sse("delta", {"text": "正在生成报表，请稍候。\n"})
        yield _sse(
            "tool",
            {"name": "generate_report", "args": fast_report_args, "status": "calling"},
        )
        tool_result = await dispatch_tool_call("generate_report", fast_report_args)
        yield _sse("tool", {"name": "generate_report", "status": "done"})
        reply_text, data_card, report_md = _direct_report_reply(tool_result if isinstance(tool_result, dict) else {})
        if reply_text:
            visible = _REPORT_RE.sub("", reply_text).strip()
            yield _sse("phase", {"phase": "answering", "label": "整理回答…"})
            async for chunk in _stream_text_by_char(visible):
                yield chunk
            _persist_turn(session_id, last_user, reply_text)
            yield _sse(
                "done",
                _attach_server_elapsed(
                    {
                        "reply": reply_text,
                        "data_card": data_card,
                        "report_content": report_md,
                        "export_formats": export_formats,
                        "session_id": session_id,
                        "debug": {
                            "mock": cfg.is_mock,
                            "intent": {"intent": f"{fast_report_args.get('report_type')}_report", "fast_path": True},
                            "already_clarifying": False,
                            "tool_calls": [{"name": "generate_report", "args": fast_report_args, "result_preview": _preview(tool_result)}],
                        },
                    },
                    t0,
                ),
            )
            return

    yield _sse("phase", {"phase": "planning", "label": "读取上下文、识别意图…"})
    # 立即给前端一个可见文本，避免“空等无输出”
    yield _sse("delta", {"text": "我先快速理解你的问题，并准备查询数据。\n"})
    await asyncio.sleep(SSE_PHASE_DELAY_MS / 1000.0)

    intent = await _run_planner(merged_user_assistant)
    last_assistant = next(
        (m for m in reversed(merged_user_assistant) if m.get("role") == "assistant"),
        None,
    )
    already_clarifying = bool(last_assistant and _is_clarifying_question(last_assistant))
    yield _sse(
        "intent",
        {"intent": intent.get("intent"), "already_clarifying": already_clarifying},
    )
    yield _sse(
        "meta",
        _estimate_run_profile(user_text, intent=intent, already_clarifying=already_clarifying),
    )

    if intent.get("needClarify") and intent.get("clarifyQuestion") and not already_clarifying:
        clarify = str(intent.get("clarifyQuestion")).strip() or "为了更准确回答，请明确时间/区域/品类。"
        yield _sse("phase", {"phase": "clarify", "label": "需要先确认一下维度…"})
        async for chunk in _stream_text_by_char(clarify):
            yield chunk
        _persist_turn(session_id, last_user, clarify)
        yield _sse(
            "done",
            _attach_server_elapsed(
                {
                    "reply": clarify,
                    "data_card": None,
                    "report_content": None,
                    "export_formats": export_formats,
                    "session_id": session_id,
                    "debug": {"mock": cfg.is_mock, "intent": intent, "already_clarifying": already_clarifying},
                },
                t0,
            ),
        )
        return

    # 双阶段流式（第一阶段）：先导草稿，提升首屏可感知性
    draft = _draft_preview_text(intent, user_text)
    if draft:
        yield _sse("phase", {"phase": "drafting", "label": "先给你一个初步分析草稿…"})
        async for chunk in _stream_text_by_char(draft):
            yield chunk
        yield _sse("delta", {"text": "\n\n"})

    yield _sse("phase", {"phase": "querying", "label": "正在查询业务数据…"})
    yield _sse("delta", {"text": "正在连接数据源，马上给你结果。\n"})
    await asyncio.sleep(SSE_PHASE_DELAY_MS / 1000.0)

    reply_text = ""
    data_card = None
    report_md = None
    tool_trace: list[dict[str, Any]] = []
    async for kind, payload in _run_with_tools_stream(msgs):
        if kind == "tool_call":
            name = payload.get("name")
            args = payload.get("args") or {}
            yield _sse(
                "tool",
                {"name": name, "args": args, "status": "calling"},
            )
            # 在工具执行期实时吐可读进度，避免用户“长时间无文本”
            yield _sse("delta", {"text": _stream_hint_for_tool_call(str(name or ""), args)})
        elif kind == "tool_done":
            name = payload.get("name")
            yield _sse(
                "tool",
                {"name": name, "status": "done"},
            )
            yield _sse(
                "delta",
                {
                    "text": _stream_hint_for_tool_done(
                        str(name or ""),
                        payload.get("args") or {},
                    )
                },
            )
        elif kind == "final":
            reply_text = payload.get("reply") or ""
            data_card = payload.get("data_card")
            report_md = payload.get("report_content")
            tool_trace = payload.get("tool_trace") or []

    yield _sse("phase", {"phase": "answering", "label": "整理回答…"})

    # 流式回放：剥掉 <data_card>/<report_content> 标签后只显示可读文本
    visible = reply_text
    visible = _DATA_CARD_RE.sub("", visible)
    visible = _REPORT_RE.sub("", visible)
    visible = visible.strip()
    async for chunk in _stream_text_by_char(visible or reply_text):
        yield chunk

    _persist_turn(session_id, last_user, reply_text)
    yield _sse(
        "done",
        _attach_server_elapsed(
            {
                "reply": reply_text,
                "data_card": data_card,
                "report_content": report_md,
                "export_formats": export_formats,
                "session_id": session_id,
                "debug": {
                    "mock": cfg.is_mock,
                    "intent": intent,
                    "already_clarifying": already_clarifying,
                    "tool_calls": tool_trace,
                },
            },
            t0,
        ),
    )


@router.post("/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """SSE 流式主对话。事件列表：
    - meta    : {tier, eta_sec_min, eta_sec_max, hint}  —— 启发式预计耗时（仅供参考）
    - phase   : {phase, label}  —— planning / querying / answering / clarify
    - intent  : {intent, already_clarifying}
    - tool    : {name, args?, status: calling|done}
    - delta   : {text}  —— 文本增量（按字节 / 字符）
    - done    : {reply, data_card, report_content, session_id, debug, server_elapsed_ms}
    - error   : {message}
    """
    generator = _chat_stream_generator(req)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 避免 nginx 缓冲
        },
    )


# ---------------------------------------------------------------------------
# POST /api/chat/report/export → .docx
# ---------------------------------------------------------------------------

_EXPORT_MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "md": "text/markdown; charset=utf-8",
}


@router.post("/report/export")
async def export_report(req: ExportRequest):
    if not req.markdown or not req.markdown.strip():
        raise HTTPException(400, "markdown 不能为空")

    fmt = (req.format or "docx").strip().lower()
    if fmt not in _EXPORT_MEDIA:
        raise HTTPException(400, f"不支持的导出格式：{fmt}，仅支持 docx / pptx / md")

    try:
        if fmt == "docx":
            blob = markdown_to_docx_bytes(req.markdown, title=req.title)
        elif fmt == "pptx":
            blob = markdown_to_pptx_bytes(req.markdown, title=req.title)
        else:
            blob = markdown_to_md_bytes(req.markdown, title=req.title)
    except Exception as e:
        logger.exception("生成 %s 失败：%s", fmt, e)
        raise HTTPException(500, f"生成 {fmt} 失败：{e}") from e

    fname = (req.filename or req.title or "report").strip() or "report"
    from urllib.parse import quote

    safe = quote(fname)
    headers = {
        "Content-Disposition": (
            f"attachment; filename=report.{fmt}; filename*=UTF-8''{safe}.{fmt}"
        ),
    }
    return StreamingResponse(
        iter([blob]),
        media_type=_EXPORT_MEDIA[fmt],
        headers=headers,
    )


# ---------------------------------------------------------------------------
# 数据库结构 / 接口样例 缓存
# ---------------------------------------------------------------------------

@router.get("/catalog")
def catalog_summary() -> dict[str, Any]:
    return get_catalog_summary()


class RefreshRequest(BaseModel):
    include_tables: bool = True


@router.post("/catalog/refresh")
async def catalog_refresh(req: RefreshRequest | None = None):
    base = os.environ.get(
        "ASSISTANT_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/insights/business"
    )
    include_tables = True if req is None else bool(req.include_tables)
    return await refresh_catalog(internal_api_base=base, include_tables=include_tables)
