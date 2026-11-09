-- ============================================================
-- 数据仓库 · DWS 汇总层校验脚本（第 3 周）
-- ------------------------------------------------------------
-- 校验思路：DWS 是"可加总"的预聚合层，因此每一张表都必须
--           能回滚到 DWD 的口径，否则 DWS 就是错的。
--           以下 7 组校验全部为只读（SELECT / SHOW / EXPLAIN）。
-- 注意：每条语句只查一张表 / 一个指标，不要用 union 拼装，
--       否则 9 路 union 会触发 Tez "Too many counters: 121 max=120"。
-- ============================================================

use ydsh_dws;

-- ------------------------------------------------------------
-- 1. 行数
-- ------------------------------------------------------------
select count(1) as sales_day_rows      from dws_sales_day;
select count(1) as sales_week_rows     from dws_sales_week;
select count(1) as sales_month_rows    from dws_sales_month;
select count(1) as category_month_rows from dws_category_month;
select count(1) as store_month_rows    from dws_store_month;
select count(1) as province_month_rows from dws_province_month;
select count(1) as user_day_rows       from dws_user_day;
select count(1) as user_month_rows     from dws_user_month;
select count(1) as behavior_day_rows   from dws_behavior_day;

-- ------------------------------------------------------------
-- 2. 分区数量（除 dws_sales_month，其余均应为 12）
-- ------------------------------------------------------------
select count(distinct stat_month) as part_sales_day      from dws_sales_day;
select count(distinct stat_month) as part_sales_week     from dws_sales_week;
select count(distinct stat_month) as part_category_month from dws_category_month;
select count(distinct stat_month) as part_store_month    from dws_store_month;
select count(distinct stat_month) as part_province_month from dws_province_month;
select count(distinct stat_month) as part_user_day       from dws_user_day;
select count(distinct stat_month) as part_user_month     from dws_user_month;
select count(distinct stat_month) as part_behavior_day   from dws_behavior_day;

-- ------------------------------------------------------------
-- 3. 口径回滚一：DWS 日汇总的 GMV 合计 = DWD 订单实付合计
--    预期 36,116,687.06
-- ------------------------------------------------------------
select cast(round(sum(gmv), 2) as decimal(18, 2))         as dws_gmv_sum
from dws_sales_day;
select cast(round(sum(pay_amount), 2) as decimal(18, 2))  as dwd_gmv_sum
from ydsh_dwd.dwd_order;

-- 有效 GMV 回滚，预期 24,185,272.59
select cast(round(sum(valid_gmv), 2) as decimal(18, 2))   as dws_valid_gmv_sum
from dws_sales_day;
select cast(round(sum(case when is_valid_revenue = 1 then pay_amount else 0 end), 2)
       as decimal(18, 2))                                 as dwd_valid_gmv_sum
from ydsh_dwd.dwd_order;

-- 订单量回滚，预期 14,398
select sum(order_cnt) as dws_order_cnt from dws_sales_day;
select count(1)       as dwd_order_cnt from ydsh_dwd.dwd_order;

-- 下单用户数回滚，预期 1,000
select count(distinct user_id) as dws_buyer_cnt from dws_user_day;
select count(distinct user_id) as dwd_buyer_cnt from ydsh_dwd.dwd_order;

-- ------------------------------------------------------------
-- 4. 口径回滚二：日 / 周 / 月三层必须彼此相等（"同源可加总"）
-- ------------------------------------------------------------
select cast(round(sum(gmv), 2) as decimal(18, 2)) as by_day   from dws_sales_day;
select cast(round(sum(gmv), 2) as decimal(18, 2)) as by_week  from dws_sales_week;
select cast(round(sum(gmv), 2) as decimal(18, 2)) as by_month from dws_sales_month;

-- ------------------------------------------------------------
-- 5. 口径回滚三：品类汇总 = 明细分摊合计（预期 35,833,305.06）
--    比订单口径少 283,382.65，差额来自 114 张"有订单无明细"的单
-- ------------------------------------------------------------
select cast(round(sum(sales_amt), 2) as decimal(18, 2))   as dws_category_sales
from dws_category_month;
select cast(round(sum(alloc_amount), 2) as decimal(18, 2)) as dwd_item_alloc
from ydsh_dwd.dwd_order_item;

-- 有订单但无明细的订单数与金额（差额来源）
select count(1) as orders_without_item,
       cast(round(sum(o.pay_amount), 2) as decimal(18, 2)) as amount_without_item
from ydsh_dwd.dwd_order o
left join (select distinct order_id from ydsh_dwd.dwd_order_item) i
       on o.order_id = i.order_id
where i.order_id is null;

-- ------------------------------------------------------------
-- 6. 占比闭合：每月各维度占比之和应为 1
-- ------------------------------------------------------------
select stat_month, cast(round(sum(sales_share), 6) as decimal(12, 6)) as share_sum
from dws_category_month group by stat_month order by stat_month;

select stat_month, cast(round(sum(gmv_share), 6) as decimal(12, 6)) as share_sum
from dws_province_month group by stat_month order by stat_month;

-- ------------------------------------------------------------
-- 7. 分区裁剪实测（对比带 / 不带分区条件时的扫描行数）
-- ------------------------------------------------------------
explain select count(1) from dws_sales_day where stat_month = '2024-12';
explain select count(1) from dws_sales_day;

-- ------------------------------------------------------------
-- 8. 主键唯一性：日×渠道、月×品类、月×门店 不应有重复粒度
-- ------------------------------------------------------------
select count(1) as dup_sales_day
from (
  select order_date, channel_code, count(1) as c
  from dws_sales_day group by order_date, channel_code having count(1) > 1
) t;

select count(1) as dup_category_month
from (
  select stat_month, category, count(1) as c
  from dws_category_month group by stat_month, category having count(1) > 1
) t;

select count(1) as dup_user_month
from (
  select stat_month, user_id, count(1) as c
  from dws_user_month group by stat_month, user_id having count(1) > 1
) t;

-- ------------------------------------------------------------
-- 9. 累计消费单调性：cum_gmv 必须 >= 当月 gmv
-- ------------------------------------------------------------
select count(1) as cum_gmv_violation
from dws_user_month where cum_gmv < gmv;

-- ------------------------------------------------------------
-- 10. 关键技术演示：取某月某渠道的一天明细（人肉看一眼数据）
-- ------------------------------------------------------------
select order_date, channel_name, order_cnt, gmv, buyer_cnt, aov
from dws_sales_day
where stat_month = '2024-12'
order by order_date, channel_name
limit 8;