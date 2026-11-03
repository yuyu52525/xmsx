-- ============================================================
-- 探索性数据分析（EDA）· 基于 DWD 星型模型
-- ------------------------------------------------------------
-- 依赖：ydsh_dwd.dwd_order / dwd_order_item / dwd_user_behavior
--       dim_user / dim_product / dim_store / dim_date
-- 口径说明：
--   GMV（全量）  = sum(pay_amount)，含待支付/已取消/退款中
--   GMV（有效）  = sum(pay_amount) where is_valid_revenue = 1（已完成 + 已支付）
--   客单价 AOV   = GMV / 订单数
--   品类销售     = sum(alloc_amount)，按明细占比把订单实付分摊到品类，可加总回 GMV
-- ============================================================
use ydsh_dwd;

-- 1) 基础 KPI
select '1) 基础 KPI' as section;
select
  (select count(*) from dim_user)                                       as total_users,
  count(distinct user_id)                                               as buy_users,
  count(*)                                                              as total_orders,
  round(sum(pay_amount), 2)                                             as gmv_all,
  round(sum(if(is_valid_revenue = 1, pay_amount, 0)), 2)                as gmv_valid,
  round(avg(pay_amount), 2)                                             as aov,
  round(sum(discount_amount), 2)                                        as total_discount
from dwd_order;

-- 2) 月度 GMV 趋势与环比（窗口函数 lag）
select '2) 月度趋势' as section;
select
  order_month,
  count(*)                                                     as orders,
  round(sum(pay_amount), 2)                                    as gmv,
  round(lag(sum(pay_amount)) over (order by order_month), 2)   as prev_gmv,
  round(100 * (sum(pay_amount) - lag(sum(pay_amount)) over (order by order_month))
        / lag(sum(pay_amount)) over (order by order_month), 2) as mom_pct
from dwd_order
group by order_month
order by order_month;

-- 3) 季度汇总
select '3) 季度汇总' as section;
select
  concat(year(order_date), '-Q', quarter(order_date)) as quarter_key,
  count(*) as orders,
  round(sum(pay_amount), 2) as gmv,
  round(avg(pay_amount), 2) as aov
from dwd_order
group by year(order_date), quarter(order_date)
order by quarter_key;

-- 4) 品类销售分布（含占比）
select '4) 品类销售分布' as section;
select
  p.category,
  count(*)                                                  as item_rows,
  sum(i.quantity)                                           as qty,
  round(sum(i.alloc_amount), 2)                             as sales,
  round(100 * sum(i.alloc_amount) / sum(sum(i.alloc_amount)) over (), 2) as pct
from dwd_order_item i
join dim_product p on i.product_id = p.product_id
group by p.category
order by sales desc;

-- 5) 二级类目 Top 8
select '5) 二级类目 Top8' as section;
select
  p.sub_category,
  round(sum(i.alloc_amount), 2) as sales,
  sum(i.quantity)               as qty
from dwd_order_item i
join dim_product p on i.product_id = p.product_id
group by p.sub_category
order by sales desc
limit 8;

-- 6) 商品销售额 Top 10
select '6) 商品 Top10' as section;
select
  i.product_id, p.product_name, p.category,
  sum(i.quantity)               as qty,
  round(sum(i.alloc_amount), 2) as sales
from dwd_order_item i
join dim_product p on i.product_id = p.product_id
group by i.product_id, p.product_name, p.category
order by sales desc
limit 10;

-- 7) 省份销售分布
select '7) 省份销售分布' as section;
select
  u.province,
  count(*)                                  as orders,
  round(sum(o.pay_amount), 2)               as gmv,
  round(avg(o.pay_amount), 2)               as aov,
  round(100 * sum(o.pay_amount) / sum(sum(o.pay_amount)) over (), 2) as pct
from dwd_order o
join dim_user u on o.user_id = u.user_id
group by u.province
order by gmv desc;

-- 8) 七大区销售分布
select '8) 大区分布' as section;
select
  u.region_area,
  count(distinct o.user_id)   as users,
  count(*)                    as orders,
  round(sum(o.pay_amount), 2) as gmv,
  round(avg(o.pay_amount), 2) as aov
from dwd_order o
join dim_user u on o.user_id = u.user_id
group by u.region_area
order by gmv desc;

-- 9) 门店 Top 10
select '9) 门店 Top10' as section;
select
  s.store_id, s.store_name, s.city,
  count(*)                    as orders,
  round(sum(o.pay_amount), 2) as gmv
from dwd_order o
join dim_store s on o.store_id = s.store_id
group by s.store_id, s.store_name, s.city
order by gmv desc
limit 10;

