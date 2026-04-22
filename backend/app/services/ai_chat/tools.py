"""Function Calling 工具声明 + dispatcher。

设计要点：
- 工具底层不直接写 SQL / 连 MySQL，而是通过 httpx 调本地 /api/insights/business/*，
  以复用现成的口径与连接治理，避免重复维护。
- 同时兼容「在线真实库」与「离线 fallback」：
    * 在线：httpx 真调 localhost:8000 返回 JSON；
    * 离线（请求失败，例如用户 VPN 关了）：优先从 data_catalog 缓存读，
      若没有缓存 → 返回结构化 _offline 标记，由 LLM 或 mock 层提示用户。
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx

from app.services.ai_chat.business_date import business_today
from app.services.ai_chat.schema_catalog import get_cached_business_api_sample

logger = logging.getLogger(__name__)

_INTERNAL_API_BASE = os.environ.get(
    "ASSISTANT_INTERNAL_API_BASE", "http://127.0.0.1:8000/api/insights/business"
).rstrip("/")


# ---------------------------------------------------------------------------
# tools 定义（OpenAI Function Calling 规范）
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_kpi_summary",
            "description": "查询某日期窗口的核心 KPI（订单数、GMV、客单价、去重买家、退单等）。今日用 scope=today；区间传 start_date/end_date。",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["today", "range"],
                        "description": "today=仅今日；range=用 start_date/end_date",
                    },
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "district_name": {
                        "type": "string",
                        "description": "可选：仅统计收货地址匹配该区县（如「海淀区」「朝阳区」），不过滤留空。",
                    },
                },
                "required": ["scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_goods",
            "description": "查询时间窗口内「单品 / 品类」按 GMV 的 TOP N。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
                    "district_name": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_members",
            "description": "查询时间窗口内会员（客户）的 GMV TOP N 排名。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                    "district_name": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_trend",
            "description": "查询每日订单数与 GMV 序列（趋势）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "district_name": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_intraday_gmv",
            "description": "今日分钟桶 GMV 与订单数（看当日时段分布时用）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_region_rank",
            "description": "各区县 GMV 排行（含环比 mom_pct）。区域维度排名优先用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_distribution",
            "description": (
                "按商品类别（蔬菜/肉类/水果/主食/杂粮等）汇总销售金额与行数。"
                "适用：「蔬菜卖得比肉多吗」「本月哪个品类增长最快」「品类占比」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 30, "default": 10},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_backorder_trend",
            "description": (
                "退货 / 退单按日序列（笔数与金额）。"
                "适用：「最近退货有没有在涨」「哪天退得最多」「退货趋势」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_xinfadi_price",
            "description": (
                "新发地批发市场日行情（最低价 / 均价 / 最高价 / 成交量）。"
                "适用：「西红柿最近什么价」「本月蔬菜均价走势」「白菜最高到多少钱」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ops_alerts",
            "description": (
                "今日运营预警：待处理退货、今日补单 / 分拣单、今日三色占比（正常/退单/补单）。"
                "适用：「今天有哪些异常要处理」「今天退货补单多少」「告警列表」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                    "district_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_member_orders",
            "description": (
                "查某一会员 / 某一收货地址在区间内的订单明细（下钻）。"
                "适用：「张总最近下了哪几单」「北京市海淀区 X 路 123 号的订单」。"
                "member_id 或 address 至少给一个；返回最多 500 行。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "member_id": {"type": "integer"},
                    "address": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_detail",
            "description": (
                "单笔订单完整信息：表头（订单号/金额/时间/下单人） + 商品行（品名/规格/数量/金额）。"
                "适用：「这个订单号 XXX 具体是什么内容」「单号 45678 买了什么」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "订单主键 id"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_today_orders",
            "description": (
                "今日 0 点至今全市订单列表（时间倒序）。"
                "适用：「今天都出了哪些单」「今天最近几单」。limit 默认 100，最多 500。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar_heatmap",
            "description": (
                "按日 GMV / 订单数序列，用于日历热力视图。"
                "适用：「最近一个季度哪些日子出单多」「本月日历热力」。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schema_overview",
            "description": (
                "盘点业务库中有哪些数据表与关键字段（元数据自省）。"
                "适用：「你都能查什么数据」「数据库里有哪些表」「你这边有没有 XX 数据」。"
                "【兜底规则】：当你无法在已有工具里找到合适的接口回答用户问题时，优先调用此工具，"
                "基于真实表结构告诉用户你有 / 没有相应数据，而不是胡编。"
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": (
                "生成结构化长文。"
                "report_type=daily|weekly|monthly 为常规日报/周报/月报，按 date 锚点取窗口；"
                "report_type=proposal 为**企划案 / 策划案 / 方案**，适用「帮我写个企划案 / 策划案 / 营销方案」，需要传 topic（主题）；"
                "report_type=insight_brief 为**经营分析简报 / 复盘 / 总结**，适用「帮我复盘一下 / 经营分析 / 做个经营简报」。"
                "【日期】用户说「昨天的日报」→ date 必须传昨天；「前天的日报」→ date 传前天；「上周的周报」→ date 传上周末尾日；不传才等价今天。"
                "【长文版本】proposal 与 insight_brief 会自动并行拉 KPI+区域+品类+趋势+行情+预警，最后由 LLM 基于真实数据组合成章节型 Markdown。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "report_type": {
                        "type": "string",
                        "enum": ["daily", "weekly", "monthly", "proposal", "insight_brief"],
                    },
                    "date": {
                        "type": "string",
                        "description": "基准日 YYYY-MM-DD；常规报告决定锚点，proposal/insight_brief 决定分析窗口的结束日。缺省=今天。",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "可选：proposal/insight_brief 可自定义分析起始日 YYYY-MM-DD，不传则按 date 回推 30 天。",
                    },
                    "topic": {
                        "type": "string",
                        "description": "企划案主题，如「夏季集采保障」「海淀区机关单位客户拓展」「学校档口端午供给方案」；report_type=proposal 时必填。",
                    },
                    "district_name": {"type": "string"},
                },
                "required": ["report_type"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------

async def _get(path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """调本地 insights_business 接口；失败降级。"""
    url = f"{_INTERNAL_API_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(url, params=params or {})
            r.raise_for_status()
            return r.json()
    except Exception as e:
        # 尝试 offline 缓存
        sample = get_cached_business_api_sample(path)
        if sample is not None:
            logger.warning("业务接口 %s 失败，回退缓存样例：%s", path, e)
            return {**sample, "_offline": True, "_error": str(e)[:200]}
        logger.warning("业务接口 %s 失败且无缓存：%s", path, e)
        return {"_offline": True, "_error": str(e)[:200], "rows": []}


async def dispatch_tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """按 name 调底层接口，返回尽量贴近 OpenAI tool_result 所需的 JSON。"""
    try:
        if name == "get_kpi_summary":
            params = {"scope": args.get("scope", "today")}
            for k in ("start_date", "end_date", "district_name"):
                if args.get(k):
                    params[k] = args[k]
            # 聊天交互优先时延，跳过业务库高开销衍生指标（首单会员）
            params["fast_mode"] = True
            return await _get("/kpi-summary", params)

        if name == "get_top_goods":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            if args.get("limit"):
                params["limit"] = int(args["limit"])
            if args.get("district_name"):
                params["district_name"] = args["district_name"]
            return await _get("/goods-top", params)

        if name == "get_top_members":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            if args.get("limit"):
                params["limit"] = int(args["limit"])
            if args.get("district_name"):
                params["district_name"] = args["district_name"]
            data = await _get("/orders-top-members", params)
            if isinstance(data, dict) and isinstance(data.get("rows"), list):
                data["rows"] = [_mask_member_row(r) for r in data["rows"]]
                data["_pii_masked"] = True
            return data

        if name == "get_daily_trend":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            if args.get("district_name"):
                params["district_name"] = args["district_name"]
            return await _get("/orders-daily", params)

        if name == "get_intraday_gmv":
            params: dict[str, Any] = {}
            if args.get("district_name"):
                params["district_name"] = args["district_name"]
            return await _get("/today-intraday-gmv", params)

        if name == "get_region_rank":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            data = await _get("/cockpit-smart-side-insights", params)
            kd = data.get("key_districts") or []
            limit = int(args.get("limit") or 10)
            return {
                "start_date": data.get("start_date"),
                "end_date": data.get("end_date"),
                "rows": kd[:limit],
                "_source": "cockpit-smart-side-insights.key_districts",
            }

        if name == "get_category_distribution":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            if args.get("limit"):
                params["limit"] = int(args["limit"])
            return await _get("/category-distribution", params)

        if name == "get_backorder_trend":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            return await _get("/backorder-daily", params)

        if name == "get_xinfadi_price":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            return await _get("/xinfadi-summary-series", params)

        if name == "get_ops_alerts":
            params: dict[str, Any] = {}
            if args.get("limit"):
                params["limit"] = int(args["limit"])
            if args.get("district_name"):
                params["district_name"] = args["district_name"]
            return await _get("/ops-alerts", params)

        if name == "get_member_orders":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            if args.get("member_id"):
                params["member_id"] = int(args["member_id"])
            if args.get("address"):
                params["address"] = str(args["address"])
            data = await _get("/member-orders-in-range", params)
            if isinstance(data, dict) and isinstance(data.get("rows"), list):
                data["rows"] = [_mask_member_row(r) for r in data["rows"]]
                data["_pii_masked"] = True
            return data

        if name == "get_order_detail":
            order_id = args.get("order_id")
            if not order_id:
                return {"error": "order_id 必填"}
            head = await _get("/order-head", {"order_id": int(order_id)})
            lines_ = await _get("/order-line-items", {"order_id": int(order_id)})
            head = _mask_member_row(head) if isinstance(head, dict) else head
            return {"head": head, "items": (lines_ or {}).get("rows") or []}

        if name == "get_today_orders":
            params: dict[str, Any] = {}
            if args.get("limit"):
                params["limit"] = int(args["limit"])
            data = await _get("/today-orders-list", params)
            if isinstance(data, dict) and isinstance(data.get("rows"), list):
                data["rows"] = [_mask_member_row(r) for r in data["rows"]]
                data["_pii_masked"] = True
            return data

        if name == "get_calendar_heatmap":
            params = {k: args[k] for k in ("start_date", "end_date") if k in args}
            return await _get("/orders-calendar-heatmap", params)

        if name == "get_schema_overview":
            return await _get("/meta/tables", None)

        if name == "generate_report":
            return await _generate_report(args)

        return {"error": f"未知工具：{name}"}
    except Exception as e:
        logger.exception("tool %s 异常：%s", name, e)
        return {"error": str(e)[:300]}


def _daterange_for_report(
    report_type: str,
    base: Optional[str],
    start_override: Optional[str] = None,
) -> tuple[str, str]:
    today = date.fromisoformat(base) if base else business_today()
    if start_override:
        try:
            return date.fromisoformat(start_override).isoformat(), today.isoformat()
        except Exception:
            pass
    if report_type == "weekly":
        start = today - timedelta(days=6)
    elif report_type == "monthly":
        start = today.replace(day=1)
    elif report_type in ("proposal", "insight_brief"):
        # 长文分析默认看近 30 天
        start = today - timedelta(days=29)
    else:
        start = today
    return start.isoformat(), today.isoformat()


async def _generate_report(args: dict[str, Any]) -> dict[str, Any]:
    """组合 KPI + 区域 + 单品 + 趋势，生成 Markdown 报告正文。

    - daily / weekly / monthly：工具层直接拼完整报告 Markdown，LLM 只需把它塞进 <report_content>；
    - proposal / insight_brief：工具层返回「数据摘要包 + 写作纲要」，LLM 再基于真实数据写章节长文。
    """
    report_type = str(args.get("report_type") or "daily")
    if report_type not in ("daily", "weekly", "monthly", "proposal", "insight_brief"):
        report_type = "daily"
    start, end = _daterange_for_report(
        report_type,
        args.get("date"),
        start_override=args.get("start_date"),
    )
    district = args.get("district_name") or None
    topic = str(args.get("topic") or "").strip()

    if report_type in ("proposal", "insight_brief"):
        return await _generate_analytical_brief(
            report_type=report_type,
            start=start,
            end=end,
            district=district,
            topic=topic,
        )

    kpi = await _get(
        "/kpi-summary",
        {
            "scope": "range",
            "start_date": start,
            "end_date": end,
            "fast_mode": True,
            **({"district_name": district} if district else {}),
        },
    )
    regions = await _get(
        "/cockpit-smart-side-insights",
        {"start_date": start, "end_date": end},
    )
    goods = await _get(
        "/goods-top",
        {"start_date": start, "end_date": end, "limit": 10, **({"district_name": district} if district else {})},
    )
    trend = await _get(
        "/orders-daily",
        {"start_date": start, "end_date": end, **({"district_name": district} if district else {})},
    )

    def _fmt_money(v: Any) -> str:
        try:
            n = float(v or 0)
        except Exception:
            n = 0.0
        if n >= 100000000:
            return f"¥{n/100000000:.2f}亿"
        if n >= 10000:
            return f"¥{n/10000:.1f}万"
        return f"¥{n:,.0f}"

    title_type = {"daily": "日报", "weekly": "周报", "monthly": "月报"}.get(report_type, "报告")
    title = f"{title_type}（{start} ~ {end}）"
    if district:
        title += f" · {district}"

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## 一、核心指标")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---|")
    lines.append(f"| 订单数 | {int(kpi.get('order_count') or 0):,} |")
    lines.append(f"| GMV | {_fmt_money(kpi.get('gmv'))} |")
    lines.append(f"| 客单价 | {_fmt_money(kpi.get('avg_ticket'))} |")
    lines.append(f"| 去重买家 | {int(kpi.get('distinct_buyers') or 0):,} |")
    lines.append(f"| 退货金额占比 | {float(kpi.get('return_rate_by_amount_pct') or 0):.2f}% |")
    lines.append("")

    lines.append("## 二、区域 TOP（按 GMV）")
    lines.append("")
    kd = regions.get("key_districts") or []
    if kd:
        lines.append("| 排名 | 区域 | GMV | 订单数 | 环比 |")
        lines.append("|---|---|---|---|---|")
        for i, r in enumerate(kd[:10], start=1):
            mom = r.get("mom_pct")
            mom_str = "—" if mom is None else f"{mom:+.1f}%"
            lines.append(
                f"| {i} | **{r.get('district_name') or '—'}** | {_fmt_money(r.get('gmv'))} "
                f"| {int(r.get('order_count') or 0):,} | {mom_str} |"
            )
    else:
        lines.append("_暂无区域数据_")
    lines.append("")

    lines.append("## 三、品类 TOP（按金额）")
    lines.append("")
    gs = goods.get("rows") or []
    if gs:
        lines.append("| 排名 | 商品 | 销量 | 金额 |")
        lines.append("|---|---|---|---|")
        for i, r in enumerate(gs[:10], start=1):
            lines.append(
                f"| {i} | **{r.get('goods_name') or '—'}** | {int(float(r.get('total_qty') or 0)):,} "
                f"| {_fmt_money(r.get('total_amount'))} |"
            )
    else:
        lines.append("_暂无品类数据_")
    lines.append("")

    lines.append("## 四、每日趋势")
    lines.append("")
    series = trend.get("series") or []
    if series:
        lines.append("| 日期 | 订单数 | GMV |")
        lines.append("|---|---|---|")
        for r in series[-14:]:
            lines.append(
                f"| {r.get('day')} | {int(r.get('order_count') or 0):,} | {_fmt_money(r.get('gmv'))} |"
            )
    else:
        lines.append("_暂无趋势数据_")
    lines.append("")

    lines.append("## 五、建议")
    lines.append("")
    lines.append("- 关注 **环比下降** 的区域，加强补货与客情维护。")
    lines.append("- 稳住 **头部品类** 库存，挖掘腰部品类增长潜力。")
    lines.append("- 针对客单价变动，评估是否需要促销/组合套餐。")

    markdown = "\n".join(lines)
    return {
        "report_type": report_type,
        "title": title,
        "start_date": start,
        "end_date": end,
        "markdown": markdown,
    }


async def _generate_analytical_brief(
    report_type: str,
    start: str,
    end: str,
    district: Optional[str],
    topic: str,
) -> dict[str, Any]:
    """proposal / insight_brief：先并行多源拉数，拼一份「数据摘要包 + 写作纲要」，
    交给 answerer LLM 去写章节型长文（由 answerer 输出 <report_content>）。
    """
    import asyncio as _aio

    dn = {"district_name": district} if district else {}

    # 并行取数：KPI / 区域 / 品类 / 单品 / 趋势 / 行情 / 今日预警 / 退货趋势
    kpi, regions, category, goods, trend, xinfadi, alerts, backorder = await _aio.gather(
        _get("/kpi-summary", {"scope": "range", "start_date": start, "end_date": end, "fast_mode": True, **dn}),
        _get("/cockpit-smart-side-insights", {"start_date": start, "end_date": end, **dn}),
        _get("/category-distribution", {"start_date": start, "end_date": end, "limit": 10}),
        _get("/goods-top", {"start_date": start, "end_date": end, "limit": 10, **dn}),
        _get("/orders-daily", {"start_date": start, "end_date": end, **dn}),
        _get("/xinfadi-summary-series", {"start_date": start, "end_date": end}),
        _get("/ops-alerts", {"limit": 10, **dn}),
        _get("/backorder-daily", {"start_date": start, "end_date": end}),
        return_exceptions=True,
    )

    def _safe(v: Any) -> Any:
        """gather 里即便抛异常也不能污染数据包。"""
        return v if not isinstance(v, BaseException) else {"_error": str(v)[:200]}

    kind_zh = "企划案" if report_type == "proposal" else "经营分析简报"
    title = f"{kind_zh}（{start} ~ {end}）"
    if topic:
        title += f" · {topic}"
    if district:
        title += f" · {district}"

    # 提供一份规范化的「写作纲要」让 answerer 照着填
    if report_type == "proposal":
        outline = [
            "# {title}",
            "",
            "## 一、背景与目标",
            "- 基于下方真实数据，用 1-2 段说明当前形势与主题「{topic}」的提出理由；",
            "- 明确要达成的 1-2 个可量化目标（如 GMV / 新客数 / 品类渗透）。",
            "",
            "## 二、数据洞察（必须引用下方真实数字）",
            "- 引用 KPI、环比、品类/区域头部、退货情况、外部行情（新发地）",
            "- 至少出现 3 个以上的具体数字，不得编造。",
            "",
            "## 三、机会点与风险",
            "- 基于数据提炼机会（例：某区域环比高增、某品类客单价抬升）；",
            "- 同步列出风险（退货上升 / 行情剧烈波动 / 覆盖区县收缩）。",
            "",
            "## 四、策略动作（方案主体）",
            "- 至少 3 条，可执行、可度量；区分人群 / 品类 / 区域 / 渠道；",
            "- 每条动作注明负责团队（建议）与预期效果。",
            "",
            "## 五、资源与排期",
            "- 预算框架（人 / 货 / 场）、时间线（2-4 周为宜）；",
            "- 关键里程碑。",
            "",
            "## 六、风控与复盘指标",
            "- 明确预警线（退货率、客单价、区域 GMV 环比）；",
            "- 约定一个复盘时点。",
        ]
    else:
        outline = [
            "# {title}",
            "",
            "## 一、经营摘要",
            "- 用 1 段总结窗口期（{start} ~ {end}）的总体表现；引用 KPI 关键数字。",
            "",
            "## 二、核心指标对比",
            "- 订单数 / GMV / 客单价 / 退货占比；如有环比必须引用。",
            "",
            "## 三、区域与品类结构",
            "- 区域 TOP & 环比异常；品类头部/腰部增长点；",
            "- 引用真实数字，不许凭空。",
            "",
            "## 四、异常与归因",
            "- 若有预警（今日 ops-alerts）或退货上扬，点名指出并做归因假设；",
            "- 同时参考新发地行情是否拉动/挤压某品类。",
            "",
            "## 五、行动建议",
            "- 3-5 条，指向可调整的人/货/场动作；",
            "- 附短期（本周）与中期（本月）两档。",
        ]
    outline_md = "\n".join(outline).format(title=title, topic=topic or "未指定", start=start, end=end)

    return {
        "report_type": report_type,
        "title": title,
        "start_date": start,
        "end_date": end,
        "topic": topic or None,
        "district_name": district,
        "kind_zh": kind_zh,
        "writing_outline_markdown": outline_md,
        "data_pack": {
            "kpi": _safe(kpi),
            "regions": _safe(regions),
            "category_distribution": _safe(category),
            "goods_top": _safe(goods),
            "trend_daily": _safe(trend),
            "xinfadi_price": _safe(xinfadi),
            "ops_alerts": _safe(alerts),
            "backorder_trend": _safe(backorder),
        },
        "instruction_for_llm": (
            "这是用于生成长文的数据包与写作纲要。"
            "请严格以 writing_outline_markdown 为骨架，引用 data_pack 中的真实数字（包括具体日期、区县名、品类名、金额），"
            "不要编造数据；输出时把完整的长文 Markdown 放进 <report_content>…</report_content> 标签，"
            "自然语言摘要放在标签之前（2-3 句即可）。"
        ),
    }


# ---------------------------------------------------------------------------
# PII 温和脱敏（仅作用于 get_top_members 等暴露个人字段的工具）
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")


def _mask_name(n: Any) -> str:
    """保留首字，其后统一用 `**`。例：「张三」→「张**」。"""
    s = str(n or "").strip()
    if not s:
        return ""
    # 对英文名也做同样处理
    return s[0] + "**"


def _mask_phone(s: Any) -> str:
    """脱敏大陆手机号：13812345678 → 138****5678。"""
    return _PHONE_RE.sub(lambda m: f"{m.group(1)}****{m.group(3)}", str(s or ""))


def _mask_member_row(r: dict[str, Any]) -> dict[str, Any]:
    """对会员 TOP 行做温和脱敏：姓名保留首字、手机号保留前 3 后 4。
    其它字段（GMV、订单数等聚合指标）完全保留。"""
    if not isinstance(r, dict):
        return r
    out = dict(r)
    for k in ("member_name", "name", "buyer_name"):
        if k in out and out[k]:
            out[k] = _mask_name(out[k])
    for k in ("member_phone", "phone", "mobile", "buyer_phone"):
        if k in out and out[k]:
            out[k] = _mask_phone(out[k])
    # 常见「nickname」也遮一下
    if "nickname" in out and out["nickname"]:
        out["nickname"] = _mask_name(out["nickname"])
    return out


def tool_result_content(data: Any) -> str:
    """把工具返回转成 LLM 侧 tool role 的 content（JSON 文本；裁剪过长）。"""
    try:
        s = json.dumps(data, ensure_ascii=False)
    except Exception:
        s = str(data)
    # DashScope qwen-plus 上下文足够，但仍保护性裁剪
    return s if len(s) <= 12000 else s[:12000] + "...[truncated]"
