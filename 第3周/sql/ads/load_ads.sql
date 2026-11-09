-- ============================================================
-- 数据仓库 · ADS 应用层 ETL 装载脚本（第 3 周）
-- ------------------------------------------------------------
-- 前置：先执行 create_ads.sql
-- 上游：ydsh_dws（9 张汇总表）
-- 说明：ADS 层每条语句只写一张表，不做 union 拼装，
--       避免再次触发 Tez 120 计数器上限。
-- ============================================================

use ydsh_ads;

set hive.auto.convert.join = true;
set hive.mapjoin.smalltable.filesize = 25000000;

-- ------------------------------------------------------------
-- 1. ads_kpi_overview：KPI 总览（单行）
-- ------------------------------------------------------------
insert overwrite table ads_kpi_overview
select
  concat('全周期 ', r.d1, ' ~ ', r.d2)                                  as stat_scope,
  s.gmv,
  s.valid_gmv,
  s.order_cnt,
  s.valid_order_cnt,
  u.buyer_cnt,
  round(s.gmv / s.order_cnt, 2)                                         as aov,
  round(s.gmv / u.buyer_cnt, 2)                                         as arpu,
  round(u.repurchase_users / u.buyer_cnt, 4)                            as repurchase_rate,
  round(s.valid_gmv / s.gmv, 4)                                         as valid_revenue_rate,
  round(s.cancel_cnt / s.order_cnt, 4)                                  as cancel_rate,
  round(s.refund_cnt / s.order_cnt, 4)                                  as refund_rate,
  round(s.item_qty / s.order_cnt, 2)                                    as avg_order_items,
  cast(current_timestamp() as string)                                   as calc_time
from (
  select sum(gmv) as gmv, sum(valid_gmv) as valid_gmv,
         sum(order_cnt) as order_cnt, sum(valid_order_cnt) as valid_order_cnt,
         sum(item_qty) as item_qty, sum(cancel_cnt) as cancel_cnt,
         sum(refund_cnt) as refund_cnt
  from ydsh_dws.dws_sales_month
) s
cross join (
  select count(1) as buyer_cnt,
         sum(case when total_orders >= 2 then 1 else 0 end) as repurchase_users
  from (
    select user_id, sum(order_cnt) as total_orders
    from ydsh_dws.dws_user_month
    group by user_id
  ) x
) u
cross join (
  select min(order_date) as d1, max(order_date) as d2 from ydsh_dws.dws_sales_day
) r;

-- ------------------------------------------------------------
-- 2. ads_kpi_month：月度 KPI + 环比 / 同比
--    同比只有 1 年数据，lag(12) 恒为 NULL —— 这是数据边界，不是算错
-- ------------------------------------------------------------
insert overwrite table ads_kpi_month
select
  m.stat_month,
  m.gmv,
  m.valid_gmv,
  m.order_cnt,
  m.valid_order_cnt,
  u.buyer_cnt,
  round(m.gmv / m.order_cnt, 2)                                         as aov,
  round(m.gmv / u.buyer_cnt, 2)                                         as arpu,
  round(u.repurchase_users / u.buyer_cnt, 4)                            as repurchase_rate,
  cast(round((m.gmv - lag(m.gmv) over (order by m.stat_month))
             / lag(m.gmv) over (order by m.stat_month), 4) as decimal(12, 4))  as gmv_mom,
  cast(round((m.order_cnt - lag(m.order_cnt) over (order by m.stat_month))
             / lag(m.order_cnt) over (order by m.stat_month), 4) as decimal(12, 4)) as order_cnt_mom,
  cast(round((m.gmv - lag(m.gmv, 12) over (order by m.stat_month))
             / lag(m.gmv, 12) over (order by m.stat_month), 4) as decimal(12, 4)) as gmv_yoy,
  lag(m.gmv) over (order by m.stat_month)                               as prev_month_gmv
from (
  select stat_month, sum(gmv) as gmv, sum(valid_gmv) as valid_gmv,
         sum(order_cnt) as order_cnt, sum(valid_order_cnt) as valid_order_cnt
  from ydsh_dws.dws_sales_month
  group by stat_month
) m
join (
  select stat_month, count(1) as buyer_cnt,
         sum(case when order_cnt >= 2 then 1 else 0 end) as repurchase_users
  from ydsh_dws.dws_user_month
  group by stat_month
) u on m.stat_month = u.stat_month;

