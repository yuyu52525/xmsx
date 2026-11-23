-- ============================================================================
-- 云购生活数仓 · 第 5 周 逐层一致性核对 SQL
-- ----------------------------------------------------------------------------
-- 用途：与 `第5周/py/e2e_verify.py` 同口径的手工核对脚本，供答辩现场用 beeline 演示。
--       两者的期望值完全一致；脚本版会额外比对副本与接口，SQL 版只覆盖数仓内部。
--
-- 执行：
--   docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第5周/sql/integrity_check.sql
--
-- 约定（第 1～4 周踩出来的）：
--   1. 中文别名必须加反引号
--   2. 金额一律 round(sum(...), 2)，否则出现 28757.559999999998
--   3. 单条 SQL 的 union all 分支不超过 8 路（Tez 计数器上限 120）
--   4. 分区裁剪必须用分区列本身（order_month），不能用 substr(order_date)
-- ============================================================================

use default;

-- ---------------------------------------------------------------------------
-- 1. 服务层：Hive 版本
-- ---------------------------------------------------------------------------
select version() as `Hive版本`;

-- ---------------------------------------------------------------------------
-- 2. ODS 贴源层：6 张表，期望合计 114,809
-- ---------------------------------------------------------------------------
select 'ods_user'          as `表`, count(*) as `行数` from ydsh_ods.ods_user
union all select 'ods_product',       count(*) from ydsh_ods.ods_product
union all select 'ods_store',         count(*) from ydsh_ods.ods_store
union all select 'ods_order',         count(*) from ydsh_ods.ods_order
union all select 'ods_order_item',    count(*) from ydsh_ods.ods_order_item
union all select 'ods_user_behavior', count(*) from ydsh_ods.ods_user_behavior;

-- 期望：1000 / 600 / 60 / 15600 / 37549 / 60000 → 合计 114,809

-- ---------------------------------------------------------------------------
-- 3. DWD 明细层：6 条主链路 + 生成维表，主链路期望合计 111,037
-- ---------------------------------------------------------------------------
select 'dim_user'          as `表`, count(*) as `行数` from ydsh_dwd.dim_user
union all select 'dim_product',        count(*) from ydsh_dwd.dim_product
union all select 'dim_store',          count(*) from ydsh_dwd.dim_store
union all select 'dwd_order',          count(*) from ydsh_dwd.dwd_order
union all select 'dwd_order_item',     count(*) from ydsh_dwd.dwd_order_item
union all select 'dwd_user_behavior',  count(*) from ydsh_dwd.dwd_user_behavior
union all select 'dim_date(生成维表)',  count(*) from ydsh_dwd.dim_date;

-- 期望：1000 / 600 / 60 / 14398 / 34979 / 60000 / 731
--       6 条主链路合计 111,037（清洗剔除 3,772 行 = 3.29%）

-- ---------------------------------------------------------------------------
-- 4. DWS 汇总层：9 张表
-- ---------------------------------------------------------------------------
select 'dws_sales_day'      as `表`, count(*) as `行数` from ydsh_dws.dws_sales_day
union all select 'dws_sales_week',     count(*) from ydsh_dws.dws_sales_week
union all select 'dws_sales_month',    count(*) from ydsh_dws.dws_sales_month
union all select 'dws_category_month', count(*) from ydsh_dws.dws_category_month
union all select 'dws_store_month',    count(*) from ydsh_dws.dws_store_month
union all select 'dws_province_month', count(*) from ydsh_dws.dws_province_month
union all select 'dws_user_day',       count(*) from ydsh_dws.dws_user_day
union all select 'dws_user_month',     count(*) from ydsh_dws.dws_user_month;

select count(*) as `dws_behavior_day行数` from ydsh_dws.dws_behavior_day;

-- 期望：1464 / 212 / 48 / 96 / 720 / 180 / 14100 / 8448，behavior_day 368
-- 注意：dws_sales_week 是 53 周 × 4 渠道 = 212，不是 208；
--       2024-W53 只有 12-30、12-31 两天，不能当"最差周"解读。

-- ---------------------------------------------------------------------------
-- 5. DWS 汇总值回算：日 / 周 / 月 三个粒度的 GMV 加总都必须等于 36,116,687.06
-- ---------------------------------------------------------------------------
select 'day' as `粒度`, cast(round(sum(gmv), 2) as decimal(18, 2)) as `GMV合计` from ydsh_dws.dws_sales_day
union all select 'week',  cast(round(sum(gmv), 2) as decimal(18, 2)) from ydsh_dws.dws_sales_week
union all select 'month', cast(round(sum(gmv), 2) as decimal(18, 2)) from ydsh_dws.dws_sales_month;

-- ---------------------------------------------------------------------------
-- 6. ADS 应用层：11 张表
-- ---------------------------------------------------------------------------
select 'ads_kpi_overview'   as `表`, count(*) as `行数` from ydsh_ads.ads_kpi_overview
union all select 'ads_kpi_month',      count(*) from ydsh_ads.ads_kpi_month
union all select 'ads_sales_daily',    count(*) from ydsh_ads.ads_sales_daily
union all select 'ads_category_rank',  count(*) from ydsh_ads.ads_category_rank
union all select 'ads_province_sales', count(*) from ydsh_ads.ads_province_sales
union all select 'ads_store_rank',     count(*) from ydsh_ads.ads_store_rank
union all select 'ads_channel_month',  count(*) from ydsh_ads.ads_channel_month
union all select 'ads_behavior_funnel', count(*) from ydsh_ads.ads_behavior_funnel;

