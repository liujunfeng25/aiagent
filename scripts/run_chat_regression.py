#!/usr/bin/env python3
"""批量回归测试 AI 对话质量（正确性/耗时/美观）。

用法：
  python scripts/run_chat_regression.py
  python scripts/run_chat_regression.py --base-url http://127.0.0.1:8000/api --pretty
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "scripts" / "chat_regression_cases.json"
OUT_DIR = ROOT / "scripts" / "out"


@dataclass
class CaseResult:
    case_id: str
    query: str
    latency_sec: float
    ok_http: bool
    tools: list[str]
    has_card: bool
    has_chart: bool
    has_report: bool
    export_formats: list[str]
    tool_pass: bool
    output_pass: bool
    format_pass: bool
    latency_pass: bool
    pass_all: bool
    reply_preview: str
    error: str = ""


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    i = (len(sorted_vals) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def post_json(url: str, payload: dict[str, Any], timeout_sec: float) -> tuple[int, dict[str, Any]]:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=raw, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return int(resp.status), json.loads(body)


def check_tool(expect_any: list[str], expect_all: list[str], got_tools: list[str]) -> bool:
    s = set(got_tools)
    ok_any = True if not expect_any else bool(s.intersection(expect_any))
    ok_all = True if not expect_all else set(expect_all).issubset(s)
    return ok_any and ok_all


def check_output(expect_output: str, has_card: bool, has_chart: bool, has_report: bool) -> bool:
    if expect_output == "card":
        return has_card and not has_report
    if expect_output == "chart":
        return has_card and has_chart
    if expect_output == "report":
        return has_report
    if expect_output == "plain":
        return not has_card and not has_report
    return True


def check_formats(expect_formats: list[str], got_formats: list[str]) -> bool:
    if not expect_formats:
        return True
    return set(expect_formats) == set(got_formats or [])


def run_case(base_url: str, case: dict[str, Any], timeout_sec: float) -> CaseResult:
    query = str(case.get("query") or "")
    case_id = str(case.get("id") or query[:24] or "case")
    t0 = time.time()
    try:
        code, data = post_json(
            f"{base_url.rstrip('/')}/chat",
            {"messages": [{"role": "user", "content": query}]},
            timeout_sec=timeout_sec,
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError, Exception) as e:
        dt = time.time() - t0
        return CaseResult(
            case_id=case_id,
            query=query,
            latency_sec=round(dt, 3),
            ok_http=False,
            tools=[],
            has_card=False,
            has_chart=False,
            has_report=False,
            export_formats=[],
            tool_pass=False,
            output_pass=False,
            format_pass=False,
            latency_pass=False,
            pass_all=False,
            reply_preview="",
            error=str(e),
        )

    dt = time.time() - t0
    debug = data.get("debug") or {}
    tools = [str(x.get("name") or "") for x in (debug.get("tool_calls") or [])]
    has_card = isinstance(data.get("data_card"), dict)
    has_report = bool(data.get("report_content"))
    has_chart = bool((data.get("data_card") or {}).get("chart")) if has_card else False
    export_formats = data.get("export_formats") or []
    reply_preview = str(data.get("reply") or "").replace("\n", " ")[:120]

    tool_pass = check_tool(
        expect_any=list(case.get("expect_tools_any") or []),
        expect_all=list(case.get("expect_tools_all") or []),
        got_tools=tools,
    )
    output_pass = check_output(
        expect_output=str(case.get("expect_output") or ""),
        has_card=has_card,
        has_chart=has_chart,
        has_report=has_report,
    )
    format_pass = check_formats(
        expect_formats=list(case.get("expect_export_formats") or []),
        got_formats=[str(x) for x in export_formats],
    )
    max_sec = float(case.get("max_sec") or 0)
    latency_pass = True if max_sec <= 0 else dt <= max_sec

    pass_all = bool(code == 200 and tool_pass and output_pass and format_pass and latency_pass)
    return CaseResult(
        case_id=case_id,
        query=query,
        latency_sec=round(dt, 3),
        ok_http=code == 200,
        tools=tools,
        has_card=has_card,
        has_chart=has_chart,
        has_report=has_report,
        export_formats=[str(x) for x in export_formats],
        tool_pass=tool_pass,
        output_pass=output_pass,
        format_pass=format_pass,
        latency_pass=latency_pass,
        pass_all=pass_all,
        reply_preview=reply_preview,
    )


def build_markdown_report(summary: dict[str, Any], results: list[CaseResult]) -> str:
    lines: list[str] = []
    lines.append(f"# Chat 回归报告（{summary['timestamp']}）")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append(f"- 用例总数：{summary['total_cases']}")
    lines.append(f"- 通过数：{summary['passed_cases']}")
    lines.append(f"- 通过率：{summary['pass_rate_pct']:.1f}%")
    lines.append(f"- P50 响应：{summary['latency_p50_sec']:.2f}s")
    lines.append(f"- P95 响应：{summary['latency_p95_sec']:.2f}s")
    lines.append("")
    lines.append("## 工具命中分布")
    lines.append("")
    for name, cnt in summary["tool_coverage_top10"]:
        lines.append(f"- {name}: {cnt}")
    lines.append("")
    lines.append("## 失败样例")
    lines.append("")
    failed = [r for r in results if not r.pass_all]
    if not failed:
        lines.append("- 无失败样例")
    else:
        for r in failed:
            lines.append(
                f"- `{r.case_id}` | {r.latency_sec:.2f}s | tools={r.tools} | "
                f"tool={r.tool_pass} output={r.output_pass} format={r.format_pass} latency={r.latency_pass}"
            )
            if r.error:
                lines.append(f"  - error: {r.error}")
            else:
                lines.append(f"  - reply: {r.reply_preview}")
    lines.append("")
    lines.append("## 样例明细（前20）")
    lines.append("")
    for r in results[:20]:
        lines.append(
            f"- `{r.case_id}` | {r.latency_sec:.2f}s | pass={r.pass_all} | "
            f"tools={r.tools} | card={r.has_card} chart={r.has_chart} report={r.has_report}"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run chat regression suite")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/api", help="API base URL")
    ap.add_argument("--cases", default=str(DEFAULT_CASES), help="Cases JSON path")
    ap.add_argument("--timeout-sec", type=float, default=240.0, help="Per-case timeout seconds")
    ap.add_argument("--pretty", action="store_true", help="Pretty print JSON output")
    args = ap.parse_args()

    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"[ERR] cases file not found: {cases_path}", file=sys.stderr)
        return 2

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        print(f"[ERR] invalid cases: {cases_path}", file=sys.stderr)
        return 2

    results: list[CaseResult] = []
    for c in cases:
        r = run_case(args.base_url, c, timeout_sec=args.timeout_sec)
        results.append(r)
        print(
            json.dumps(
                {
                    "id": r.case_id,
                    "sec": r.latency_sec,
                    "pass": r.pass_all,
                    "tools": r.tools,
                    "card": r.has_card,
                    "chart": r.has_chart,
                    "report": r.has_report,
                    "formats": r.export_formats,
                    "error": r.error,
                },
                ensure_ascii=False,
            )
        )

    lat = sorted([r.latency_sec for r in results])
    passed = sum(1 for r in results if r.pass_all)
    tool_counter = Counter()
    for r in results:
        for t in r.tools:
            if t:
                tool_counter[t] += 1

    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_url": args.base_url,
        "cases_file": str(cases_path),
        "total_cases": len(results),
        "passed_cases": passed,
        "pass_rate_pct": (passed * 100.0 / len(results)) if results else 0.0,
        "latency_p50_sec": statistics.median(lat) if lat else 0.0,
        "latency_p95_sec": percentile(lat, 0.95),
        "tool_coverage_top10": tool_counter.most_common(10),
    }

    payload = {
        "summary": summary,
        "results": [r.__dict__ for r in results],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = OUT_DIR / f"chat_regression_report_{ts}.json"
    out_md = OUT_DIR / f"chat_regression_report_{ts}.md"
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None),
        encoding="utf-8",
    )
    out_md.write_text(build_markdown_report(summary, results), encoding="utf-8")

    print("")
    print(f"[OK] JSON: {out_json}")
    print(f"[OK] MARKDOWN: {out_md}")
    print(
        f"[OK] pass_rate={summary['pass_rate_pct']:.1f}% "
        f"P50={summary['latency_p50_sec']:.2f}s P95={summary['latency_p95_sec']:.2f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