-- ------------------------------------------------------------
-- 3. ads_sales_daily：销售日报 + 7 日移动平均 + 日环比 + 月累计
-- ------------------------------------------------------------
insert overwrite table ads_sales_daily
select
  d.order_date,
  d.gmv,
  d.valid_gmv,
  d.order_cnt,
  u.buyer_cnt,
  d.item_qty,
  round(d.gmv / d.order_cnt, 2)                                         as aov,
  round(avg(d.gmv) over (order by d.order_date
                         rows between 6 preceding and current row), 2)  as gmv_ma7,
  cast(round((d.gmv - lag(d.gmv) over (order by d.order_date))
             / lag(d.gmv) over (order by d.order_date), 4) as decimal(12, 4)) as gmv_dod,
  round(sum(d.gmv) over (partition by substring(d.order_date, 1, 7)
                         order by d.order_date
                         rows between unbounded preceding and current row), 2) as month_cum_gmv,
  d.is_weekend
from (
  select order_date,
         sum(gmv) as gmv, sum(valid_gmv) as valid_gmv,
         sum(order_cnt) as order_cnt, sum(item_qty) as item_qty,
         max(is_weekend) as is_weekend
  from ydsh_dws.dws_sales_day
  group by order_date
) d
join (
  select order_date, count(1) as buyer_cnt
  from ydsh_dws.dws_user_day
  group by order_date
) u on d.order_date = u.order_date;

-- ------------------------------------------------------------
-- 4. ads_category_rank：品类月榜
-- ------------------------------------------------------------
insert overwrite table ads_category_rank
select
  stat_month, category, sales_amt, item_qty, order_cnt, buyer_cnt,
  avg_item_price, sales_share,
  rank() over (partition by stat_month order by sales_amt desc)         as rank_no
from ydsh_dws.dws_category_month;

-- ------------------------------------------------------------
-- 5. ads_province_sales：省份月榜
-- ------------------------------------------------------------
insert overwrite table ads_province_sales
select
  stat_month, province, region_area, gmv, order_cnt, buyer_cnt, aov, arpu, gmv_share,
  rank() over (partition by stat_month order by gmv desc)               as rank_no
from ydsh_dws.dws_province_month;

-- ------------------------------------------------------------
-- 6. ads_store_rank：门店月榜（含坪效）
-- ------------------------------------------------------------
insert overwrite table ads_store_rank
select
  stat_month, store_id, store_name, province, city, gmv, order_cnt, buyer_cnt,
  aov, sales_per_sqm,
  rank() over (partition by stat_month order by gmv desc)               as rank_no
from ydsh_dws.dws_store_month;

-- ------------------------------------------------------------
-- 7. ads_channel_month：渠道月占比
-- ------------------------------------------------------------
insert overwrite table ads_channel_month
select
  stat_month, channel_code, channel_name, is_online, gmv, order_cnt, buyer_cnt, aov,
  cast(round(gmv / sum(gmv) over (partition by stat_month), 6)
       as decimal(12, 6))                                               as gmv_share,
  cast(round(order_cnt / sum(order_cnt) over (partition by stat_month), 6)
       as decimal(12, 6))                                               as order_share
from ydsh_dws.dws_sales_month;

