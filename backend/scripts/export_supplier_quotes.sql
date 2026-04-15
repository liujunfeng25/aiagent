-- =============================================================================
-- 按供应商维度导出：供货方 + 已报价 goods_id + 单价（及可选品名）
-- 使用前请将注释中的表名/列名改为与贵司业务库一致。
-- 智能分单代码中：supplier 表、supplier_goods 表；明细表名运行时解析（常见 orders_items）。
-- =============================================================================

-- ---------------------------------------------------------------------------
-- A. 最小集：仅 supplier + supplier_goods（无品名，仅有 goods_id）
-- ---------------------------------------------------------------------------
SELECT
    s.id AS supplier_db_id,
    TRIM(s.realname) AS supplier_name,
    sg.goods_id,
    NULL AS goods_name,
    CAST(sg.price AS DECIMAL(18, 4)) AS quote_unit_price
FROM supplier_goods sg
INNER JOIN supplier s ON s.id = sg.supplier_id
WHERE sg.price IS NOT NULL
  AND CAST(sg.price AS DECIMAL(18, 4)) > 0
ORDER BY supplier_name, sg.goods_id;


-- ---------------------------------------------------------------------------
-- B. 推荐：在 A 基础上，用「订单明细」反查品名（一行 goods_id 对应一个展示名）
--     将 orders_items 改为实表名；goods_id / goods_name 改为实列名。
-- ---------------------------------------------------------------------------
/*
SELECT
    s.id AS supplier_db_id,
    TRIM(s.realname) AS supplier_name,
    sg.goods_id,
    gi.goods_name,
    CAST(sg.price AS DECIMAL(18, 4)) AS quote_unit_price
FROM supplier_goods sg
INNER JOIN supplier s ON s.id = sg.supplier_id
LEFT JOIN (
    SELECT
        g.goods_id,
        MAX(TRIM(g.goods_name)) AS goods_name
    FROM orders_items g
    WHERE g.goods_id IS NOT NULL
    GROUP BY g.goods_id
) gi ON gi.goods_id = sg.goods_id
WHERE sg.price IS NOT NULL
  AND CAST(sg.price AS DECIMAL(18, 4)) > 0
ORDER BY supplier_name, gi.goods_name, sg.goods_id;
*/


-- ---------------------------------------------------------------------------
-- C. 若存在独立商品主数据表（示例名 goods），可改为：
--     INNER JOIN goods g ON g.id = sg.goods_id
--    再 SELECT g.xxx AS goods_name
-- ---------------------------------------------------------------------------
