-- ============================================================
-- 数据清洗（二）· 子任务 1：枚举字段标准化 + 文本规范化
-- ------------------------------------------------------------
-- 依赖（第 1 周清洗一产物，执行前需确认存在）：
--   ydsh_ods.dwd_user      缺失值清洗后用户表
--   ydsh_ods.dwd_product   缺失值清洗后商品表
--   ydsh_ods.dwd_order     去重后订单表
--   ydsh_ods.ods_user_behavior  行为日志（无缺失/重复，直接用 ODS）
-- 输出（本脚本生成 4 张标准化中间表）：
--   ydsh_dwd.stg_user_enum / stg_product_enum / stg_order_enum / stg_behavior_enum
-- ------------------------------------------------------------
-- 统一枚举值域（全部统一为中文标准值）：
--   gender        男 / 女 / 未知
--   member_level  普通会员 / 银卡会员 / 金卡会员 / 钻石会员
--   order_status  待支付 / 已支付 / 已完成 / 已取消 / 退款中
--   pay_type      支付宝 / 微信支付 / 银行卡 / 货到付款
--   channel       门店 / APP / 小程序 / PC官网
--   behavior_type 浏览 / 加购 / 收藏 / 购买
-- ============================================================

create database if not exists ydsh_dwd;
use ydsh_dwd;

-- ------------------------------------------------------------
-- 1. 用户表：gender、member_level 标准化
--    空值性别 -> 未知；空会员等级 -> 普通会员，并打 level_imputed 标记
-- ------------------------------------------------------------
drop table if exists stg_user_enum;

create table stg_user_enum as
select
  user_id,
  user_name,
  case when lower(trim(gender)) in ('男', 'm', 'male', '1') then '男'
       when lower(trim(gender)) in ('女', 'f', 'female', '0') then '女'
       else '未知' end                                        as gender,
  age,
  trim(city)                                                  as city,
  trim(province)                                              as province,
  register_date,
  case when lower(trim(member_level)) in ('金卡会员', '金卡', 'gold')     then '金卡会员'
       when lower(trim(member_level)) in ('银卡会员', '银卡', 'silver')   then '银卡会员'
       when lower(trim(member_level)) in ('钻石会员', '钻石', 'diamond')  then '钻石会员'
       else '普通会员' end                                    as member_level,
  case when member_level is null or trim(member_level) = '' then 1 else 0 end as level_imputed,
  phone,
  email,
  email_missing,
  age_filled
from ydsh_ods.dwd_user;

-- ------------------------------------------------------------
-- 2. 商品表：category / brand 去首尾空格、压缩内部空白、统一大写
--    （中文类目不受大小写影响，规则用于兜底英文品牌/类目）
-- ------------------------------------------------------------
drop table if exists stg_product_enum;

create table stg_product_enum as
select
  product_id,
  product_name,
  upper(regexp_replace(trim(category), '\\s+', ''))     as category,
  upper(regexp_replace(trim(sub_category), '\\s+', '')) as sub_category,
  upper(regexp_replace(trim(brand), '\\s+', ''))        as brand,
  price,
  cost,
  stock,
  trim(status)                                          as status,
  launch_date,
  launch_date_filled
from ydsh_ods.dwd_product;

-- ------------------------------------------------------------
-- 3. 订单表：order_status / pay_type / channel 标准化
--    order_status 阿拉伯数字编码按 dim_order_status 编码表约定映射
-- ------------------------------------------------------------
drop table if exists stg_order_enum;