-- 10) 渠道分布（线上 / 线下）
select '10) 渠道分布' as section;
select
  o.channel_name,
  o.is_online,
  count(*)                    as orders,
  round(sum(o.pay_amount), 2) as gmv,
  round(avg(o.pay_amount), 2) as aov,
  round(100 * sum(o.pay_amount) / sum(sum(o.pay_amount)) over (), 2) as pct
from dwd_order o
group by o.channel_name, o.is_online
order by gmv desc;

-- 11) 支付方式分布
select '11) 支付方式分布' as section;
select
  o.pay_name,
  count(*)                    as orders,
  round(sum(o.pay_amount), 2) as gmv,
  round(100 * count(*) / sum(count(*)) over (), 2) as order_pct
from dwd_order o
group by o.pay_name
order by orders desc;

-- 12) 会员等级消费能力
select '12) 会员等级' as section;
select
  u.member_level,
  count(distinct o.user_id)   as users,
  count(*)                    as orders,
  round(sum(o.pay_amount), 2) as gmv,
  round(sum(o.pay_amount) / count(distinct o.user_id), 2) as arpu,
  round(avg(o.pay_amount), 2) as aov
from dwd_order o
join dim_user u on o.user_id = u.user_id
group by u.member_level
order by gmv desc;

-- 13) 下单时段分布
select '13) 时段分布' as section;
select
  case when order_hour < 6 then '00-06 凌晨'
       when order_hour < 9 then '06-09 早间'
       when order_hour < 12 then '09-12 上午'
       when order_hour < 14 then '12-14 午间'
       when order_hour < 18 then '14-18 下午'
       when order_hour < 22 then '18-22 晚间'
       else '22-24 深夜' end as hour_bucket,
  count(*) as orders,
  round(sum(pay_amount), 2) as gmv
from dwd_order
group by case when order_hour < 6 then '00-06 凌晨'
              when order_hour < 9 then '06-09 早间'
              when order_hour < 12 then '09-12 上午'
              when order_hour < 14 then '12-14 午间'
              when order_hour < 18 then '14-18 下午'
              when order_hour < 22 then '18-22 晚间'
              else '22-24 深夜' end
order by orders desc;

-- 14) 工作日 vs 周末（时间维度关联）
select '14) 周末效应' as section;
select
  d.is_weekend,
  count(*)                    as orders,
  round(sum(o.pay_amount), 2) as gmv,
  round(avg(o.pay_amount), 2) as aov
from dwd_order o
join dim_date d on o.order_date = d.date_key
group by d.is_weekend
order by d.is_weekend;

-- 15) 用户累计消费（窗口函数：逐单累加）
select '15) 用户累计消费 Top10（窗口函数）' as section;
select * from (
  select
    t.user_id,
    t.order_id,
    t.order_date,
    round(t.pay_amount, 2)                                              as pay_amount,
    round(sum(t.pay_amount) over (partition by t.user_id order by t.order_timestamp
                                  rows between unbounded preceding and current row), 2) as cum_amount,
    row_number() over (partition by t.user_id order by t.order_timestamp) as order_seq
  from dwd_order t
  where t.is_valid_revenue = 1
) s
order by cum_amount desc
limit 10;

-- 16) 用户消费分层与复购
select '16) 用户消费分层' as section;
select
  tier,
  count(*)                    as users,
  round(sum(total), 2)        as gmv,
  round(avg(orders), 2)       as avg_orders,
  round(avg(total), 2)        as avg_amount
from (
  select
    user_id,
    count(*)         as orders,
    sum(pay_amount)  as total,
    case when sum(pay_amount) >= 50000 then 'A 高价值(>=5万)'
         when sum(pay_amount) >= 20000 then 'B 中高(2-5万)'
         when sum(pay_amount) >= 5000  then 'C 普通(0.5-2万)'
         else 'D 低价值(<5千)' end as tier
  from dwd_order
  where is_valid_revenue = 1
  group by user_id
) t
group by tier
order by tier;

-- 17) 用户下单次数分布（复购率）
select '17) 下单次数分布' as section;
select
  orders AS orders_per_user,
  count(*) as users
from (
  select user_id, count(*) as orders
  from dwd_order
  group by user_id
) t
group by orders
order by orders;

-- 18) 行为漏斗
select '18) 行为漏斗' as section;
select
  behavior_type,
  count(*)                 as cnt,
  count(distinct user_id)  as users,
  count(distinct product_id) as products
from dwd_user_behavior
group by behavior_type
order by cnt desc;

-- 19) 月度行为量（趋势）
select '19) 月度行为量' as section;
select
  behavior_month,
  sum(if(behavior_type = '浏览', 1, 0)) as pv,
  sum(if(behavior_type = '加购', 1, 0)) as cart,
  sum(if(behavior_type = '收藏', 1, 0)) as fav,
  sum(if(behavior_type = '购买', 1, 0)) as buy
from dwd_user_behavior
group by behavior_month
order by behavior_month;