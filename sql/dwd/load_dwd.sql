-- ============================================================
-- 数据仓库 · DWD 层 ETL 加载脚本
-- ------------------------------------------------------------
-- 依赖：ydsh_ods.ods_store（门店原始表）
--       ydsh_dwd.stg_user_dim / stg_order_fact / stg_product_fmt
--                 / stg_item_fmt / stg_behavior_fmt（清洗二产物）
-- 加载顺序：dim_member_level/pay_type/order_status/channel（已由 clean_split_merge 建好）
--           → dim_user → dim_product → dim_store → dim_date
--           → dwd_order → dwd_order_item → dwd_user_behavior
-- ============================================================

use ydsh_dwd;

set hive.exec.dynamic.partition = true;
set hive.exec.dynamic.partition.mode = nonstrict;
set hive.exec.max.dynamic.partitions = 2000;
set hive.exec.max.dynamic.partitions.pernode = 500;
set hive.enforce.bucketing = true;
set hive.enforce.sorting = false;

-- ------------------------------------------------------------
-- 1. 用户维度
-- ------------------------------------------------------------
insert overwrite table dim_user
select
  user_id, user_name, gender, age, age_group, city, province, region, region_area,
  register_date, level_code, member_level, level_rank, level_imputed,
  phone, email, email_missing, age_filled
from stg_user_dim;

-- ------------------------------------------------------------
-- 2. 商品维度
-- ------------------------------------------------------------
insert overwrite table dim_product
select
  product_id, product_name, category, sub_category, brand,
  price, price_fixed, cost, stock, status, launch_date, launch_date_filled
from stg_product_fmt;

-- ------------------------------------------------------------
-- 3. 门店维度（门店表本身无脏数据，仅做去空格与地区合并）
-- ------------------------------------------------------------
insert overwrite table dim_store
select
  trim(store_id)                     as store_id,
  trim(store_name)                   as store_name,
  trim(province)                     as province,
  trim(city)                         as city,
  trim(district)                     as district,
  trim(address)                      as address,
  concat(trim(province), '-', trim(city)) as region,
  case when trim(province) in ('北京市', '天津市', '河北省', '山西省', '内蒙古自治区') then '华北'
       when trim(province) in ('辽宁省', '吉林省', '黑龙江省')                        then '东北'
       when trim(province) in ('上海市', '江苏省', '浙江省', '安徽省', '福建省', '山东省') then '华东'
       when trim(province) in ('河南省', '湖北省', '湖南省')                          then '华中'
       when trim(province) in ('广东省', '广西壮族自治区', '海南省')                   then '华南'
       when trim(province) in ('重庆市', '四川省', '贵州省', '云南省', '西藏自治区')    then '西南'
       when trim(province) in ('陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区') then '西北'
       else '其他' end                as region_area,
  case when trim(open_date) rlike '^[0-9]{8}$'
       then concat(substr(trim(open_date), 1, 4), '-', substr(trim(open_date), 5, 2), '-', substr(trim(open_date), 7, 2))
       else regexp_replace(trim(open_date), '/', '-') end as open_date,
  area,
  trim(manager)                      as manager
from ydsh_ods.ods_store;

-- ------------------------------------------------------------
-- 4. 时间维度：2023-01-01 ~ 2024-12-31 共 731 天
-- ------------------------------------------------------------
insert overwrite table dim_date
select
  date_format(d, 'yyyy-MM-dd')                                    as date_key,
  year(d)                                                         as year,
  quarter(d)                                                      as quarter,
  month(d)                                                        as month,
  date_format(d, 'yyyy-MM')                                       as month_key,
  day(d)                                                          as day,
  case when dayofweek(d) = 1 then 7 else dayofweek(d) - 1 end     as day_of_week,
  case dayofweek(d) when 1 then '周日' when 2 then '周一' when 3 then '周二' when 4 then '周三'
                    when 5 then '周四' when 6 then '周五' else '周六' end as weekday_name,
  if(dayofweek(d) in (1, 7), 1, 0)                                as is_weekend,
  weekofyear(d)                                                   as week_of_year
from (
  select date_add(to_date('2023-01-01'), t.i) as d
  from (select 1) dummy
  lateral view posexplode(split(space(730), ' ')) t as i, x
) s;

