-- ============================================================
-- 数据仓库 · DWS 汇总层 ETL 装载脚本（第 3 周）
-- ------------------------------------------------------------
-- 前置：先执行 create_dws.sql（DROP 会删数据，故建表与装载必须成对执行）
-- 上游：ydsh_dwd
-- 口径：金额一律取 dwd_order.pay_amount（订单口径）或
--       dwd_order_item.alloc_amount（明细分摊口径），
--       绝不用 item_amount（明细原值，约为实付的 11 倍，见文档"金额三口径"）
-- ============================================================

use ydsh_dws;

set hive.exec.dynamic.partition = true;
set hive.exec.dynamic.partition.mode = nonstrict;
set hive.exec.max.dynamic.partitions = 1000;
set hive.exec.max.dynamic.partitions.pernode = 200;
set hive.auto.convert.join = true;
set hive.mapjoin.smalltable.filesize = 25000000;

-- ------------------------------------------------------------
-- 0. 公共中间结果：订单件数（一条订单 → 明细数量合计）
--    订单表本身没有件数，件数只能从明细表向上汇总；
--    先用 CTE 算好，避免在每张日/周/月表里重复 join 明细。
-- ------------------------------------------------------------
drop table if exists tmp_order_qty;
create table tmp_order_qty as
select order_id, sum(quantity) as item_qty
from ydsh_dwd.dwd_order_item
group by order_id;

-- ------------------------------------------------------------
-- 0.1 公共中间结果：日期 → 自然周映射
--     为什么不用 dim_date.week_of_year？
--     因为它在跨年时会把 12-30 / 12-31 也标成"第 1 周"：
--     实测 week_key='2024-W01' 的 week_start/end 会变成
--     2024-01-01 ~ 2024-12-31（整整一年并进同一周）。
--     这里改为"周一日期往前推 6 天"自行推导：
--       周一 = date_sub(日期, 星期几-1)
--       第几周 = (周一 - 当年1月1日) / 7 + 1   （周末跨年按周一所在年归年）
--     2024-01-01 恰好是周一，故 2024 年第 53 周只有 12-30、12-31 两天。
-- ------------------------------------------------------------
drop table if exists tmp_date_week;
create table tmp_date_week as
select
  date_key,
  week_start,
  concat(cast(year(week_start) as string), '-W',
         lpad(cast(week_no as string), 2, '0'))                        as week_key,
  cast(year(week_start) as int)                                        as week_year,
  week_no,
  day_of_week,
  is_weekend
from (
  select
    date_key,
    week_start,
    cast(floor(datediff(week_start,
         concat(cast(year(week_start) as string), '-01-01')) / 7) as int) + 1 as week_no,
    day_of_week,
    is_weekend
  from (
    select
      date_key,
      date_sub(date_key, cast(day_of_week as int) - 1)                 as week_start,
      day_of_week,
      is_weekend
    from ydsh_dwd.dim_date
  ) d1
) d2;

-- ------------------------------------------------------------
-- 1. dws_sales_day：日 × 渠道
-- ------------------------------------------------------------
insert overwrite table dws_sales_day partition (stat_month)
select
  s.order_date,
  s.channel_code,
  s.channel_name,
  s.is_online,
  s.week_key,
  s.day_of_week,
  s.is_weekend,
  s.order_cnt,
  s.valid_order_cnt,
  s.gmv,
  s.valid_gmv,
  s.discount_amount,
  s.buyer_cnt,
  s.item_qty,
  s.cancel_cnt,
  s.refund_cnt,
  s.aov,
  s.stat_month
