-- 本地 MySQL：在 Navicat 中连接到实例后执行（若使用 docker-compose 中的 mysql 服务，镜像已通过 MYSQL_DATABASE 自动创建 agent，一般无需再执行）
-- Navicat 连接参数（docker-compose 默认映射）：主机 127.0.0.1，端口 3307，用户名 root，密码 116165，数据库 agent
-- 若本机 3306 未被占用且 compose 中改回 3306:3306，则端口填 3306
-- 后端「数据洞察」业务库：在 backend/.env 中可设 INSIGHTS_MYSQL_HOST=127.0.0.1、INSIGHTS_MYSQL_PORT=3307、INSIGHTS_MYSQL_PASSWORD=...（与上一致）

CREATE DATABASE IF NOT EXISTS `agent`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
