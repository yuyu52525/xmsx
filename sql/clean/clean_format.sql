-- ============================================================
-- 数据清洗（二）· 子任务 2：异常值处理 + 格式标准化
-- ------------------------------------------------------------
-- 依赖：clean_enum.sql 生成的
--   ydsh_dwd.stg_user_enum / stg_product_enum / stg_order_enum / stg_behavior_enum
--   （以及原始明细表 ydsh_ods.ods_order_item）
-- 输出：ydsh_dwd.stg_user_fmt / stg_product_fmt / stg_order_fmt
--       stg_item_fmt / stg_behavior_fmt
-- ------------------------------------------------------------
-- 异常值判定依据（全部基于真实分位数扫描，见 docs/evidence/scan_ods.txt）：
--   1) 订单金额：中位数 2,542.53，Q1=1,293.39，Q3=3,809.12，P95=4,835.89
--      正常订单金额区间 0～5,000 元（14,978 条），>100,000 元 312 条为注入异常，
--      5,000～100,000 之间 0 条 —— 业务断崖清晰。
--      P99 = 5,516,776.62 已被异常值污染（占比 3.8%，超过 1%），
--      因此放弃 P99 口径，改用 IQR 箱线图法：上限 = Q3 + 3×IQR = 11,356.33 元。
--   2) 购买数量：正常取值只有 1～5（36,468 条），另有 0/负数（718 条）与 99（363 条），
--      99 为正常最大值的近 20 倍，判为异常；负数/0 无业务含义。
--   3) 商品价格：正常区间 1～10,000 元（564 条），负数 20 条、>100,000 元 16 条。
--      维度表不能删行（会被事实表外键引用），按「同类目商品价格中位数」修正并打标。
--   4) 明细单价：773 条 unit_price <= 0（最低 -8,992.96），会使明细金额为负、分摊失效，
--      按「同商品有效单价中位数」修正；无有效单价的回退到该商品售价。
-- ============================================================

use ydsh_dwd;

-- ------------------------------------------------------------
-- 1. 订单表：删除负金额与超大金额订单，统一日期格式
-- ------------------------------------------------------------
drop table if exists stg_order_fmt;

create table stg_order_fmt as
select
  order_id,
  user_id,
  store_id,
  case when trim(order_date) rlike '^[0-9]{8}$'
       then concat(substr(trim(order_date), 1, 4), '-', substr(trim(order_date), 5, 2), '-', substr(trim(order_date), 7, 2))
       else regexp_replace(trim(order_date), '/', '-') end                as order_date,
  lpad(split(trim(order_time), ':')[0], 2, '0')                           as order_hh,
  trim(order_time)                                                        as order_time,
  pay_amount,
  discount_amount,
  pay_type,
  order_status,
  channel
from stg_order_enum
where pay_amount > 0                -- 剔除负金额（业务上不成立）
  and pay_amount <= 11356.33;       -- 剔除超大金额（Q3 + 3×IQR）

-- ------------------------------------------------------------
-- 2. 用户表：注册日期、手机号格式统一
-- ------------------------------------------------------------
drop table if exists stg_user_fmt;

create table stg_user_fmt as
select
  user_id,
  user_name,
  gender,
  age,
  city,
  province,
  case when trim(register_date) rlike '^[0-9]{8}$'
       then concat(substr(trim(register_date), 1, 4), '-', substr(trim(register_date), 5, 2), '-', substr(trim(register_date), 7, 2))
       else regexp_replace(trim(register_date), '/', '-') end              as register_date,
  member_level,
  level_imputed,
  case when length(regexp_replace(trim(phone), '[^0-9]', '')) = 11
       then regexp_replace(trim(phone), '[^0-9]', '')
       else lpad(regexp_replace(trim(phone), '[^0-9]', ''), 11, '1') end    as phone,
  case when length(regexp_replace(trim(phone), '[^0-9]', '')) = 11 then 0 else 1 end as phone_fixed,
  email,
  email_missing,
  age_filled
from stg_user_enum;

-- ------------------------------------------------------------
-- 3. 商品表：异常价格按同类目中位数修正（维度表不删行，保证外键完整）
-- ------------------------------------------------------------
drop table if exists stg_product_med;
create table stg_product_med as
select category, percentile_approx(price, 0.5, 10000) as med_price
from stg_product_enum
where price > 0 and price <= 100000
group by category;

drop table if exists stg_product_fmt;

create table stg_product_fmt as
select
  p.product_id,
  p.product_name,
  p.category,
  p.sub_category,
  p.brand,
  case when p.price > 0 and p.price <= 100000 then p.price
       else round(coalesce(m.med_price, 0), 2) end                        as price,
  case when p.price > 0 and p.price <= 100000 then 0 else 1 end            as price_fixed,
  p.cost,
  p.stock,
  p.status,
  case when trim(p.launch_date) rlike '^[0-9]{8}$'
       then concat(substr(trim(p.launch_date), 1, 4), '-', substr(trim(p.launch_date), 5, 2), '-', substr(trim(p.launch_date), 7, 2))
       else regexp_replace(trim(p.launch_date), '/', '-') end              as launch_date,
  p.launch_date_filled