from (
  select
    o.order_date                                                        as order_date,
    o.channel_code                                                      as channel_code,
    o.channel_name                                                      as channel_name,
    max(o.is_online)                                                    as is_online,
    max(w.week_key)                                                     as week_key,
    max(w.day_of_week)                                                  as day_of_week,
    max(w.is_weekend)                                                   as is_weekend,
    count(1)                                                            as order_cnt,
    sum(case when o.is_valid_revenue = 1 then 1 else 0 end)             as valid_order_cnt,
    round(sum(o.pay_amount), 2)                                         as gmv,
    round(sum(case when o.is_valid_revenue = 1 then o.pay_amount else 0 end), 2) as valid_gmv,
    round(sum(o.discount_amount), 2)                                    as discount_amount,
    count(distinct o.user_id)                                           as buyer_cnt,
    sum(coalesce(q.item_qty, 0))                                        as item_qty,
    sum(case when o.status_name = '已取消' then 1 else 0 end)          as cancel_cnt,
    sum(case when o.status_name = '退款中' then 1 else 0 end)          as refund_cnt,
    case when count(1) > 0
         then round(sum(o.pay_amount) / count(1), 2) else 0 end         as aov,
    substring(o.order_date, 1, 7)                                       as stat_month
  from ydsh_dwd.dwd_order o
  left join tmp_date_week w
         on o.order_date = w.date_key
  left join tmp_order_qty q
         on o.order_id = q.order_id
  group by o.order_date, o.channel_code, o.channel_name, substring(o.order_date, 1, 7)
) s;

-- ------------------------------------------------------------
-- 2. dws_sales_week：自然周 × 渠道
--    周键来自 tmp_date_week（自己推导，不用 dim_date.week_of_year，
--    否则跨年的 12-30/12-31 会被并进第 1 周）
-- ------------------------------------------------------------
insert overwrite table dws_sales_week partition (stat_month)
select
  r.week_key,
  max(r.week_start)                                                   as week_start,
  date_add(max(r.week_start), 6)                                      as week_end,
  r.week_year                                                         as year,
  r.week_no                                                           as week_of_year,
  r.channel_code,
  r.channel_name,
  max(r.is_online)                                                    as is_online,
  count(1)                                                            as order_cnt,
  sum(case when r.is_valid_revenue = 1 then 1 else 0 end)             as valid_order_cnt,
  round(sum(r.pay_amount), 2)                                         as gmv,
  round(sum(case when r.is_valid_revenue = 1 then r.pay_amount else 0 end), 2) as valid_gmv,
  round(sum(r.discount_amount), 2)                                    as discount_amount,
  count(distinct r.user_id)                                           as buyer_cnt,
  sum(coalesce(r.item_qty, 0))                                        as item_qty,
  sum(case when r.status_name = '已取消' then 1 else 0 end)          as cancel_cnt,
  sum(case when r.status_name = '退款中' then 1 else 0 end)          as refund_cnt,
  case when count(1) > 0
       then round(sum(r.pay_amount) / count(1), 2) else 0 end         as aov,
  min(substring(r.order_date, 1, 7))                                  as stat_month
from (
  select
    w.week_key,
    w.week_year,
    w.week_no,
    w.week_start,
    o.order_date, o.channel_code, o.channel_name, o.is_online,
    o.user_id, o.pay_amount, o.discount_amount, o.is_valid_revenue, o.status_name,
    q.item_qty
  from ydsh_dwd.dwd_order o
  left join tmp_date_week w on o.order_date = w.date_key
  left join tmp_order_qty q  on o.order_id = q.order_id
) r
group by r.week_key, r.week_year, r.week_no, r.channel_code, r.channel_name;

-- ------------------------------------------------------------
-- 3. dws_sales_month：月 × 渠道（不分区表）
-- ------------------------------------------------------------
insert overwrite table dws_sales_month
select
  m.stat_month,
  m.channel_code,
  m.channel_name,
  m.is_online,
  m.order_cnt,
  m.valid_order_cnt,
  m.gmv,
  m.valid_gmv,
  m.discount_amount,
  m.buyer_cnt,
  m.item_qty,
  m.cancel_cnt,
  m.refund_cnt,
  m.aov
