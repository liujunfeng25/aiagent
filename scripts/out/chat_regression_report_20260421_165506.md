# Chat 回归报告（2026-04-21 16:55:06）

## 总览

- 用例总数：16
- 通过数：16
- 通过率：100.0%
- P50 响应：2.69s
- P95 响应：5.01s

## 工具命中分布

- generate_report: 7
- get_daily_trend: 2
- get_kpi_summary: 1
- get_region_rank: 1
- get_category_distribution: 1
- get_ops_alerts: 1
- get_xinfadi_price: 1
- get_today_orders: 1
- get_schema_overview: 1

## 失败样例

- 无失败样例

## 样例明细（前20）

- `kpi-today` | 4.11s | pass=True | tools=['get_kpi_summary'] | card=True chart=False report=False
- `rank-region` | 3.96s | pass=True | tools=['get_region_rank'] | card=True chart=False report=False
- `rank-category-month` | 4.90s | pass=True | tools=['get_category_distribution'] | card=True chart=False report=False
- `trend-7days-chart` | 0.09s | pass=True | tools=['get_daily_trend'] | card=True chart=True report=False
- `trend-20days-chart` | 0.10s | pass=True | tools=['get_daily_trend'] | card=True chart=True report=False
- `ops-alerts` | 3.61s | pass=True | tools=['get_ops_alerts'] | card=True chart=False report=False
- `xinfadi-price` | 4.10s | pass=True | tools=['get_xinfadi_price'] | card=True chart=True report=False
- `today-orders` | 3.68s | pass=True | tools=['get_today_orders'] | card=True chart=False report=False
- `daily-report-default-docx` | 0.57s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `weekly-report-default-docx` | 0.78s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `monthly-report-default-docx` | 1.78s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `report-ppt-request` | 0.55s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `report-md-request` | 0.48s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `proposal-report` | 4.62s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `insight-brief` | 5.33s | pass=True | tools=['generate_report'] | card=False chart=False report=True
- `schema-coverage` | 0.18s | pass=True | tools=['get_schema_overview'] | card=False chart=False report=False