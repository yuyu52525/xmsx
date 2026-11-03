-- ============================================================
-- 数据清洗（一）重复值检测与去重
-- 背景：ods_order 共 15600 行，order_id 去重后 15000 个
-- 策略：
--   1) 先用 distinct * 判断是否「整行完全重复」
--   2) 用 row_number() 按 order_id 分区、order_time 倒序取第一条
-- 输出：dwd_order
-- ============================================================
use ydsh_ods;

-- ------------------------------------------------------------
-- 1. 重复类型判定
-- ------------------------------------------------------------
select 'ods_order 总行数'        as metric, count(*) as val from ods_order
union all
select 'order_id 去重数',        count(distinct order_id) from ods_order
union all
select '整行去重后行数',         count(*) from (select distinct * from ods_order) t;

-- ------------------------------------------------------------
-- 2. 去重：同一 order_id 保留 order_time 最新的一条
-- ------------------------------------------------------------
drop table if exists dwd_order;

create table dwd_order as
select
  order_id, user_id, store_id, order_date, order_time,
  pay_amount, discount_amount, pay_type, order_status, channel
from (
  select
    order_id, user_id, store_id, order_date, order_time,
    pay_amount, discount_amount, pay_type, order_status, channel,
    row_number() over (partition by order_id order by order_time desc) as rn
  from ods_order
) t
where rn = 1;

-- ------------------------------------------------------------
-- 3. 校验：去重前后行数差应等于重复行数
-- ------------------------------------------------------------
select 'dwd_order 行数' as metric, count(*) as val from dwd_order
union all
select 'order_id 唯一数', count(distinct order_id) from dwd_order
union all
select '剩余重复 order_id 数', count(*) from (
  select order_id from dwd_order group by order_id having count(*) > 1
) d;
