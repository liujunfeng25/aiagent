# 业务库 orders 等：字段名以实表为准（助手已在运行环境对 shixunwang.orders 执行 SHOW COLUMNS 校准）。
# 库内全部表枚举：GET /api/insights/business/meta/tables
# 说明文档：同目录 data_catalog.md

ORDERS_TABLE = "orders"
ORDERS_PK_COL = "id"
ORDERS_SN_COL = "order_sn"
ORDERS_TIME_COL = "add_time"  # int unsigned UNIX 时间戳，上的 MUL 索引
ORDERS_AMOUNT_COL = "total_amount"
ORDERS_MEMBER_COL = "member_id"
ORDERS_MEMBER_NAME_COL = "member_realname"  # varchar(100)
ORDERS_MEMBER_LOGIN_COL = "member_name"  # varchar(20)，与 realname 并列展示用

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

# 单品排名：表/字段不写死。运行时见 order_items_resolver（优先 orders_items；本地样例库若有 order_goods 会在候选表中被匹配）

TOP_GOODS_MAX = 20
TOP_GOODS_DEFAULT = 10

TOP_REGIONS_MAX = 20
TOP_REGIONS_DEFAULT = 10
