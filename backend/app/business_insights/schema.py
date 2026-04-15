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
ORDERS_MEMBER_ADDRESS_COL = "member_address"  # 客户收货地址，智能排线/运距优先用
ORDERS_SEND_DATE_COL = "send_date"  # 送货日；智能排线筛选「今日订单」
ORDERS_REMARK_COL = "remark"  # 排线顺序（越早优先级越高，按升序）
ORDERS_DRIVER_ID_COL = "driver_id"  # 关联 driver 表；未指派为 NULL

DRIVER_TABLE = "driver"
DRIVER_PK_COL = "id"
DRIVER_CAR_PLATE_COL = "car_plate_no"
DRIVER_PHONE_COL = "phone"

BACKORDER_TABLE = "backorder"
BACKORDER_PK_COL = "id"
BACKORDER_SN_COL = "backorder_sn"
BACKORDER_ORDER_FK_COL = "order_id"
BACKORDER_STATUS_COL = "status"
BACKORDER_BACK_STATUS_COL = "back_status"
BACKORDER_TIME_COL = "add_time"
BACKORDER_AMOUNT_COL = "total_amount"
# 实库统计：back_status=3 为已完成占比极高；<=2 视为待处理退货（与 KPI 全量 backorder 口径区分）
BACKORDER_PENDING_BACK_STATUS_MAX = 2

DISORDER_TABLE = "disorder"
DISORDER_PK_COL = "id"
DISORDER_SN_COL = "disorder_sn"
DISORDER_STATUS_COL = "status"
# 实库 status=4 占比最高，视为已结案；!=4 视为分拣单待跟进
DISORDER_STATUS_DONE = 4

ORDERS_DISORDER_FK_COL = "disorder_id"

XINFADI_SUMMARY_TABLE = "chart_xinfadi_price_summary"
XINFADI_DATE_COL = "update_date"

# 老板看板：最多查近一年，减轻库压力
MAX_RANGE_DAYS = 366
DEFAULT_RANGE_DAYS = 30
# 智能驾驶舱（地图落点、区间 KPI、排名/趋势等未传日期时）：缩短默认窗口以控点数与负载
COCKPIT_DEFAULT_RANGE_DAYS = 7

TOP_MEMBERS_MAX = 50
TOP_MEMBERS_DEFAULT = 10

# 单品排名：表/字段不写死。运行时见 order_items_resolver（优先 orders_items；本地样例库若有 order_goods 会在候选表中被匹配）

TOP_GOODS_MAX = 20
TOP_GOODS_DEFAULT = 10

TOP_REGIONS_MAX = 20
TOP_REGIONS_DEFAULT = 10
