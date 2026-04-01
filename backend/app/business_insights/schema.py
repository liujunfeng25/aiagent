# 与 docker MySQL agent 库 DESCRIBE 结果对齐（orders / backorder / chart_xinfadi_price_summary）

ORDERS_TABLE = "orders"
ORDERS_TIME_COL = "add_time"  # int unsigned UNIX 时间戳
ORDERS_AMOUNT_COL = "total_amount"
ORDERS_MEMBER_COL = "member_id"
ORDERS_MEMBER_NAME_COL = "member_realname"

BACKORDER_TABLE = "backorder"
BACKORDER_TIME_COL = "add_time"
BACKORDER_AMOUNT_COL = "total_amount"

XINFADI_SUMMARY_TABLE = "chart_xinfadi_price_summary"
XINFADI_DATE_COL = "update_date"

# 老板看板：最多查近一年，减轻库压力
MAX_RANGE_DAYS = 366
DEFAULT_RANGE_DAYS = 30

TOP_MEMBERS_MAX = 50
TOP_MEMBERS_DEFAULT = 10
