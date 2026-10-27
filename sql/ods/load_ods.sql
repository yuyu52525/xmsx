-- ============================================================
-- ODS 层数据导入脚本
-- 前提：6 个 CSV 已放到项目 ./data/csv/ 目录（容器内挂载为 /data）
-- 执行：
--   docker exec -it hive-server beeline -u jdbc:hive2://localhost:10000 -f /data/load_ods.sql
-- ============================================================

use ydsh_ods;

load data local inpath '/data/ods_user.csv'          into table ods_user;
load data local inpath '/data/ods_product.csv'       into table ods_product;
load data local inpath '/data/ods_store.csv'         into table ods_store;
load data local inpath '/data/ods_order.csv'         into table ods_order;
load data local inpath '/data/ods_order_item.csv'    into table ods_order_item;
load data local inpath '/data/ods_user_behavior.csv' into table ods_user_behavior;

-- ------------------------------------------------------------
-- 行数校验（预期值见数据字典）
-- ------------------------------------------------------------
select 'ods_user'          as tbl, count(*) as cnt from ods_user
union all
select 'ods_product',       count(*) from ods_product
union all
select 'ods_store',         count(*) from ods_store
union all
select 'ods_order',         count(*) from ods_order
union all
select 'ods_order_item',    count(*) from ods_order_item
union all
select 'ods_user_behavior', count(*) from ods_user_behavior;
