-- ============================================================
-- DWD 层结构与加载校验（补充校验脚本）
-- 用于答辩演示：分桶信息、分区裁剪、明细与订单金额闭合、孤儿订单
-- ============================================================
use ydsh_dwd;

-- 1) 分桶信息（应显示 Num Buckets: 8，Bucket Columns: [user_id]）
describe formatted dwd_order;

-- 2) 分区裁剪：查询单月时应只扫描 1 个分区
explain select count(*) from dwd_order where order_month = '2024-12';

-- 3) 分区裁剪对比：不带分区条件时扫描全部 12 个分区
explain select count(*) from dwd_order;

-- 4) 有明细的订单数 / 没有明细的订单数
select count(distinct order_id) as orders_with_items,
       round(sum(alloc_amount), 2) as alloc_sum
from dwd_order_item;

select count(*) as orders_without_items
from dwd_order o
left join (select distinct order_id, order_month from dwd_order_item) i
  on o.order_id = i.order_id and o.order_month = i.order_month
where i.order_id is null;

-- 5) 金额闭合校验：有明细订单的实付合计 应等于 明细分摊合计
select round(sum(o.pay_amount), 2) as pay_sum_of_orders_with_items
from dwd_order o
join (select distinct order_id, order_month from dwd_order_item) i
  on o.order_id = i.order_id and o.order_month = i.order_month;

-- 6) 事实表 + 维度表星型 JOIN 演示（订单宽表片段）
select o.order_id, o.order_timestamp, u.province, u.member_level,
       s.store_name, p.category, o.pay_amount, o.status_name
from dwd_order o
join dim_user u    on o.user_id = u.user_id
join dim_store s   on o.store_id = s.store_id
join dwd_order_item i on o.order_id = i.order_id
join dim_product p on i.product_id = p.product_id
where o.order_month = '2024-12'
limit 5;

-- 7) 分桶抽样：TABLESAMPLE(BUCKET 1 OUT OF 8) 只读 1/8 数据
select count(*) as bucket1_orders
from dwd_order tablesample(bucket 1 out of 8 on user_id);