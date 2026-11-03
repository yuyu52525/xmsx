-- ============================================================
-- 数据质量对比统计（清洗前 ODS vs 清洗后 DWD）
-- ------------------------------------------------------------
-- 修复率口径：修复率 = (清洗前问题数 - 清洗后问题数) / 清洗前问题数 × 100%
-- 五类脏数据：完整性(缺失) / 唯一性(重复) / 一致性(格式) / 准确性(异常值) / 有效性(枚举)
-- 每个指标一条独立语句，避免 Tez 计数器超限
-- ============================================================

-- ============================================================
-- 一、完整性：缺失值
-- ============================================================
select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'user.age 缺失' as metric,
         sum(if(src = 'ods' and age is null, 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and age is null, 1, 0)) as after_cnt
  from (select 'ods' as src, age from ydsh_ods.ods_user
        union all
        select 'dwd' as src, age from ydsh_dwd.dim_user) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'user.email 缺失（保留并打标）' as metric,
         sum(if(src = 'ods' and (email is null or trim(email) = ''), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and (email is null or trim(email) = ''), 1, 0)) as after_cnt
  from (select 'ods' as src, email from ydsh_ods.ods_user
        union all
        select 'dwd' as src, email from ydsh_dwd.dim_user) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'product.launch_date 缺失' as metric,
         sum(if(src = 'ods' and (launch_date is null or trim(launch_date) = ''), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and (launch_date is null or trim(launch_date) = ''), 1, 0)) as after_cnt
  from (select 'ods' as src, launch_date from ydsh_ods.ods_product
        union all
        select 'dwd' as src, launch_date from ydsh_dwd.dim_product) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order.pay_amount 缺失' as metric,
         sum(if(src = 'ods' and pay_amount is null, 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and pay_amount is null, 1, 0)) as after_cnt
  from (select 'ods' as src, pay_amount from ydsh_ods.ods_order
        union all
        select 'dwd' as src, pay_amount from ydsh_dwd.dwd_order) t
) s;

-- ============================================================
-- 二、唯一性：重复值
-- ============================================================
select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order 重复行数（总行数 - 唯一 order_id）' as metric,
         sum(if(src = 'ods', 1, 0)) - count(distinct if(src = 'ods', order_id, null)) as before_cnt,
         sum(if(src = 'dwd', 1, 0)) - count(distinct if(src = 'dwd', order_id, null)) as after_cnt
  from (select 'ods' as src, order_id from ydsh_ods.ods_order
        union all
        select 'dwd' as src, order_id from ydsh_dwd.dwd_order) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order_item / behavior 主键重复行数' as metric,
         sum(if(src = 'ods_item', 1, 0)) - count(distinct if(src = 'ods_item', id, null))
       + sum(if(src = 'ods_behavior', 1, 0)) - count(distinct if(src = 'ods_behavior', id, null)) as before_cnt,
         sum(if(src = 'dwd_item', 1, 0)) - count(distinct if(src = 'dwd_item', id, null))
       + sum(if(src = 'dwd_behavior', 1, 0)) - count(distinct if(src = 'dwd_behavior', id, null)) as after_cnt
  from (select 'ods_item' as src, item_id as id from ydsh_ods.ods_order_item
        union all
        select 'dwd_item', item_id from ydsh_dwd.dwd_order_item
        union all
        select 'ods_behavior', behavior_id from ydsh_ods.ods_user_behavior
        union all
        select 'dwd_behavior', behavior_id from ydsh_dwd.dwd_user_behavior) t
) s;