from (
  select
    substring(o.order_date, 1, 7)                                       as stat_month,
    o.channel_code                                                      as channel_code,
    o.channel_name                                                      as channel_name,
    max(o.is_online)                                                    as is_online,
    count(1)                                                            as order_cnt,
    sum(case when o.is_valid_revenue = 1 then 1 else 0 end)             as valid_order_cnt,
    round(sum(o.pay_amount), 2)                                         as gmv,
    round(sum(case when o.is_valid_revenue = 1 then o.pay_amount else 0 end), 2) as valid_gmv,
    round(sum(o.discount_amount), 2)                                    as discount_amount,
    count(distinct o.user_id)                                           as buyer_cnt,
    sum(coalesce(q.item_qty, 0))                                        as item_qty,
    sum(case when o.status_name = '已取消' then 1 else 0 end)          as cancel_cnt,
    sum(case when o.status_name = '退款中' then 1 else 0 end)          as refund_cnt,
    case when count(1) > 0
         then round(sum(o.pay_amount) / count(1), 2) else 0 end         as aov
  from ydsh_dwd.dwd_order o
  left join tmp_order_qty q on o.order_id = q.order_id
  group by substring(o.order_date, 1, 7), o.channel_code, o.channel_name
) m;

-- ------------------------------------------------------------
-- 4. dws_category_month：月 × 品类
--    用 alloc_amount（分摊到明细的实付），不用 item_amount（原值）
-- ------------------------------------------------------------
insert overwrite table dws_category_month partition (stat_month)
select
  c.category,
  c.sales_amt,
  c.item_qty,
  c.order_cnt,
  c.buyer_cnt,
  c.sku_cnt,
  c.avg_item_price,
  cast(round(c.sales_amt / sum(c.sales_amt) over (partition by c.stat_month), 6)
       as decimal(12, 6))                                               as sales_share,
  c.stat_month
from (
  select
    p.category                                                          as category,
    round(sum(i.alloc_amount), 2)                                       as sales_amt,
    sum(i.quantity)                                                     as item_qty,
    count(distinct i.order_id)                                          as order_cnt,
    count(distinct i.user_id)                                           as buyer_cnt,
    count(distinct i.product_id)                                        as sku_cnt,
    case when sum(i.quantity) > 0
         then round(sum(i.alloc_amount) / sum(i.quantity), 2) else 0 end as avg_item_price,
    substring(i.order_date, 1, 7)                                       as stat_month
  from ydsh_dwd.dwd_order_item i
  join ydsh_dwd.dim_product p on i.product_id = p.product_id
  group by p.category, substring(i.order_date, 1, 7)
) c;

-- ------------------------------------------------------------
-- 5. dws_store_month：月 × 门店（含坪效）
-- ------------------------------------------------------------
insert overwrite table dws_store_month partition (stat_month)
select
  s.store_id,
  s.store_name,
  s.province,
  s.city,
  s.region_area,
  s.store_area,
  s.order_cnt,
  s.valid_order_cnt,
  s.gmv,
  s.valid_gmv,
  s.buyer_cnt,
  s.aov,
  s.sales_per_sqm,
  s.stat_month
from (
  select
    o.store_id                                                          as store_id,
    st.store_name                                                       as store_name,
    st.province                                                         as province,
    st.city                                                             as city,
    st.region_area                                                      as region_area,
    st.area                                                             as store_area,
    count(1)                                                            as order_cnt,
    sum(case when o.is_valid_revenue = 1 then 1 else 0 end)             as valid_order_cnt,
    round(sum(o.pay_amount), 2)                                         as gmv,
    round(sum(case when o.is_valid_revenue = 1 then o.pay_amount else 0 end), 2) as valid_gmv,
    count(distinct o.user_id)                                           as buyer_cnt,
    case when count(1) > 0
         then round(sum(o.pay_amount) / count(1), 2) else 0 end         as aov,
    case when st.area > 0
         then round(sum(o.pay_amount) / st.area, 2) else 0 end          as sales_per_sqm,
    substring(o.order_date, 1, 7)                                       as stat_month
  from ydsh_dwd.dwd_order o
  join ydsh_dwd.dim_store st on o.store_id = st.store_id
  group by substring(o.order_date, 1, 7), o.store_id, st.store_name, st.province,
           st.city, st.region_area, st.area
) s;