-- ------------------------------------------------------------
-- 5. 订单事实表（动态分区 + 分桶）
-- ------------------------------------------------------------
insert overwrite table dwd_order partition (order_month)
select
  order_id, user_id, store_id, order_date, order_time, order_timestamp, order_hour,
  pay_amount, discount_amount,
  pay_code, pay_name, status_code, status_name, is_paid, is_valid_revenue,
  channel_code, channel_name, is_online,
  order_month
from stg_order_fact;

-- ------------------------------------------------------------
-- 6. 订单明细事实表（仅保留有效订单的明细，并做金额分摊）
-- ------------------------------------------------------------
insert overwrite table dwd_order_item partition (order_month)
select
  item_id, order_id, user_id, product_id, store_id, order_date,
  quantity, unit_price, discount,
  round(item_amount, 2) as item_amount,
  case when order_amt > 0 then round(pay_amount * item_amount / order_amt, 2) else 0 end as alloc_amount,
  order_month
from (
  select
    i.item_id, i.order_id, o.user_id, i.product_id, o.store_id, o.order_date,
    i.quantity, i.unit_price, i.discount,
    i.quantity * i.unit_price * (1 - i.discount)                                        as item_amount,
    o.pay_amount,
    sum(i.quantity * i.unit_price * (1 - i.discount)) over (partition by i.order_id)     as order_amt,
    o.order_month
  from stg_item_fmt i
  join stg_order_fact o on i.order_id = o.order_id
) t;

-- ------------------------------------------------------------
-- 7. 用户行为事实表（动态分区）
-- ------------------------------------------------------------
insert overwrite table dwd_user_behavior partition (behavior_month)
select
  behavior_id, user_id, product_id, behavior_type, behavior_time,
  substr(behavior_time, 1, 10) as behavior_date,
  session_id,
  substr(behavior_time, 1, 7)  as behavior_month
from stg_behavior_fmt;

-- ============================================================
-- 8. 加载校验
-- ============================================================
select '1) 各表行数' as check_item;
select 'dim_user'         as tbl, count(*) as cnt from dim_user;
select 'dim_product'      as tbl, count(*) as cnt from dim_product;
select 'dim_store'        as tbl, count(*) as cnt from dim_store;
select 'dim_date'         as tbl, count(*) as cnt from dim_date;
select 'dwd_order'        as tbl, count(*) as cnt from dwd_order;
select 'dwd_order_item'   as tbl, count(*) as cnt from dwd_order_item;
select 'dwd_user_behavior' as tbl, count(*) as cnt from dwd_user_behavior;

select '2) 分区列表' as check_item;
show partitions dwd_order;

select '2b) 明细表分区' as check_item;
show partitions dwd_order_item;

select '2c) 行为表分区' as check_item;
show partitions dwd_user_behavior;

select '3) 时间维度范围' as check_item;
select min(date_key) as mn, max(date_key) as mx, count(*) as cnt,
       sum(is_weekend) as weekend_cnt
from dim_date;

-- 4) 外键完整性（应全为 0）
select '4) 事实表外键孤儿数（应全为 0）' as check_item;
select count(*) as order_user_orphan
from dwd_order o left join dim_user u on o.user_id = u.user_id where u.user_id is null;
select count(*) as order_store_orphan
from dwd_order o left join dim_store s on o.store_id = s.store_id where s.store_id is null;
select count(*) as item_product_orphan
from dwd_order_item i left join dim_product p on i.product_id = p.product_id where p.product_id is null;
select count(*) as behavior_product_orphan
from dwd_user_behavior b left join dim_product p on b.product_id = p.product_id where p.product_id is null;

-- 5) 金额分摊闭合：有明细的订单，其实付合计 应等于 明细分摊合计
select '5) 明细分摊金额 vs 有明细订单实付' as check_item;
select
  (select round(sum(alloc_amount), 2) from dwd_order_item) as item_alloc_sum;
select round(sum(o.pay_amount), 2) as pay_sum_of_orders_with_items
from dwd_order o
join (select distinct order_id, order_month from dwd_order_item) i
  on o.order_id = i.order_id and o.order_month = i.order_month;

-- 6) 分类汇总校验：订单数与 GMV 应与清洗后中间表一致
select '6) 订单数与 GMV' as check_item;
select count(*) as orders, round(sum(pay_amount), 2) as gmv,
       round(avg(pay_amount), 2) as aov
from dwd_order;

select '7) 无效营收订单占比' as check_item;
select status_name, is_valid_revenue, count(*) as cnt, round(sum(pay_amount), 2) as amt
from dwd_order group by status_name, is_valid_revenue order by cnt desc;