-- ============================================================
-- 三、一致性：格式不统一
-- ============================================================
select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'user.register_date 非标准格式' as metric,
         sum(if(src = 'ods' and not dt rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$', 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and not dt rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$', 1, 0)) as after_cnt
  from (select 'ods' as src, register_date as dt from ydsh_ods.ods_user
        union all
        select 'dwd' as src, register_date from ydsh_dwd.dim_user) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'user.phone 非 11 位纯数字' as metric,
         sum(if(src = 'ods' and not phone rlike '^[0-9]{11}$', 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and not phone rlike '^[0-9]{11}$', 1, 0)) as after_cnt
  from (select 'ods' as src, phone from ydsh_ods.ods_user
        union all
        select 'dwd' as src, phone from ydsh_dwd.dim_user) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order.order_date 非标准格式' as metric,
         sum(if(src = 'ods' and not dt rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$', 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and not dt rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$', 1, 0)) as after_cnt
  from (select 'ods' as src, order_date as dt from ydsh_ods.ods_order
        union all
        select 'dwd' as src, order_date from ydsh_dwd.dwd_order) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'behavior.behavior_time 非标准格式' as metric,
         sum(if(src = 'ods' and not dt rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$', 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and not dt rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$', 1, 0)) as after_cnt
  from (select 'ods' as src, behavior_time as dt from ydsh_ods.ods_user_behavior
        union all
        select 'dwd' as src, behavior_time from ydsh_dwd.dwd_user_behavior) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order.order_timestamp 非标准格式' as metric,
         0 as before_cnt,
         sum(if(src = 'dwd' and not ts rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$', 1, 0)) as after_cnt
  from (select 'dwd' as src, order_timestamp as ts from ydsh_dwd.dwd_order) t
) s;

-- ============================================================
-- 四、准确性：异常值
-- ============================================================
select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order.pay_amount 负金额' as metric,
         sum(if(src = 'ods' and pay_amount < 0, 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and pay_amount < 0, 1, 0)) as after_cnt
  from (select 'ods' as src, pay_amount from ydsh_ods.ods_order
        union all
        select 'dwd' as src, pay_amount from ydsh_dwd.dwd_order) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order.pay_amount 超大金额（>11356.33）' as metric,
         sum(if(src = 'ods' and pay_amount > 11356.33, 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and pay_amount > 11356.33, 1, 0)) as after_cnt
  from (select 'ods' as src, pay_amount from ydsh_ods.ods_order
        union all
        select 'dwd' as src, pay_amount from ydsh_dwd.dwd_order) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'user.age 异常（<1 或 >120）' as metric,
         sum(if(src = 'ods' and (age < 1 or age > 120), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and (age < 1 or age > 120), 1, 0)) as after_cnt
  from (select 'ods' as src, age from ydsh_ods.ods_user
        union all
        select 'dwd' as src, age from ydsh_dwd.dim_user) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'product.price 异常（<=0 或 >100000）' as metric,
         sum(if(src = 'ods' and (price <= 0 or price > 100000), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and (price <= 0 or price > 100000), 1, 0)) as after_cnt
  from (select 'ods' as src, price from ydsh_ods.ods_product
        union all
        select 'dwd' as src, price from ydsh_dwd.dim_product) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order_item.quantity 异常（<=0 或 >50）' as metric,
         sum(if(src = 'ods' and (quantity <= 0 or quantity > 50), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and (quantity <= 0 or quantity > 50), 1, 0)) as after_cnt
  from (select 'ods' as src, quantity from ydsh_ods.ods_order_item
        union all
        select 'dwd' as src, quantity from ydsh_dwd.dwd_order_item) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order_item.unit_price 异常（<=0）' as metric,
         sum(if(src = 'ods' and unit_price <= 0, 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and unit_price <= 0, 1, 0)) as after_cnt
  from (select 'ods' as src, unit_price from ydsh_ods.ods_order_item
        union all
        select 'dwd' as src, unit_price from ydsh_dwd.dwd_order_item) t
) s;