-- ------------------------------------------------------------
-- 6. dws_province_month：月 × 用户所在省
-- ------------------------------------------------------------
insert overwrite table dws_province_month partition (stat_month)
select
  p.province,
  p.region_area,
  p.order_cnt,
  p.valid_order_cnt,
  p.gmv,
  p.valid_gmv,
  p.buyer_cnt,
  p.aov,
  p.arpu,
  cast(round(p.gmv / sum(p.gmv) over (partition by p.stat_month), 6)
       as decimal(12, 6))                                               as gmv_share,
  p.stat_month
from (
  select
    u.province                                                          as province,
    max(u.region_area)                                                  as region_area,
    count(1)                                                            as order_cnt,
    sum(case when o.is_valid_revenue = 1 then 1 else 0 end)             as valid_order_cnt,
    round(sum(o.pay_amount), 2)                                         as gmv,
    round(sum(case when o.is_valid_revenue = 1 then o.pay_amount else 0 end), 2) as valid_gmv,
    count(distinct o.user_id)                                           as buyer_cnt,
    case when count(1) > 0
         then round(sum(o.pay_amount) / count(1), 2) else 0 end         as aov,
    case when count(distinct o.user_id) > 0
         then round(sum(o.pay_amount) / count(distinct o.user_id), 2) else 0 end as arpu,
    substring(o.order_date, 1, 7)                                       as stat_month
  from ydsh_dwd.dwd_order o
  join ydsh_dwd.dim_user u on o.user_id = u.user_id
  group by u.province, substring(o.order_date, 1, 7)
) p;

-- ------------------------------------------------------------
-- 7. dws_user_day：日 × 用户
--    is_first_order 以"该用户全周期最早下单日"为基准，用于拉新分析
-- ------------------------------------------------------------
insert overwrite table dws_user_day partition (stat_month)
select
  d.order_date,
  d.user_id,
  d.order_cnt,
  d.gmv,
  d.valid_gmv,
  d.item_qty,
  case when d.order_date = f.first_date then 1 else 0 end               as is_first_order,
  d.stat_month
from (
  select
    o.order_date                                                        as order_date,
    o.user_id                                                           as user_id,
    count(1)                                                            as order_cnt,
    round(sum(o.pay_amount), 2)                                         as gmv,
    round(sum(case when o.is_valid_revenue = 1 then o.pay_amount else 0 end), 2) as valid_gmv,
    sum(coalesce(q.item_qty, 0))                                        as item_qty,
    substring(o.order_date, 1, 7)                                       as stat_month
  from ydsh_dwd.dwd_order o
  left join tmp_order_qty q on o.order_id = q.order_id
  group by o.order_date, o.user_id, substring(o.order_date, 1, 7)
) d
join (
  select user_id, min(order_date) as first_date
  from ydsh_dwd.dwd_order
  group by user_id
) f on d.user_id = f.user_id;

-- ------------------------------------------------------------
-- 8. dws_user_month：月 × 用户（含累计消费与复购标记）
-- ------------------------------------------------------------
insert overwrite table dws_user_month partition (stat_month)
select
  a.user_id,
  a.user_name,
  a.member_level,
  a.level_rank,
  a.province,
  a.order_cnt,
  a.gmv,
  a.valid_gmv,
  a.first_order_date,
  a.last_order_date,
  a.avg_order_amt,
  sum(a.gmv) over (partition by a.user_id order by a.stat_month
                   rows between unbounded preceding and current row)    as cum_gmv,
  case when a.order_cnt >= 2 then 1 else 0 end                          as is_repurchase,
  a.stat_month