-- ------------------------------------------------------------
-- 8. ads_behavior_funnel：行为漏斗（月）
--    UV 跨日不可累加，故漏斗只用 PV；日均 PV 用 "总 PV / 当月天数"
-- ------------------------------------------------------------
insert overwrite table ads_behavior_funnel
select
  stat_month,
  sum(case when behavior_type = '浏览' then pv_cnt else 0 end)          as browse_pv,
  sum(case when behavior_type = '加购' then pv_cnt else 0 end)          as cart_pv,
  sum(case when behavior_type = '收藏' then pv_cnt else 0 end)          as fav_pv,
  sum(case when behavior_type = '购买' then pv_cnt else 0 end)          as buy_pv,
  round(sum(case when behavior_type = '浏览' then pv_cnt else 0 end)
        / count(distinct behavior_date), 2)                             as browse_pv_avg,
  round(sum(case when behavior_type = '购买' then pv_cnt else 0 end)
        / count(distinct behavior_date), 2)                             as buy_pv_avg,
  cast(round(sum(case when behavior_type = '加购' then pv_cnt else 0 end)
             / sum(case when behavior_type = '浏览' then pv_cnt else 0 end), 6)
       as decimal(12, 6))                                               as cart_rate,
  cast(round(sum(case when behavior_type = '收藏' then pv_cnt else 0 end)
             / sum(case when behavior_type = '浏览' then pv_cnt else 0 end), 6)
       as decimal(12, 6))                                               as fav_rate,
  cast(round(sum(case when behavior_type = '购买' then pv_cnt else 0 end)
             / sum(case when behavior_type = '浏览' then pv_cnt else 0 end), 6)
       as decimal(12, 6))                                               as buy_rate
from ydsh_dws.dws_behavior_day
group by stat_month;

-- ------------------------------------------------------------
-- 9. ads_user_rfm：用户价值分层
--    R 以数据最大日期为基准；R/F/M 各用 ntile(5) 分 5 档（正好 200 人/档）
-- ------------------------------------------------------------
insert overwrite table ads_user_rfm
select
  x.user_id,
  x.user_name,
  x.member_level,
  x.last_order_date,
  x.recency_days,
  x.frequency,
  x.monetary,
  x.r_score,
  x.f_score,
  x.m_score,
  concat(cast(x.r_score as string), cast(x.f_score as string),
         cast(x.m_score as string))                                     as rfm_score,
  case when x.r_score >= 4 and x.f_score >= 4 and x.m_score >= 4 then '重要价值客户'
       when x.r_score <  4 and x.f_score >= 4 and x.m_score >= 4 then '重要保持客户'
       when x.r_score >= 4 and x.f_score <  4 and x.m_score >= 4 then '重要发展客户'
       when x.r_score <  4 and x.f_score <  4 and x.m_score >= 4 then '重要挽留客户'
       when x.r_score >= 4 and x.f_score >= 4 and x.m_score <  4 then '一般价值客户'
       when x.r_score <  4 and x.f_score >= 4 and x.m_score <  4 then '一般保持客户'
       when x.r_score >= 4 and x.f_score <  4 and x.m_score <  4 then '一般发展客户'
       else '一般挽留客户' end                                           as rfm_segment
from (
  select
    u.user_id,
    u.user_name,
    u.member_level,
    u.last_order_date,
    datediff(r.ref_date, u.last_order_date)                             as recency_days,
    u.frequency,
    u.monetary,
    6 - ntile(5) over (order by datediff(r.ref_date, u.last_order_date) asc) as r_score,
    ntile(5) over (order by u.frequency asc)                            as f_score,
    ntile(5) over (order by u.monetary asc)                             as m_score
  from (
    select user_id,
           max(user_name) as user_name,
           max(member_level) as member_level,
           max(last_order_date) as last_order_date,
           sum(order_cnt) as frequency,
           sum(gmv) as monetary
    from ydsh_dws.dws_user_month
    group by user_id
  ) u
  cross join (
    select max(order_date) as ref_date from ydsh_dws.dws_sales_day
  ) r
) x;

-- ------------------------------------------------------------
-- 10. 装载结果核对（一条语句一张表，避免计数器超限）
-- ------------------------------------------------------------
select count(1) as ads_kpi_overview   from ads_kpi_overview;
select count(1) as ads_kpi_month      from ads_kpi_month;
select count(1) as ads_sales_daily    from ads_sales_daily;
select count(1) as ads_category_rank  from ads_category_rank;
select count(1) as ads_province_sales from ads_province_sales;
select count(1) as ads_store_rank     from ads_store_rank;
select count(1) as ads_channel_month  from ads_channel_month;
select count(1) as ads_behavior_funnel from ads_behavior_funnel;
select count(1) as ads_user_rfm       from ads_user_rfm;