create table stg_order_enum as
select
  order_id,
  user_id,
  store_id,
  order_date,
  order_time,
  pay_amount,
  discount_amount,
  case when lower(trim(pay_type)) in ('支付宝', 'alipay', 'ali')        then '支付宝'
       when lower(trim(pay_type)) in ('微信支付', '微信', 'wechat', 'wx') then '微信支付'
       when lower(trim(pay_type)) in ('银行卡', 'bank', 'card', '银联')   then '银行卡'
       when lower(trim(pay_type)) in ('货到付款', 'cod', 'cash')          then '货到付款'
       else '其他' end                                    as pay_type,
  case when lower(trim(order_status)) in ('已完成', '完成', '3')                then '已完成'
       when lower(trim(order_status)) in ('已支付', '已付款', '2')              then '已支付'
       when lower(trim(order_status)) in ('待支付', '1')                       then '待支付'
       when lower(trim(order_status)) in ('已取消', 'cancelled', 'canceled', '4') then '已取消'
       when lower(trim(order_status)) in ('退款中', 'refunding', '5')           then '退款中'
       else '未知' end                                    as order_status,
  case when lower(trim(channel)) in ('门店', 'store', '线下门店')   then '门店'
       when lower(trim(channel)) in ('app')                          then 'APP'
       when lower(trim(channel)) in ('小程序', 'miniapp')            then '小程序'
       when lower(trim(channel)) in ('pc官网', 'pc', '官网')          then 'PC官网'
       else '其他' end                                    as channel
from ydsh_ods.dwd_order;

-- ------------------------------------------------------------
-- 4. 行为日志：behavior_type 标准化
-- ------------------------------------------------------------
drop table if exists stg_behavior_enum;

create table stg_behavior_enum as
select
  behavior_id,
  user_id,
  product_id,
  case when lower(trim(behavior_type)) in ('pv', '浏览', 'view', 'page_view') then '浏览'
       when lower(trim(behavior_type)) in ('cart', '加购', 'add_cart')        then '加购'
       when lower(trim(behavior_type)) in ('fav', '收藏', 'favorite')         then '收藏'
       when lower(trim(behavior_type)) in ('buy', '购买', 'purchase')         then '购买'
       else '其他' end                             as behavior_type,
  behavior_time,
  session_id
from ydsh_ods.ods_user_behavior;

-- ============================================================
-- 5. 校验：各枚举字段 distinct 取值必须收敛到规范值域
-- ============================================================
select '0) 表行数' as check_item;
select 'stg_user_enum'      as tbl, count(*) as cnt from stg_user_enum
union all select 'stg_product_enum', count(*) from stg_product_enum
union all select 'stg_order_enum',   count(*) from stg_order_enum
union all select 'stg_behavior_enum',count(*) from stg_behavior_enum;

-- 5.1 gender
select gender, count(*) as cnt from stg_user_enum group by gender order by cnt desc;
-- 5.2 member_level
select member_level, sum(level_imputed) as imputed, count(*) as cnt
from stg_user_enum group by member_level order by cnt desc;
-- 5.3 order_status
select order_status, count(*) as cnt from stg_order_enum group by order_status order by cnt desc;
-- 5.4 pay_type
select pay_type, count(*) as cnt from stg_order_enum group by pay_type order by cnt desc;
-- 5.5 channel
select channel, count(*) as cnt from stg_order_enum group by channel order by cnt desc;
-- 5.6 behavior_type
select behavior_type, count(*) as cnt from stg_behavior_enum group by behavior_type order by cnt desc;
-- 5.7 category 是否存在首尾空格
select category, count(*) as cnt from stg_product_enum group by category order by cnt desc;

-- 5.8 收敛性断言：非规范值残留条数（应全部为 0）
select
  sum(if(gender not in ('男', '女', '未知'), 1, 0))                            as gender_bad
from stg_user_enum;
select
  sum(if(member_level not in ('普通会员', '银卡会员', '金卡会员', '钻石会员'), 1, 0)) as member_level_bad
from stg_user_enum;
select
  sum(if(order_status not in ('待支付', '已支付', '已完成', '已取消', '退款中'), 1, 0)) as order_status_bad,
  sum(if(pay_type not in ('支付宝', '微信支付', '银行卡', '货到付款'), 1, 0))         as pay_type_bad,
  sum(if(channel not in ('门店', 'APP', '小程序', 'PC官网'), 1, 0))                 as channel_bad
from stg_order_enum;
select
  sum(if(behavior_type not in ('浏览', '加购', '收藏', '购买'), 1, 0))              as behavior_type_bad
from stg_behavior_enum;
select
  sum(if(category <> trim(category) or category rlike ' ', 1, 0))                as category_space_bad,
  sum(if(brand <> trim(brand) or brand rlike ' ', 1, 0))                         as brand_space_bad
from stg_product_enum;