# 业务 MySQL 数据目录（驾驶舱 / 数据洞察）

白名单字段定义见同目录 [`schema.py`](./schema.py)。完整表结构以运行环境为准，可通过只读接口拉取：

`GET /api/insights/business/meta/tables`

返回当前 `resolve_business_mysql` 所连库中全部表的列名与类型（不含密码与连接串）。

## 已对接大屏 / 洞察的表

| 表名 | 用途 |
|------|------|
| `orders` | 订单主表：时间戳、金额、会员 |
| `order_goods` / `orders_items` 等 | 订单明细行（品名、数量、单价）；**线上常为 `orders_items`，且 `orders` 主键为 `id`（非 `order_id`）** |

## 单品 API 如何找明细表

`GET /goods-top` 会通过 `INFORMATION_SCHEMA` 自动匹配明细表（优先 `orders_items`，其次 `order_goods` 等），并按主表实际主键拼接 `JOIN`（`orders.order_id` 或 `orders.id`）。

手工指定（可选环境变量）：

| 变量 | 含义 |
|------|------|
| `INSIGHTS_ORDER_ITEMS_TABLE` | 明细表名，如 `orders_items` |
| `INSIGHTS_ORDER_ITEMS_FK` | 明细表上指向订单的列，默认自动识别 |
| `INSIGHTS_ORDERS_PK` | 订单主表主键列，如 `id` |
| `INSIGHTS_ORDER_ITEMS_NAME_COL` | 品名列 |
| `INSIGHTS_ORDER_ITEMS_PRICE_COL` | 单价列 |
| `INSIGHTS_ORDER_ITEMS_QTY_COLS` | 数量列，逗号分隔多个则按顺序 `COALESCE`，如 `needqty,sendqty` |
| `backorder` | 背单/缺货 |
| `chart_xinfadi_price_summary` | 新发地批发价日汇总 |

其他表是否适用于可视化，请以 `meta/tables` 结果为准再扩展白名单 SQL。
