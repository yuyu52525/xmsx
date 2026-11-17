-- ============================================================
-- 数据仓库 · 第 4 周 ADS 增量装载脚本
-- ------------------------------------------------------------
-- 前置：先执行 create_ads_w4.sql
-- 说明：一条语句只写一张表（第 3 周经验：Tez 计数器上限 120，
--       多表 union 拼装会报 Too many counters）
-- ============================================================

use ydsh_ads;

set hive.auto.convert.join = true;
set hive.mapjoin.smalltable.filesize = 25000000;
set hive.exec.parallel = false;

-- ------------------------------------------------------------
-- 1. ads_pay_type_month：月 × 支付方式（订单口径 pay_amount）
--    口径自检：sum(gmv) 必须等于 36,116,687.06（= ads_kpi_overview.gmv）
-- ------------------------------------------------------------
insert overwrite table ads_pay_type_month
select
  t.stat_month,
  t.pay_code,
  t.pay_name,
  t.order_cnt,
  t.buyer_cnt,
  t.gmv,
  t.valid_gmv,
  round(t.gmv / t.order_cnt, 2)                                        as aov,
  cast(round(t.gmv / sum(t.gmv) over (partition by t.stat_month), 6)
       as decimal(12, 6))                                              as gmv_share,
  cast(round(t.order_cnt / sum(t.order_cnt) over (partition by t.stat_month), 6)
       as decimal(12, 6))                                              as order_share,
  rank() over (partition by t.stat_month order by t.gmv desc)          as rank_no
from (
  select
    substr(order_date, 1, 7)                                           as stat_month,
    pay_code,
    pay_name,
    count(1)                                                           as order_cnt,
    count(distinct user_id)                                            as buyer_cnt,
    round(sum(pay_amount), 2)                                          as gmv,
    round(sum(case when is_valid_revenue = 1 then pay_amount else 0 end), 2) as valid_gmv
  from ydsh_dwd.dwd_order
  group by substr(order_date, 1, 7), pay_code, pay_name
) t;

-- ------------------------------------------------------------
-- 2. ads_hour_category：小时 × 品类（明细分摊口径 alloc_amount）
--    口径自检：sum(sales_amt) 必须等于 35,833,305.06（= ads_category_rank 合计）
--    关联链：dwd_order_item（明细）→ dwd_order（取 order_hour）
--            → dim_product（取 category）
-- ------------------------------------------------------------
insert overwrite table ads_hour_category
select
  h.hour_of_day,
  h.category,
  h.order_cnt,
  h.item_qty,
  h.buyer_cnt,
  h.sales_amt,
  h.avg_item_price,
  cast(round(h.sales_amt / h.cat_total, 6) as decimal(12, 6))          as hour_share_of_category,
  cast(round(h.sales_amt / sum(h.sales_amt) over (partition by h.hour_of_day), 6)
       as decimal(12, 6))                                              as category_share_of_hour,
  -- 注意：这里必须用 dense_rank 而不是 rank。
  -- 本表一行是"小时×品类"，同一个品类有 24 行、cat_total 相同，
  -- 用 rank() 会排出 1/25/49/… 这种跳号（实测踩过），dense_rank 才是 1~8 的品类名次。
  dense_rank() over (order by h.cat_total desc)                        as category_order
from (
  select
    a.hour_of_day,
    a.category,
    a.order_cnt,
    a.item_qty,
    a.buyer_cnt,
    a.sales_amt,
    a.avg_item_price,
    sum(a.sales_amt) over (partition by a.category)                    as cat_total
  from (
    select
      o.order_hour                                                     as hour_of_day,
      p.category                                                       as category,
      count(distinct o.order_id)                                       as order_cnt,
      sum(i.quantity)                                                  as item_qty,
      count(distinct o.user_id)                                        as buyer_cnt,
      round(sum(i.alloc_amount), 2)                                    as sales_amt,
      round(sum(i.alloc_amount) / sum(i.quantity), 2)                  as avg_item_price
    from ydsh_dwd.dwd_order_item i
    join ydsh_dwd.dwd_order      o on i.order_id   = o.order_id
    join ydsh_dwd.dim_product    p on i.product_id = p.product_id
    group by o.order_hour, p.category
  ) a
) h;

-- ------------------------------------------------------------
-- 3. 装载结果核对（一条语句一张表）
-- ------------------------------------------------------------
select count(1) as ads_pay_type_month from ads_pay_type_month;
select count(1) as ads_hour_category   from ads_hour_category;