"""通义千问（DashScope 兼容 OpenAI SDK）客户端封装。

- AI_PROVIDER=dashscope（默认）：走阿里云百炼 DashScope Compatible Mode，
  同一份 OpenAI v1 SDK 代码即可切换后端。
- AI_API_KEY 为空时自动进入 mock 模式：生成结构化 data_card / report_content，
  工具层仍会真实去查库；方便未配 Key 时完整跑通全流程。

两段式调用：
- planner：意图识别（较便宜模型，如 qwen-turbo），输出 JSON 或决定是否反问
- answerer：带 tools 多轮 Function Calling 得出最终回复
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 默认走阿里云百炼 DashScope 兼容 OpenAI 的端点
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@dataclass
class LLMConfig:
    provider: str = field(
        default_factory=lambda: os.environ.get("AI_PROVIDER", "dashscope").strip().lower()
    )
    api_key: str = field(
        default_factory=lambda: os.environ.get("AI_API_KEY", "").strip()
    )
    base_url: str = field(
        default_factory=lambda: os.environ.get("AI_BASE_URL", DEFAULT_BASE_URL).strip()
    )
    model_planner: str = field(
        default_factory=lambda: os.environ.get("AI_MODEL_PLANNER", "qwen-plus").strip()
    )
    model_answer: str = field(
        default_factory=lambda: os.environ.get("AI_MODEL_ANSWER", "qwen-max").strip()
    )

    @property
    def is_mock(self) -> bool:
        return not self.api_key or self.provider == "mock"


def get_config() -> LLMConfig:
    return LLMConfig()


_client_cache: Any = None


def _get_openai_client():
    """延迟初始化；失败（如 openai 未装）时返回 None 由上层走 mock。"""
    global _client_cache
    if _client_cache is not None:
        return _client_cache
    cfg = get_config()
    if cfg.is_mock:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:  # 未装 openai 包时安全降级
        logger.warning("openai SDK 未安装，AI 助手走 mock：%s", e)
        return None
    try:
        _client_cache = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    except Exception as e:
        logger.warning("初始化 OpenAI 客户端失败，AI 助手走 mock：%s", e)
        return None
    return _client_cache


def chat_completion(
    *,
    messages: list[dict[str, Any]],
    model: Optional[str] = None,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Any = None,
    temperature: float = 0.3,
    response_format: Optional[dict[str, Any]] = None,
    max_tokens: Optional[int] = None,
) -> dict[str, Any]:
    """统一 chat.completions 入口。返回 dict（含 choices、message、tool_calls 等关键字段）。

    为了兼容 mock，返回值抹平为 OpenAI v1 ChatCompletion 的简化 dict，
    关键访问路径：
      data["choices"][0]["message"]["content"]
      data["choices"][0]["message"]["tool_calls"]（可能为 None）
    """
    cfg = get_config()
    client = _get_openai_client()
    if client is None:
        return _mock_chat_completion(messages=messages, tools=tools)

    payload: dict[str, Any] = {
        "model": model or cfg.model_answer,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"
    if response_format is not None:
        payload["response_format"] = response_format
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    try:
        resp = client.chat.completions.create(**payload)
    except Exception as e:
        logger.exception("LLM 调用失败，回退 mock：%s", e)
        return _mock_chat_completion(messages=messages, tools=tools, error=str(e))

    return _normalize_resp(resp)


def _normalize_resp(resp: Any) -> dict[str, Any]:
    """把 OpenAI v1 对象转为纯 dict。"""
    try:
        if hasattr(resp, "model_dump"):
            return resp.model_dump()
    except Exception:
        pass
    try:
        # 兼容较旧 SDK：手动取字段
        choices = []
        for ch in getattr(resp, "choices", []) or []:
            msg = getattr(ch, "message", None)
            tool_calls = []
            for tc in getattr(msg, "tool_calls", None) or []:
                tool_calls.append(
                    {
                        "id": getattr(tc, "id", None),
                        "type": getattr(tc, "type", "function"),
                        "function": {
                            "name": getattr(getattr(tc, "function", None), "name", ""),
                            "arguments": getattr(getattr(tc, "function", None), "arguments", "{}"),
                        },
                    }
                )
            choices.append(
                {
                    "finish_reason": getattr(ch, "finish_reason", None),
                    "message": {
                        "role": getattr(msg, "role", "assistant"),
                        "content": getattr(msg, "content", None),
                        "tool_calls": tool_calls or None,
                    },
                }
            )
        return {"choices": choices}
    except Exception:
        return {"choices": [{"message": {"role": "assistant", "content": ""}}]}


# ---------------------------------------------------------------------------
# Mock 分支：未配置 AI_API_KEY 时，仍要把完整流程跑通
# ---------------------------------------------------------------------------

def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str):
                return c
    return ""


def _mock_chat_completion(
    *,
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    """在没有真实 LLM 时，按用户文字命中关键字生成 tool_calls 或最终回复。

    - 若带 tools 且当前没有 tool 结果（上一条非 tool）→ 生成 tool_calls
    - 已有 tool 结果 → 输出最终自然语言 + <data_card> / <report_content>
    """
    user_text = _last_user_text(messages)
    last = messages[-1] if messages else {}

    # 已产生过工具结果（上一步是 tool role） → 产出最终 assistant 文本
    any_tool_result = any(m.get("role") == "tool" for m in messages[-8:])
    if any_tool_result:
        card = _mock_build_card_from_tool_results(messages, user_text)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": card,
                        "tool_calls": None,
                    },
                }
            ]
        }

    # 未调工具时 → 若提供了 tools，则发一次 tool_call
    if tools:
        name, args = _mock_pick_tool(user_text)
        if name:
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "mock_call_1",
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": json.dumps(args, ensure_ascii=False),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }

    # 无工具：直接回复
    reply = "（mock 模式）你好！我是业务分析助手，可查询销售、品类/区域排名与趋势，或生成日报/周报。"
    if error:
        reply += f"\n\n提示：真实大模型未就绪（{error[:80]}…），暂以内置演示数据作答。"
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": reply, "tool_calls": None},
            }
        ]
    }


def _mock_pick_tool(text: str) -> tuple[Optional[str], dict[str, Any]]:
    """极简关键词 → 工具映射，只用于无 Key 兜底演示。"""
    from datetime import timedelta

    from app.services.ai_chat.business_date import business_today

    t = (text or "").strip()
    today_d = business_today()
    today = today_d.isoformat()
    yesterday = (today_d - timedelta(days=1)).isoformat()
    day_before = (today_d - timedelta(days=2)).isoformat()
    week_start = (today_d - timedelta(days=6)).isoformat()
    month_start = today_d.replace(day=1).isoformat()
    year_start = today_d.replace(month=1, day=1).isoformat()

    def _range_args() -> dict[str, Any]:
        if any(k in t for k in ("昨天", "昨日", "昨")):
            return {"start_date": yesterday, "end_date": yesterday}
        if "前天" in t:
            return {"start_date": day_before, "end_date": day_before}
        if any(k in t for k in ("今年", "本年", "本年度")):
            return {"start_date": year_start, "end_date": today}
        if any(k in t for k in ("本月", "这个月")):
            return {"start_date": month_start, "end_date": today}
        if any(k in t for k in ("近7天", "近 7 天", "最近一周", "本周")):
            return {"start_date": week_start, "end_date": today}
        return {"start_date": today, "end_date": today}

    def _report_date() -> str:
        if any(k in t for k in ("昨天", "昨日", "昨")):
            return yesterday
        if "前天" in t:
            return day_before
        return today

    if any(k in t for k in ("日报", "周报", "月报", "报告")):
        rtype = "weekly" if "周报" in t else ("monthly" if "月报" in t else "daily")
        return ("generate_report", {"report_type": rtype, "date": _report_date()})
    if any(k in t for k in ("区", "区域", "各区", "地区")) and any(
        k in t for k in ("排名", "最好", "最多", "TOP", "top", "卖得")
    ):
        return ("get_region_rank", {**_range_args(), "limit": 10})
    if any(k in t for k in ("品类", "单品", "商品", "品项")) and any(
        k in t for k in ("排名", "卖得", "top", "TOP", "最好")
    ):
        return ("get_top_goods", {**_range_args(), "limit": 10})
    if any(k in t for k in ("会员", "客户", "买家")) and "排名" in t:
        return ("get_top_members", {**_range_args(), "limit": 10})
    if any(k in t for k in ("趋势", "走势", "本月", "本周", "近")) and any(
        k in t for k in ("区", "销售", "GMV", "gmv", "成交")
    ):
        return ("get_daily_trend", _range_args())
    if any(k in t for k in ("今日", "今天", "今", "昨天", "昨日", "前天", "今年", "本月", "gmv", "GMV", "销售额", "成交")):
        rg = _range_args()
        if rg["start_date"] == today and rg["end_date"] == today:
            return ("get_kpi_summary", {"scope": "today"})
        return ("get_kpi_summary", {"scope": "range", **rg})
    if any(k in t for k in ("能查什么", "查哪些", "有哪些表", "schema", "元数据", "表结构")):
        return ("get_schema_overview", {})
    if any(k in t for k in ("异常", "告警", "退货", "补单")):
        return ("get_ops_alerts", {"limit": 20})
    if any(k in t for k in ("菜价", "新发地", "价格", "行情")):
        return ("get_xinfadi_price", _range_args())
    if any(k in t for k in ("企划案", "策划案", "方案", "提案")):
        return ("generate_report", {"report_type": "proposal", "topic": t[:24], "date": _report_date()})
    if any(k in t for k in ("复盘", "经营分析", "经营简报", "总结")):
        return ("generate_report", {"report_type": "insight_brief", "date": _report_date()})
    if any(k in t for k in ("今日", "今天", "今", "订单列表", "出了哪些单")):
        return ("get_today_orders", {"limit": 100})
    if any(k in t for k in ("日历热力", "热力图")):
        return ("get_calendar_heatmap", _range_args())
    if any(k in t for k in ("折线图", "曲线", "走势图", "柱状图", "柱图", "饼图", "占比图")):
        return ("get_kpi_summary", {"scope": "today"})
    return (None, {})


def _mock_build_card_from_tool_results(messages: list[dict[str, Any]], user_text: str) -> str:
    """根据最近一条 tool 消息的 name + JSON 结果，拼 <data_card> 或 <report_content>。"""
    tool_msg = None
    for m in reversed(messages):
        if m.get("role") == "tool":
            tool_msg = m
            break
    if not tool_msg:
        return "（mock）暂无工具结果。"

    name = tool_msg.get("name") or ""
    try:
        data = json.loads(tool_msg.get("content") or "{}")
    except Exception:
        data = {}

    if name == "get_region_rank":
        return _mock_card_rank(data, title="今日区域销售排名", key_name="district_name")
    if name == "get_top_goods":
        return _mock_card_rank(data, title="品类销售排名", key_name="goods_name", value_field="total_amount")
    if name == "get_top_members":
        return _mock_card_rank(data, title="客户成交排名", key_name="member_name")
    if name == "get_daily_trend":
        return _mock_card_trend(data)
    if name == "get_kpi_summary":
        return _mock_card_kpi(data)
    if name == "get_intraday_gmv":
        return _mock_card_kpi(data)
    if name == "generate_report":
        return _mock_report(data, user_text)

    return json.dumps(data, ensure_ascii=False)[:800]


def _fmt_money(n: float) -> str:
    n = float(n or 0)
    if n >= 100000000:
        return f"¥{n/100000000:.2f}亿"
    if n >= 10000:
        return f"¥{n/10000:.1f}万"
    return f"¥{n:,.0f}"


def _mock_card_rank(data: dict, *, title: str, key_name: str, value_field: str = "gmv") -> str:
    rows_src = data.get("rows") or data.get("key_districts") or []
    items = []
    total = 0.0
    for i, r in enumerate(rows_src[:10], start=1):
        name = r.get(key_name) or r.get("name") or f"#{i}"
        val = float(r.get(value_field) or r.get("gmv") or r.get("total_amount") or 0)
        items.append({"rank": i, "name": str(name), "_val": val, "trend": (f"{r['mom_pct']:+.1f}%") if r.get("mom_pct") is not None else ""})
        total += val
    max_val = max((x["_val"] for x in items), default=1.0) or 1.0
    rows = [
        {
            "rank": x["rank"],
            "name": x["name"],
            "value": _fmt_money(x["_val"]),
            "trend": x["trend"],
            "bar": round(100.0 * x["_val"] / max_val, 1),
        }
        for x in items
    ]
    kpis = [
        {"label": "入榜数量", "value": f"{len(rows)}"},
        {"label": "合计金额", "value": _fmt_money(total)},
        {"label": "榜首", "value": rows[0]["name"] if rows else "—"},
    ]
    card = {"type": "rank", "title": title, "kpis": kpis, "rows": rows}
    summary = f"{title}已生成，Top {len(rows)} 合计 {_fmt_money(total)}。"
    return summary + "\n<data_card>" + json.dumps(card, ensure_ascii=False) + "</data_card>"


def _mock_card_kpi(data: dict) -> str:
    kpis = [
        {"label": "今日 GMV", "value": _fmt_money(float(data.get("gmv") or 0))},
        {"label": "订单数", "value": f"{int(data.get('order_count') or 0)}"},
        {"label": "客单价", "value": _fmt_money(float(data.get("avg_ticket") or 0))},
    ]
    card = {"type": "kpi", "title": "今日核心 KPI", "kpis": kpis, "rows": []}
    return "今日核心 KPI 如下：\n<data_card>" + json.dumps(card, ensure_ascii=False) + "</data_card>"


def _mock_card_trend(data: dict) -> str:
    series = data.get("series") or []
    rows = []
    for i, r in enumerate(series[-10:], start=1):
        day = str(r.get("day") or r.get("date") or "")
        val = float(r.get("gmv") or 0)
        rows.append({"rank": i, "name": day, "value": _fmt_money(val), "trend": "", "bar": 100})
    maxv = max((float(r.get("gmv") or 0) for r in series[-10:]), default=1.0) or 1.0
    for r in rows:
        try:
            v = float(str(r["value"]).replace("¥", "").replace(",", "").replace("万", "").replace("亿", ""))
        except Exception:
            v = 0
        r["bar"] = round(100.0 * v / maxv, 1) if maxv else 0
    kpis = [
        {"label": "窗口", "value": f"{data.get('start_date', '')} ~ {data.get('end_date', '')}"},
        {"label": "合计 GMV", "value": _fmt_money(float((data.get("summary") or {}).get("gmv") or 0))},
        {"label": "订单", "value": f"{int((data.get('summary') or {}).get('order_count') or 0)}"},
    ]
    card = {"type": "trend", "title": "每日 GMV 趋势", "kpis": kpis, "rows": rows}
    return "近期 GMV 趋势：\n<data_card>" + json.dumps(card, ensure_ascii=False) + "</data_card>"


def _mock_report(data: dict, user_text: str) -> str:
    md = data.get("markdown") or "# 报告\n\n暂无数据"
    title = data.get("title") or "业务报告"
    return (
        f"已为您生成 {title}，可点击右上角「下载 .docx」。\n"
        f"<report_content>{md}</report_content>"
    )
