-- ============================================================
-- 数据质量预评估（五维度）
-- 每个维度单独一条语句执行，避免单个 Tez 作业计数器超限
-- 输出列：dim | metric | val
-- ============================================================
use ydsh_ods;

-- ---------- 1. 完整性 ----------
select '完整性' as dim, 'ods_user.age 空值数' as metric, cast(sum(if(age is null,1,0)) as string) as val from ods_user
union all select '完整性','ods_user.email 空值数', cast(sum(if(email is null or email='',1,0)) as string) from ods_user
union all select '完整性','ods_product.launch_date 空值数', cast(sum(if(launch_date is null or launch_date='',1,0)) as string) from ods_product
union all select '完整性','ods_order.pay_amount 空值数', cast(sum(if(pay_amount is null,1,0)) as string) from ods_order;

-- ---------- 2. 唯一性 ----------
select '唯一性' as dim,
       'ods_order 重复行数' as metric,
       cast(count(*) - count(distinct order_id) as string) as val from ods_order
union all select '唯一性','ods_order 去重后订单数', cast(count(distinct order_id) as string) from ods_order
union all select '唯一性','ods_user_behavior 重复行为数', cast(count(*) - count(distinct behavior_id) as string) from ods_user_behavior
union all select '唯一性','ods_order_item 重复明细数', cast(count(*) - count(distinct item_id) as string) from ods_order_item;

-- ---------- 3. 一致性 ----------
select '一致性' as dim, 'ods_user.register_date 含斜杠' as metric, cast(sum(if(register_date like '%/%',1,0)) as string) as val from ods_user
union all select '一致性','ods_user.register_date 8位无分隔', cast(sum(if(length(register_date)=8,1,0)) as string) from ods_user
union all select '一致性','ods_user.phone 含横线', cast(sum(if(phone like '%-%',1,0)) as string) from ods_user
union all select '一致性','ods_order.order_date 含斜杠', cast(sum(if(order_date like '%/%',1,0)) as string) from ods_order
union all select '一致性','ods_user_behavior.behavior_time 含斜杠', cast(sum(if(behavior_time like '%/%',1,0)) as string) from ods_user_behavior;

-- ---------- 4. 准确性 ----------
select '准确性' as dim, 'ods_user.age <0 或 >120' as metric, cast(sum(if(age < 0 or age > 120,1,0)) as string) as val from ods_user
union all select '准确性','ods_product.price <0', cast(sum(if(price < 0,1,0)) as string) from ods_product
union all select '准确性','ods_product.price >100000', cast(sum(if(price > 100000,1,0)) as string) from ods_product
union all select '准确性','ods_order.pay_amount <0', cast(sum(if(pay_amount < 0,1,0)) as string) from ods_order
union all select '准确性','ods_order.pay_amount >1000000', cast(sum(if(pay_amount > 1000000,1,0)) as string) from ods_order
union all select '准确性','ods_order_item.quantity <=0', cast(sum(if(quantity <= 0,1,0)) as string) from ods_order_item;

-- ---------- 5. 有效性 ----------
select '有效性' as dim, 'ods_order.order_status 取值种类' as metric, cast(count(distinct order_status) as string) as val from ods_order
union all select '有效性','ods_order.pay_type 取值种类', cast(count(distinct pay_type) as string) from ods_order
union all select '有效性','ods_user.gender 取值种类', cast(count(distinct gender) as string) from ods_user
union all select '有效性','ods_user.member_level 取值种类', cast(count(distinct member_level) as string) from ods_user
union all select '有效性','ods_product.category 取值种类', cast(count(distinct category) as string) from ods_product;
