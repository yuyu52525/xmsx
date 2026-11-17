-- ============================================================
-- 数据仓库 · 第 4 周 ADS 增量校验脚本
-- ------------------------------------------------------------
-- 目的：证明新表"行数对、口径对、占比自洽、能和旧表对上、能回明细复算"
-- 语法注意：Hive 4 下中文别名必须加反引号，否则报 cannot recognize input near 'as'
-- 用法：python py/sql_runner.py sql/ads/verify_ads_w4.sql
-- ============================================================

use ydsh_ads;

-- ---------- 一、行数与粒度 ----------
-- 期望：ads_pay_type_month = 48（12 月 × 4 种支付方式）
select 'ads_pay_type_month 行数' as `检查项`, count(1) as `值` from ads_pay_type_month;
select 'ads_pay_type_month 月份数' as `检查项`, count(distinct stat_month) as `值` from ads_pay_type_month;
select 'ads_pay_type_month 支付方式数' as `检查项`, count(distinct pay_code) as `值` from ads_pay_type_month;
select 'ads_pay_type_month 重复粒度行数' as `检查项`, count(1) as `值`
from (select stat_month, pay_code from ads_pay_type_month group by stat_month, pay_code having count(1) > 1) x;

-- 期望：ads_hour_category = 192（24 小时 × 8 品类）
select 'ads_hour_category 行数' as `检查项`, count(1) as `值` from ads_hour_category;
select 'ads_hour_category 小时数' as `检查项`, count(distinct hour_of_day) as `值` from ads_hour_category;
select 'ads_hour_category 品类数' as `检查项`, count(distinct category) as `值` from ads_hour_category;
select 'ads_hour_category 重复粒度行数' as `检查项`, count(1) as `值`
from (select hour_of_day, category from ads_hour_category group by hour_of_day, category having count(1) > 1) x;

-- ---------- 二、金额口径对账（最关键） ----------
-- ads_pay_type_month 是订单口径 → 必须等于 ads_kpi_overview.gmv
select '支付表 GMV 合计' as `检查项`, round(sum(gmv), 2) as `值` from ads_pay_type_month;
select 'KPI 总览 GMV' as `检查项`, round(max(gmv), 2) as `值` from ads_kpi_overview;
select '支付表 有效GMV 合计' as `检查项`, round(sum(valid_gmv), 2) as `值` from ads_pay_type_month;
select 'KPI 总览 有效GMV' as `检查项`, round(max(valid_gmv), 2) as `值` from ads_kpi_overview;
select '支付表 订单量合计' as `检查项`, sum(order_cnt) as `值` from ads_pay_type_month;
select 'KPI 总览 订单量' as `检查项`, max(order_cnt) as `值` from ads_kpi_overview;

-- ads_hour_category 是明细口径 → 必须等于 ads_category_rank 合计
select '热力表 销售额合计' as `检查项`, round(sum(sales_amt), 2) as `值` from ads_hour_category;
select '品类榜 销售额合计' as `检查项`, round(sum(sales_amt), 2) as `值` from ads_category_rank;
select '热力表 件数合计' as `检查项`, sum(item_qty) as `值` from ads_hour_category;
select '品类榜 件数合计' as `检查项`, sum(item_qty) as `值` from ads_category_rank;

-- ---------- 三、占比字段自洽（分组内占比求和应为 1） ----------
select '支付表 每月 GMV 占比求和偏差' as `检查项`,
       cast(round(max(abs(s - 1)), 4) as decimal(8, 4)) as `值`
from (select stat_month, sum(gmv_share) as s from ads_pay_type_month group by stat_month) x;

select '热力表 每品类时段占比求和偏差' as `检查项`,
       cast(round(max(abs(s - 1)), 4) as decimal(8, 4)) as `值`
from (select category, sum(hour_share_of_category) as s from ads_hour_category group by category) x;

select '热力表 每小时品类占比求和偏差' as `检查项`,
       cast(round(max(abs(s - 1)), 4) as decimal(8, 4)) as `值`
from (select hour_of_day, sum(category_share_of_hour) as s from ads_hour_category group by hour_of_day) x;

-- ---------- 四、分布形态（业务可解释性） ----------
-- 支付方式全年构成（饼图数据）
select pay_name,
       round(sum(gmv), 2)                                              as gmv,
       sum(order_cnt)                                                  as order_cnt,
       cast(round(sum(gmv) / 36116687.06, 4) as decimal(8, 4))         as gmv_share_of_year
from ads_pay_type_month
group by pay_name
order by gmv desc;

-- 时段高峰：全年每小时销售额（应呈"午间 + 晚间双峰"）
select hour_of_day, round(sum(sales_amt), 2) as sales_amt, sum(order_cnt) as order_cnt
from ads_hour_category
group by hour_of_day
order by hour_of_day;

-- 品类 × 时段：每个品类的峰值时段（检验热力图是否存在梯度）
select category,
       max(category_order)                                             as category_order,
       round(sum(sales_amt), 2)                                        as year_amt,
       cast(max(peak_hour) as int)                                     as peak_hour
from (
  select category, category_order, hour_of_day, sales_amt,
         first_value(hour_of_day) over (partition by category order by sales_amt desc) as peak_hour
  from ads_hour_category
) t
group by category
order by year_amt desc;

-- ---------- 五、明细可追溯抽样（回 DWD 复算 3 个格子） ----------
select '抽样1 支付表 2024-12 微信' as `检查项`, round(sum(gmv), 2) as `值`
from ads_pay_type_month where stat_month = '2024-12' and pay_code = 'P2';
select '抽样1 DWD 复算' as `检查项`, round(sum(pay_amount), 2) as `值`
from ydsh_dwd.dwd_order
where substr(order_date, 1, 7) = '2024-12' and pay_code = 'P2';

select '抽样2 热力表 9点 食品生鲜' as `检查项`, round(sum(sales_amt), 2) as `值`
from ads_hour_category where hour_of_day = 9 and category = '食品生鲜';
select '抽样2 DWD 复算' as `检查项`, round(sum(i.alloc_amount), 2) as `值`
from ydsh_dwd.dwd_order_item i
join ydsh_dwd.dwd_order   o on i.order_id   = o.order_id
join ydsh_dwd.dim_product p on i.product_id = p.product_id
where o.order_hour = 9 and p.category = '食品生鲜';