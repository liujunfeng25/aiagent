# Chat 回归报告（2026-04-21 16:48:21）

## 总览

- 用例总数：16
- 通过数：13
- 通过率：81.2%
- P50 响应：2.79s
- P95 响应：31.84s

## 工具命中分布

- generate_report: 7
- get_daily_trend: 2
- get_kpi_summary: 1
- get_region_rank: 1
- get_category_distribution: 1
- get_ops_alerts: 1
- get_xinfadi_price: 1
- get_today_orders: 1

## 失败样例

- `proposal-report` | 39.46s | tools=['generate_report'] | tool=True output=True format=True latency=False
  - reply: <report_content># 企划案（2026-03-23 ~ 2026-04-21） · 海淀区夏季促销  ## 一、背景与目标   当前海淀区在全市13个覆盖区县中表现稳健：近30天（2026-03-23至2026-04-21）实
- `insight-brief` | 29.30s | tools=['generate_report'] | tool=True output=True format=True latency=False
  - reply: <report_content># 经营分析简报（2026-03-23 ~ 2026-04-21）  ## 一、经营摘要   本分析周期（3月23日–4月21日）共实现 **GMV ¥1,732.12万元**，订单数 **8,657单**，
- `schema-coverage` | 2.45s | tools=[] | tool=False output=True format=True latency=True
  - reply: 请问您想查询哪类数据？例如销售排名、商品排名、日报/周报/月报、企划案、经营简报、区域趋势或KPI指标等？

## 样例明细（前20）

- `kpi-today` | 4.03s | pass=True | tools=['get_kpi_summary'] | card=True chart=False report=False
- `rank-region` | 4.03s | pass=True | tools=['get_region_rank'] | card=True chart=False report=False
- `rank-category-month` | 5.88s | pass=True | tools=['get_category_distribution'] | card=True chart=False report=False
- `trend-7days-chart` | 0.09s | pass=True | tools=['get_daily_trend'] | card=True chart=True report=False
- `trend-20days-chart` | 0.10s | pass=True | tools=['get_daily_trend'] | card=True chart=True report=False
- `ops-alerts` | 3.90s | pass=True | tools=['get_ops_alerts'] | card=True chart=False report=False
- `xinfadi-price` | 4.16s | pass=True | tools=['get_xinfadi_price'] | card=True chart=True report=False
- `today-orders` | 3.14s | pass=True | tools=['get_today_orders'] | card=True chart=False report=False
- `daily-report-default-docx` | 0.57s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `weekly-report-default-docx` | 0.68s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `monthly-report-default-docx` | 1.45s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `report-ppt-request` | 0.52s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `report-md-request` | 0.52s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `proposal-report` | 39.46s | pass=False | tools=['generate_report'] | card=False chart=False report=True
- `insight-brief` | 29.30s | pass=False | tools=['generate_report'] | card=False chart=False report=True
- `schema-coverage` | 2.45s | pass=False | tools=[] | card=False chart=False report=False