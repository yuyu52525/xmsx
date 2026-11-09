-- ============================================================
-- 第 3 周 · KPI 指标结果表（交付物 2）
-- ------------------------------------------------------------
-- 说明：本脚本只做"取数 + 排版"，不含计算逻辑——
--       所有指标已在 DWS/ADS 层算好并落表，这里把结果按报表口径取出来，
--       便于写进《KPI 指标结果表》文档、也便于现场答辩直接投屏。
-- 全部只读。
-- 注意 1：每张报表单独一条语句（不用 union 拼装，避免 Tez 计数器上限）。
-- 注意 2：Hive 的中文别名必须用反引号包裹，否则报
--         "cannot recognize input near 'as'"（第 3 周踩到的坑）。
-- ============================================================

-- ------------------------------------------------------------
-- 报表 1　核心 KPI 总览
-- ------------------------------------------------------------
select stat_scope                                            as `统计范围`,
       cast(round(gmv, 2) as decimal(18, 2))                 as `GMV_元`,
       cast(round(valid_gmv, 2) as decimal(18, 2))           as `有效GMV_元`,
       order_cnt                                             as `订单量`,
       valid_order_cnt                                       as `有效订单量`,
       buyer_cnt                                             as `下单用户数`,
       cast(round(aov, 2) as decimal(18, 2))                 as `客单价_元`,
       cast(round(arpu, 2) as decimal(18, 2))                as `ARPU_元`,
       repurchase_rate                                       as `复购率`,
       valid_revenue_rate                                    as `有效营收占比`,
       cancel_rate                                           as `取消率`,
       refund_rate                                           as `退款中占比`
from ydsh_ads.ads_kpi_overview;

-- ------------------------------------------------------------
-- 报表 2　月度 KPI 与环比
-- ------------------------------------------------------------
select stat_month                                            as `月份`,
       cast(round(gmv, 2) as decimal(18, 2))                 as `GMV_元`,
       order_cnt                                             as `订单量`,
       buyer_cnt                                             as `下单用户`,
       cast(round(aov, 2) as decimal(18, 2))                 as `客单价_元`,
       cast(round(arpu, 2) as decimal(18, 2))                as `ARPU_元`,
       repurchase_rate                                       as `当月复购率`,
       gmv_mom                                               as `GMV环比`
from ydsh_ads.ads_kpi_month
order by stat_month;

-- ------------------------------------------------------------
-- 报表 3　品类销售榜（全年）
-- ------------------------------------------------------------
select category                                              as `品类`,
       cast(round(sum(sales_amt), 2) as decimal(18, 2))      as `销售额_元`,
       sum(item_qty)                                         as `销量_件`,
       sum(order_cnt)                                        as `订单数`,
       cast(round(sum(sales_amt) / sum(item_qty), 2) as decimal(18, 2)) as `件均价_元`
from ydsh_ads.ads_category_rank
group by category
order by `销售额_元` desc;

-- 品类销售占比（全年）
select category                                              as `品类`,
       cast(round(sum(sales_amt) / sum(sum(sales_amt)) over (), 6)
            as decimal(10, 6))                               as `销售占比`
from ydsh_ads.ads_category_rank
group by category
order by `销售占比` desc;

-- ------------------------------------------------------------
-- 报表 4　省份销售榜（全年，前 5）
-- ------------------------------------------------------------
select province                                              as `省份`,
       region_area                                           as `大区`,
       cast(round(sum(gmv), 2) as decimal(18, 2))            as `GMV_元`,
       sum(order_cnt)                                        as `订单量`,
       cast(round(sum(gmv) / sum(buyer_cnt), 2) as decimal(18, 2)) as `人均消费_元`
from ydsh_ads.ads_province_sales
group by province, region_area
order by `GMV_元` desc
limit 5;

-- ------------------------------------------------------------
-- 报表 5　门店销售榜（全年，前 5，含坪效）
-- ------------------------------------------------------------
select store_name                                            as `门店`,
       province                                              as `省份`,
       cast(round(sum(gmv), 2) as decimal(18, 2))            as `GMV_元`,
       sum(order_cnt)                                        as `订单量`,
       cast(round(avg(sales_per_sqm), 2) as decimal(18, 2))  as `月均坪效_元每平米`
from ydsh_ads.ads_store_rank
group by store_name, province
order by `GMV_元` desc
limit 5;

-- ------------------------------------------------------------
-- 报表 6　渠道结构（全年）
-- ------------------------------------------------------------
select channel_name                                          as `渠道`,
       is_online                                             as `是否线上`,
       cast(round(sum(gmv), 2) as decimal(18, 2))            as `GMV_元`,
       sum(order_cnt)                                        as `订单量`,
       cast(round(sum(gmv) / sum(sum(gmv)) over (), 6)
            as decimal(10, 6))                               as `GMV占比`
from ydsh_ads.ads_channel_month
group by channel_name, is_online
order by `GMV_元` desc;

-- ------------------------------------------------------------
-- 报表 7　行为漏斗（全年汇总）
-- ------------------------------------------------------------
select sum(browse_pv)                                        as `浏览次数`,
       sum(cart_pv)                                          as `加购次数`,
       sum(fav_pv)                                           as `收藏次数`,
       sum(buy_pv)                                           as `购买次数`,
       cast(round(sum(cart_pv) / sum(browse_pv), 4) as decimal(10, 4)) as `加购率`,
       cast(round(sum(fav_pv) / sum(browse_pv), 4) as decimal(10, 4))  as `收藏率`,
       cast(round(sum(buy_pv) / sum(browse_pv), 4) as decimal(10, 4))  as `购买率`
from ydsh_ads.ads_behavior_funnel;

-- ------------------------------------------------------------
-- 报表 8　用户价值分层（RFM）
-- ------------------------------------------------------------
select rfm_segment                                           as `客户分层`,
       count(1)                                              as `人数`,
       cast(round(count(1) / sum(count(1)) over (), 4) as decimal(10, 4)) as `人数占比`,
       cast(round(avg(monetary), 2) as decimal(18, 2))       as `人均消费_元`,
       cast(round(avg(frequency), 1) as decimal(10, 1))      as `人均订单数`,
       cast(round(avg(recency_days), 1) as decimal(10, 1))   as `平均未购天数`
from ydsh_ads.ads_user_rfm
group by rfm_segment
order by `人数` desc;

-- ------------------------------------------------------------
-- 报表 9　会员等级消费贡献
-- ------------------------------------------------------------
select member_level                                          as `会员等级`,
       count(distinct user_id)                               as `用户数`,
       cast(round(sum(gmv), 2) as decimal(18, 2))            as `消费额_元`,
       cast(round(avg(avg_order_amt), 2) as decimal(18, 2))  as `人均客单价_元`
from ydsh_dws.dws_user_month
group by member_level
order by `消费额_元` desc;

-- ------------------------------------------------------------
-- 报表 10　周度 GMV 最好 / 最差各 3 周
-- ------------------------------------------------------------
select week_key                                              as `周`,
       week_start                                            as `周一`,
       cast(round(sum(gmv), 2) as decimal(18, 2))            as `GMV_元`,
       sum(order_cnt)                                        as `订单量`
from ydsh_dws.dws_sales_week
group by week_key, week_start
order by `GMV_元` desc
limit 3;

select week_key                                              as `周`,
       week_start                                            as `周一`,
       cast(round(sum(gmv), 2) as decimal(18, 2))            as `GMV_元`,
       sum(order_cnt)                                        as `订单量`
from ydsh_dws.dws_sales_week
group by week_key, week_start
order by `GMV_元` asc
limit 3;