from (
  select
    o.user_id                                                           as user_id,
    max(u.user_name)                                                    as user_name,
    max(u.member_level)                                                 as member_level,
    max(u.level_rank)                                                   as level_rank,
    max(u.province)                                                     as province,
    count(1)                                                            as order_cnt,
    round(sum(o.pay_amount), 2)                                         as gmv,
    round(sum(case when o.is_valid_revenue = 1 then o.pay_amount else 0 end), 2) as valid_gmv,
    min(o.order_date)                                                   as first_order_date,
    max(o.order_date)                                                   as last_order_date,
    round(sum(o.pay_amount) / count(1), 2)                              as avg_order_amt,
    substring(o.order_date, 1, 7)                                       as stat_month
  from ydsh_dwd.dwd_order o
  join ydsh_dwd.dim_user u on o.user_id = u.user_id
  group by o.user_id, substring(o.order_date, 1, 7)
) a;

-- ------------------------------------------------------------
-- 9. dws_behavior_day：日 × 行为类型
-- ------------------------------------------------------------
insert overwrite table dws_behavior_day partition (stat_month)
select
  b.behavior_date,
  b.behavior_type,
  b.pv_cnt,
  b.uv_cnt,
  b.product_cnt,
  b.session_cnt,
  cast(round(b.pv_cnt / sum(b.pv_cnt) over (partition by b.behavior_date), 6)
       as decimal(12, 6))                                               as pv_share,
  b.stat_month
from (
  select
    behavior_date                                                       as behavior_date,
    behavior_type                                                       as behavior_type,
    count(1)                                                            as pv_cnt,
    count(distinct user_id)                                             as uv_cnt,
    count(distinct product_id)                                          as product_cnt,
    count(distinct session_id)                                          as session_cnt,
    substring(behavior_date, 1, 7)                                      as stat_month
  from ydsh_dwd.dwd_user_behavior
  group by behavior_date, behavior_type, substring(behavior_date, 1, 7)
) b;

-- 中间表用完即删，保持 ydsh_dws 只有交付的 9 张汇总表
drop table if exists tmp_order_qty;
drop table if exists tmp_date_week;

-- 周表自检：每个 week_key 只对应一个 week_start，且 week_end = start + 6 天
select count(1) as week_key_conflict
from (
  select week_key, count(distinct week_start) as c
  from dws_sales_week group by week_key having count(distinct week_start) > 1
) t;

select week_key, week_start, week_end, count(1) as channels,
       cast(round(sum(gmv), 2) as decimal(18, 2)) as gmv
from dws_sales_week
where week_key in ('2024-W01', '2024-W02', '2024-W53')
group by week_key, week_start, week_end
order by week_key;

-- ------------------------------------------------------------
-- 10. 装载结果核对
--     这里刻意"一条语句一张表"，不用 union all 拼成一张结果集：
--     9 路 union 会各自起一个 Tez DAG，计数器立刻超过 120 上限，
--     报 "Counters limit exceeded: Too many counters: 121 max=120"。
--     （已实测 set tez.counters.max / tez.counters.limit 均无效，
--       该 Tez 版本在 AM 侧固定 120，只能拆语句。）
-- ------------------------------------------------------------
select count(1) as dws_sales_day       from dws_sales_day;
select count(1) as dws_sales_week      from dws_sales_week;
select count(1) as dws_sales_month     from dws_sales_month;
select count(1) as dws_category_month  from dws_category_month;
select count(1) as dws_store_month     from dws_store_month;
select count(1) as dws_province_month  from dws_province_month;
select count(1) as dws_user_day        from dws_user_day;
select count(1) as dws_user_month      from dws_user_month;
select count(1) as dws_behavior_day    from dws_behavior_day;

-- 分区数（除 dws_sales_month 不分区外，均应为 12）
select count(distinct stat_month) as part_sales_day      from dws_sales_day;
select count(distinct stat_month) as part_sales_week     from dws_sales_week;
select count(distinct stat_month) as part_category_month from dws_category_month;
select count(distinct stat_month) as part_store_month    from dws_store_month;
select count(distinct stat_month) as part_province_month from dws_province_month;
select count(distinct stat_month) as part_user_day       from dws_user_day;
select count(distinct stat_month) as part_user_month     from dws_user_month;
select count(distinct stat_month) as part_behavior_day   from dws_behavior_day;