select 'ads_user_rfm'       as `表`, count(*) as `行数` from ydsh_ads.ads_user_rfm
union all select 'ads_pay_type_month', count(*) from ydsh_ads.ads_pay_type_month
union all select 'ads_hour_category',  count(*) from ydsh_ads.ads_hour_category;

-- 期望：1 / 12 / 366 / 96 / 180 / 720 / 48 / 3 / 1000 / 48 / 192（合计 2,666）

-- ---------------------------------------------------------------------------
-- 7. 核心指标：订单口径 GMV / 有效 GMV / 订单量 / 买家数 / 客单价 / ARPU
-- ---------------------------------------------------------------------------
select cast(gmv as decimal(18,2))       as `GMV`
     , cast(valid_gmv as decimal(18,2)) as `有效GMV`
     , order_cnt         as `订单量`
     , buyer_cnt         as `下单用户`
     , cast(aov as decimal(18,2))       as `客单价`
     , cast(arpu as decimal(18,2))      as `ARPU`
     , round(valid_revenue_rate * 100, 2) as `有效营收占比`
  from ydsh_ads.ads_kpi_overview;

-- 期望：36116687.06 / 24185272.59 / 14398 / 1000 / 2508.45 / 36116.69 / 66.96

-- ---------------------------------------------------------------------------
-- 8. 三种金额口径：必须分别等于 36,116,687.06 / 35,833,305.06 / 402,816,786.63
-- ---------------------------------------------------------------------------
select '订单口径 pay_amount'   as `口径`, cast(round(sum(pay_amount), 2) as decimal(18, 2))  as `合计`
  from ydsh_dwd.dwd_order
union all
select '分摊口径 alloc_amount', cast(round(sum(alloc_amount), 2) as decimal(18, 2)) from ydsh_dwd.dwd_order_item
union all
select '原价口径 item_amount',  cast(round(sum(item_amount), 2) as decimal(18, 2))  from ydsh_dwd.dwd_order_item;

-- 三者不可相加：订单口径 − 分摊口径 = 283,382.65 元 = 114 张无明细订单的实付

-- 无明细订单张数与金额（解释上面那 283,382.65 元的来源）
select count(*) as `无明细订单数`, cast(round(sum(o.pay_amount), 2) as decimal(18, 2)) as `实付合计`
  from ydsh_dwd.dwd_order o
  left join (select distinct order_id from ydsh_dwd.dwd_order_item) i
         on o.order_id = i.order_id
 where i.order_id is null;

-- ---------------------------------------------------------------------------
-- 9. ADS 各维度加总交叉校验（同一指标在不同表里必须对得上）
-- ---------------------------------------------------------------------------
select 'ads_kpi_month.gmv'      as `表.字段`, cast(round(sum(gmv), 2) as decimal(18, 2)) as `合计` from ydsh_ads.ads_kpi_month
union all select 'ads_sales_daily.gmv',      cast(round(sum(gmv), 2) as decimal(18, 2)) from ydsh_ads.ads_sales_daily
union all select 'ads_province_sales.gmv',   cast(round(sum(gmv), 2) as decimal(18, 2)) from ydsh_ads.ads_province_sales
union all select 'ads_store_rank.gmv',       cast(round(sum(gmv), 2) as decimal(18, 2)) from ydsh_ads.ads_store_rank
union all select 'ads_channel_month.gmv',    cast(round(sum(gmv), 2) as decimal(18, 2)) from ydsh_ads.ads_channel_month;

select 'ads_pay_type_month.gmv'  as `表.字段`, cast(round(sum(gmv), 2) as decimal(18, 2)) as `合计` from ydsh_ads.ads_pay_type_month
union all select 'ads_category_rank.sales_amt', cast(round(sum(sales_amt), 2) as decimal(18, 2)) from ydsh_ads.ads_category_rank
union all select 'ads_hour_category.sales_amt', cast(round(sum(sales_amt), 2) as decimal(18, 2)) from ydsh_ads.ads_hour_category;

-- 期望：前 6 行全部 36,116,687.06；后 2 行全部 35,833,305.06

-- ---------------------------------------------------------------------------
-- 10. 门店排名：必须按 store_id 聚合（60 个编号只有 52 个名称）
-- ---------------------------------------------------------------------------
select store_id as `门店编号`, store_name as `门店名称`, province as `省份`
     , cast(round(sum(gmv), 2) as decimal(18, 2)) as `GMV`
     , sum(order_cnt)     as `订单量`
  from ydsh_ads.ads_store_rank
 group by store_id, store_name, province
 order by `GMV` desc
 limit 5;

-- 期望第一名：S029 云购生活·北京二店 708,051.42
-- 若按 store_name 聚合会得到 1,321,107.24（S029 + S039 两家合并），那是错误口径

-- ---------------------------------------------------------------------------
-- 11. 分区裁剪验证：带分区条件时扫描行数应显著小于全表
-- ---------------------------------------------------------------------------
explain select count(*) from ydsh_dwd.dwd_order where order_month = '2024-12';
-- 期望 TableScan rows≈1236（只扫 1 个分区）
explain select count(*) from ydsh_dwd.dwd_order;
-- 期望 TableScan rows=14398（扫 12 个分区）