from stg_product_enum p
left join stg_product_med m on p.category = m.category;

-- ------------------------------------------------------------
-- 4. 订单明细：剔除数量异常行，单价异常按同商品中位数修正，折扣率收敛到 [0,1]
--    单价异常：773 条 unit_price <= 0（最低 -8,992.96），会导致明细金额为负，
--              修正为「该商品有效单价中位数」，无有效单价的回退到商品售价。
-- ------------------------------------------------------------
drop table if exists stg_item_qty;

create table stg_item_qty as
select
  item_id,
  order_id,
  product_id,
  quantity,
  case when unit_price > 0 and unit_price <= 100000 then unit_price else null end as unit_price_raw,
  case when discount < 0 then 0 when discount > 1 then 1 else discount end          as discount
from ydsh_ods.ods_order_item
where quantity >= 1
  and quantity <= 50;                     -- 正常最大购买量 5，>50 判为异常

drop table if exists stg_item_med;
create table stg_item_med as
select product_id, percentile_approx(unit_price_raw, 0.5, 10000) as med_price
from stg_item_qty
where unit_price_raw is not null
group by product_id;

drop table if exists stg_item_fmt;

create table stg_item_fmt as
select
  i.item_id,
  i.order_id,
  i.product_id,
  i.quantity,
  case when i.unit_price_raw is not null then i.unit_price_raw
       else round(coalesce(m.med_price, p.price, 0), 2) end     as unit_price,
  case when i.unit_price_raw is not null then 0 else 1 end      as price_fixed,
  i.discount
from stg_item_qty i
left join stg_item_med m   on i.product_id = m.product_id
left join stg_product_fmt p on i.product_id = p.product_id;

-- ------------------------------------------------------------
-- 5. 行为日志：behavior_time 统一为 yyyy-MM-dd HH:mm:ss
-- ------------------------------------------------------------
drop table if exists stg_behavior_fmt;

create table stg_behavior_fmt as
select
  behavior_id,
  user_id,
  product_id,
  behavior_type,
  concat(
    regexp_replace(substr(trim(behavior_time), 1, 10), '/', '-'),
    ' ',
    case when length(substr(trim(behavior_time), instr(trim(behavior_time), ' ') + 1)) = 5
         then concat(substr(trim(behavior_time), instr(trim(behavior_time), ' ') + 1), ':00')
         else substr(trim(behavior_time), instr(trim(behavior_time), ' ') + 1) end
  )                                                                        as behavior_time,
  session_id
from stg_behavior_enum;

-- ============================================================
-- 6. 校验
-- ============================================================
select '1) 清洗后行数（清洗前：order 15000 / item 37549 / user 1000 / product 600 / behavior 60000）' as check_item;
select 'order' as tbl, count(*) as after_cnt from stg_order_fmt;
select 'item' as tbl, count(*) as after_cnt from stg_item_fmt;
select 'user' as tbl, count(*) as after_cnt from stg_user_fmt;
select 'product' as tbl, count(*) as after_cnt from stg_product_fmt;
select 'behavior' as tbl, count(*) as after_cnt from stg_behavior_fmt;

-- 6.1 金额异常残留（应全为 0）
select sum(if(pay_amount < 0, 1, 0)) as neg, sum(if(pay_amount > 11356.33, 1, 0)) as huge,
       round(min(pay_amount), 2) as mn, round(max(pay_amount), 2) as mx
from stg_order_fmt;

-- 6.2 日期格式残留（应全为 0）
select 'order_date 非标准' as check_item, count(*) as bad_cnt from stg_order_fmt
where not order_date rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$';

select 'register_date 非标准' as check_item, count(*) as bad_cnt from stg_user_fmt
where not register_date rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$';

select 'launch_date 非标准' as check_item, count(*) as bad_cnt from stg_product_fmt
where not launch_date rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2}$';

select 'behavior_time 非标准' as check_item, count(*) as bad_cnt from stg_behavior_fmt
where not behavior_time rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$';

-- 6.3 手机号格式（应全部 11 位纯数字）
select length(phone) as phone_len, sum(phone_fixed) as fixed_cnt, count(*) as cnt
from stg_user_fmt group by length(phone);

-- 6.4 商品价格残留
select sum(if(price <= 0 or price > 100000, 1, 0)) as price_bad, sum(price_fixed) as price_fixed_cnt
from stg_product_fmt;

-- 6.5 购买数量残留
select min(quantity) as mn, max(quantity) as mx, count(*) as cnt from stg_item_fmt;

-- 6.6 明细单价残留（应全部 > 0）与修正条数
select sum(if(unit_price <= 0, 1, 0)) as price_bad,
       sum(price_fixed)               as price_fixed_cnt,
       round(min(unit_price), 2)      as mn,
       round(max(unit_price), 2)      as mx
from stg_item_fmt;