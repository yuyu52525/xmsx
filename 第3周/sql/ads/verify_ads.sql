-- ============================================================
-- 数据仓库 · ADS 应用层校验脚本（第 3 周）
-- ------------------------------------------------------------
-- 校验思路：ADS 是"给业务看的结果"，错一位数就会被当成真结论，
--           因此每个指标都要能和 DWD 明细对得上。
--           全部只读（SELECT）。
-- 每个指标单独一条语句，不用 union 拼装（避免 Tez 120 计数器上限）。
-- ============================================================

use ydsh_ads;

-- ------------------------------------------------------------
-- 1. 总览 KPI —— 与《第 2 周》交接口径逐项对齐
--    GMV 36,116,687.06 / 有效 GMV 24,185,272.59 / 订单 14,398
--    AOV 2,508.45 / 用户 1,000 / ARPU 36,116.69
-- ------------------------------------------------------------
select cast(round(gmv, 2) as decimal(18, 2))                as ads_gmv,
       cast(round(valid_gmv, 2) as decimal(18, 2))          as ads_valid_gmv,
       order_cnt, buyer_cnt,
       cast(round(aov, 2) as decimal(18, 2))                as ads_aov,
       cast(round(arpu, 2) as decimal(18, 2))               as ads_arpu,
       valid_revenue_rate
from ads_kpi_overview;

-- 与 DWD 明细回滚比对（应完全相等）
select cast(round(sum(pay_amount), 2) as decimal(18, 2))    as dwd_gmv,
       count(1)                                             as dwd_order_cnt,
       count(distinct user_id)                              as dwd_buyer_cnt
from ydsh_dwd.dwd_order;

-- ------------------------------------------------------------
-- 2. 月度表加总 = 总览（12 个月不能多算也不能少算）
-- ------------------------------------------------------------
select cast(round(sum(gmv), 2) as decimal(18, 2))           as month_gmv_sum,
       sum(order_cnt)                                       as month_order_sum
from ads_kpi_month;

-- 月度环比首月应为 NULL（没有上月可比）
select stat_month, gmv_mom from ads_kpi_month order by stat_month limit 2;

-- 同比列应全为 NULL：本数据集只有 2024 一年，做不出同比
select count(1) as non_null_yoy from ads_kpi_month where gmv_yoy is not null;

-- ------------------------------------------------------------
-- 3. 日报加总 = 总览；移动平均首日应为 NULL 前 6 天无 7 日窗口
-- ------------------------------------------------------------
select cast(round(sum(gmv), 2) as decimal(18, 2))           as daily_gmv_sum,
       count(1)                                             as days
from ads_sales_daily;

select count(1) as ma7_null_rows from ads_sales_daily where gmv_ma7 is null;
select count(1) as dod_null_rows from ads_sales_daily where gmv_dod is null;

-- ------------------------------------------------------------
-- 4. 各维度占比之和必须为 1（误差仅在 1e-6 级舍入）
-- ------------------------------------------------------------
select stat_month, cast(round(sum(gmv_share), 6) as decimal(12, 6)) as channel_share_sum
from ads_channel_month group by stat_month order by stat_month;

select stat_month, cast(round(sum(sales_share), 6) as decimal(12, 6)) as category_share_sum
from ads_category_rank group by stat_month order by stat_month limit 3;

select stat_month, cast(round(sum(gmv_share), 6) as decimal(12, 6)) as province_share_sum
from ads_province_sales group by stat_month order by stat_month limit 3;

-- ------------------------------------------------------------
-- 5. 排名连续性：每月每个维度的 rank_no 应恰好覆盖 1..N
--    （count(distinct)=max 且无重复，即说明排名连续）
-- ------------------------------------------------------------
select stat_month, count(1) as n, count(distinct rank_no) as n_rank, max(rank_no) as max_rank
from ads_category_rank group by stat_month order by stat_month limit 3;

select stat_month, count(1) as n, count(distinct rank_no) as n_rank, max(rank_no) as max_rank
from ads_province_sales group by stat_month order by stat_month limit 3;

-- ------------------------------------------------------------
-- 6. RFM 分层：人数合计 = 1,000；分值与分层不能为空
-- ------------------------------------------------------------
select count(1) as total_users,
       count(distinct user_id) as distinct_users,
       sum(case when rfm_segment is null then 1 else 0 end) as null_segment
from ads_user_rfm;

select rfm_segment, count(1) as users,
       cast(round(avg(monetary), 2) as decimal(18, 2))      as avg_monetary,
       cast(round(avg(recency_days), 1) as decimal(10, 1))  as avg_recency
from ads_user_rfm group by rfm_segment order by users desc;

-- 分值范围必须落在 1..5
select min(r_score) as r_min, max(r_score) as r_max,
       min(f_score) as f_min, max(f_score) as f_max,
       min(m_score) as m_min, max(m_score) as m_max
from ads_user_rfm;

-- ------------------------------------------------------------
-- 7. 复购率为什么是 100%？—— 每用户订单数分布（关键口径说明）
-- ------------------------------------------------------------
select min(total_orders) as min_orders,
       max(total_orders) as max_orders,
       cast(round(avg(total_orders), 1) as decimal(10, 1)) as avg_orders,
       count(1) as users
from (
  select user_id, sum(order_cnt) as total_orders
  from ydsh_dws.dws_user_month group by user_id
) t;

-- ------------------------------------------------------------
-- 8. 行为漏斗：购买率高于加购率，说明该行为日志不是真实漏斗
--    （浏览 / 加购 / 收藏 / 购买 是并列的行为事件，不是同一会话的步骤）
-- ------------------------------------------------------------
select stat_month, browse_pv, cart_pv, fav_pv, buy_pv, cart_rate, fav_rate, buy_rate
from ads_behavior_funnel order by stat_month;

-- 同一会话内是否真的存在"浏览→加购→购买"先后关系？抽查 3 个会话
select session_id,
       count(1) as events,
       count(distinct behavior_type) as types,
       concat_ws(',', collect_set(behavior_type)) as type_list
from ydsh_dwd.dwd_user_behavior
group by session_id
having count(distinct behavior_type) > 1
limit 3;

-- ------------------------------------------------------------
-- 9. 空值体检：关键指标列不允许出现 NULL
-- ------------------------------------------------------------
select sum(case when gmv is null then 1 else 0 end) as null_gmv,
       sum(case when order_cnt is null then 1 else 0 end) as null_orders,
       sum(case when buyer_cnt is null then 1 else 0 end) as null_buyers
from ads_sales_daily;