-- ============================================================
-- 五、有效性：枚举取值不规范（含取值种类收敛）
-- ============================================================
select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'user.gender 非规范取值' as metric,
         sum(if(src = 'ods' and gender not in ('男', '女', '未知'), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and gender not in ('男', '女', '未知'), 1, 0)) as after_cnt
  from (select 'ods' as src, gender from ydsh_ods.ods_user
        union all
        select 'dwd' as src, gender from ydsh_dwd.dim_user) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'user.member_level 非规范取值' as metric,
         sum(if(src = 'ods' and member_level not in ('普通会员', '银卡会员', '金卡会员', '钻石会员'), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and member_level not in ('普通会员', '银卡会员', '金卡会员', '钻石会员'), 1, 0)) as after_cnt
  from (select 'ods' as src, member_level from ydsh_ods.ods_user
        union all
        select 'dwd' as src, member_level from ydsh_dwd.dim_user) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order.order_status 非规范取值' as metric,
         sum(if(src = 'ods' and order_status not in ('待支付', '已支付', '已完成', '已取消', '退款中'), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and status_name not in ('待支付', '已支付', '已完成', '已取消', '退款中'), 1, 0)) as after_cnt
  from (select 'ods' as src, order_status, cast(null as string) as status_name from ydsh_ods.ods_order
        union all
        select 'dwd' as src, cast(null as string), status_name from ydsh_dwd.dwd_order) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order.pay_type 非规范取值' as metric,
         sum(if(src = 'ods' and pay_type not in ('支付宝', '微信支付', '银行卡', '货到付款'), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and pay_name not in ('支付宝', '微信支付', '银行卡', '货到付款'), 1, 0)) as after_cnt
  from (select 'ods' as src, pay_type, cast(null as string) as pay_name from ydsh_ods.ods_order
        union all
        select 'dwd' as src, cast(null as string), pay_name from ydsh_dwd.dwd_order) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'order.channel 非规范取值' as metric,
         sum(if(src = 'ods' and channel not in ('门店', 'APP', '小程序', 'PC官网'), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and channel_name not in ('门店', 'APP', '小程序', 'PC官网'), 1, 0)) as after_cnt
  from (select 'ods' as src, channel, cast(null as string) as channel_name from ydsh_ods.ods_order
        union all
        select 'dwd' as src, cast(null as string), channel_name from ydsh_dwd.dwd_order) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'behavior.behavior_type 非规范取值' as metric,
         sum(if(src = 'ods' and behavior_type not in ('浏览', '加购', '收藏', '购买'), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and behavior_type not in ('浏览', '加购', '收藏', '购买'), 1, 0)) as after_cnt
  from (select 'ods' as src, behavior_type from ydsh_ods.ods_user_behavior
        union all
        select 'dwd' as src, behavior_type from ydsh_dwd.dwd_user_behavior) t
) s;

select metric, before_cnt, after_cnt,
       if(before_cnt = 0, 0, round(100 * (before_cnt - after_cnt) / before_cnt, 2)) as fix_rate
from (
  select 'product.category 首尾空格/取值种类 16->8' as metric,
         sum(if(src = 'ods' and category <> trim(category), 1, 0)) as before_cnt,
         sum(if(src = 'dwd' and category <> trim(category), 1, 0)) as after_cnt
  from (select 'ods' as src, category from ydsh_ods.ods_product
        union all
        select 'dwd' as src, category from ydsh_dwd.dim_product) t
) s;

-- 取值种类收敛（清洗前 vs 清洗后 distinct 个数）
select 'gender' as field, count(distinct if(src = 'ods', v, null)) as ods_types,
       count(distinct if(src = 'dwd', v, null)) as dwd_types
from (select 'ods' as src, gender as v from ydsh_ods.ods_user
      union all select 'dwd', gender from ydsh_dwd.dim_user) t;

select 'member_level' as field, count(distinct if(src = 'ods', v, null)) as ods_types,
       count(distinct if(src = 'dwd', v, null)) as dwd_types
from (select 'ods' as src, member_level as v from ydsh_ods.ods_user
      union all select 'dwd', member_level from ydsh_dwd.dim_user) t;

select 'order_status' as field, count(distinct if(src = 'ods', v, null)) as ods_types,
       count(distinct if(src = 'dwd', v, null)) as dwd_types
from (select 'ods' as src, order_status as v from ydsh_ods.ods_order
      union all select 'dwd', status_name from ydsh_dwd.dwd_order) t;

select 'pay_type' as field, count(distinct if(src = 'ods', v, null)) as ods_types,
       count(distinct if(src = 'dwd', v, null)) as dwd_types
from (select 'ods' as src, pay_type as v from ydsh_ods.ods_order
      union all select 'dwd', pay_name from ydsh_dwd.dwd_order) t;

select 'channel' as field, count(distinct if(src = 'ods', v, null)) as ods_types,
       count(distinct if(src = 'dwd', v, null)) as dwd_types
from (select 'ods' as src, channel as v from ydsh_ods.ods_order
      union all select 'dwd', channel_name from ydsh_dwd.dwd_order) t;

select 'behavior_type' as field, count(distinct if(src = 'ods', v, null)) as ods_types,
       count(distinct if(src = 'dwd', v, null)) as dwd_types
from (select 'ods' as src, behavior_type as v from ydsh_ods.ods_user_behavior
      union all select 'dwd', behavior_type from ydsh_dwd.dwd_user_behavior) t;

select 'category' as field, count(distinct if(src = 'ods', v, null)) as ods_types,
       count(distinct if(src = 'dwd', v, null)) as dwd_types
from (select 'ods' as src, category as v from ydsh_ods.ods_product
      union all select 'dwd', category from ydsh_dwd.dim_product) t;