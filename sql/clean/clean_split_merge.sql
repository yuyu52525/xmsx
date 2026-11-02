-- ============================================================
-- 数据清洗（二）· 子任务 3：字段拆分合并 + 编码映射
-- ------------------------------------------------------------
-- 依赖：clean_format.sql 生成的
--   ydsh_dwd.stg_user_fmt / stg_product_fmt / stg_order_fmt
-- 输出：
--   编码映射维表：dim_member_level / dim_pay_type / dim_order_status / dim_channel
--   合并后中间表：stg_user_dim（region 合并 + 年龄分层 + 等级编码）
--                 stg_order_fact（order_timestamp 合并 + 月份 + 各编码关联）
-- ------------------------------------------------------------
-- 说明：
--   1) order_date + order_time 合并为 order_timestamp（yyyy-MM-dd HH:mm:ss）
--   2) province + city 合并为 region（省-市），并按七大区派生 region_area
--   3) 会员等级、支付方式、订单状态、下单渠道 4 个枚举字段建立编码映射表，
--      DWD 层通过关联把「编码」翻译成「中文名称」，事实表只存 code 不存 text
-- ============================================================

use ydsh_dwd;

-- ------------------------------------------------------------
-- 1. 编码映射维表
-- ------------------------------------------------------------
drop table if exists dim_member_level;
create table dim_member_level (
  level_code string comment '等级编码',
  level_name string comment '等级名称',
  level_rank int    comment '等级序号（越大越高）'
) stored as orc;

insert overwrite table dim_member_level values
  ('L1', '普通会员', 1),
  ('L2', '银卡会员', 2),
  ('L3', '金卡会员', 3),
  ('L4', '钻石会员', 4);

drop table if exists dim_pay_type;
create table dim_pay_type (
  pay_code     string comment '支付方式编码',
  pay_name     string comment '支付方式名称',
  pay_category string comment '支付渠道大类'
) stored as orc;

insert overwrite table dim_pay_type values
  ('P1', '支付宝',   '第三方支付'),
  ('P2', '微信支付', '第三方支付'),
  ('P3', '银行卡',   '银行渠道'),
  ('P4', '货到付款', '线下支付');

drop table if exists dim_order_status;
create table dim_order_status (
  status_code      string comment '订单状态编码',
  status_name      string comment '订单状态名称',
  is_paid          int    comment '是否已付款',
  is_valid_revenue int    comment '是否计入有效营收'
) stored as orc;

insert overwrite table dim_order_status values
  ('S1', '待支付', 0, 0),
  ('S2', '已支付', 1, 1),
  ('S3', '已完成', 1, 1),
  ('S4', '已取消', 0, 0),
  ('S5', '退款中', 1, 0);

drop table if exists dim_channel;
create table dim_channel (
  channel_code string comment '渠道编码',
  channel_name string comment '渠道名称',
  is_online    int    comment '是否线上渠道'
) stored as orc;

insert overwrite table dim_channel values
  ('C1', '门店',   0),
  ('C2', 'APP',    1),
  ('C3', '小程序', 1),
  ('C4', 'PC官网', 1);

-- ------------------------------------------------------------
-- 2. 用户维度：region 合并、大区派生、年龄分层、等级编码关联
-- ------------------------------------------------------------
drop table if exists stg_user_dim;

create table stg_user_dim as
select
  u.user_id,
  u.user_name,
  u.gender,
  u.age,
  case when u.age < 25 then '25岁以下'
       when u.age < 35 then '25-34岁'
       when u.age < 45 then '35-44岁'
       when u.age < 55 then '45-54岁'
       else '55岁及以上' end                                  as age_group,
  u.city,
  u.province,
  concat(u.province, '-', u.city)                             as region,
  case when u.province in ('北京市', '天津市', '河北省', '山西省', '内蒙古自治区') then '华北'
       when u.province in ('辽宁省', '吉林省', '黑龙江省')                        then '东北'
       when u.province in ('上海市', '江苏省', '浙江省', '安徽省', '福建省', '山东省') then '华东'
       when u.province in ('河南省', '湖北省', '湖南省')                          then '华中'
       when u.province in ('广东省', '广西壮族自治区', '海南省')                   then '华南'
       when u.province in ('重庆市', '四川省', '贵州省', '云南省', '西藏自治区')    then '西南'
       when u.province in ('陕西省', '甘肃省', '青海省', '宁夏回族自治区', '新疆维吾尔自治区') then '西北'
       else '其他' end                                        as region_area,
  u.register_date,
  m.level_code,
  u.member_level,
  m.level_rank,
  u.level_imputed,
  u.phone,
  u.email,
  u.email_missing,
  u.age_filled
from stg_user_fmt u
left join dim_member_level m on u.member_level = m.level_name;

-- ------------------------------------------------------------
-- 3. 订单事实：时间戳合并 + 月份 + 编码关联
-- ------------------------------------------------------------
drop table if exists stg_order_fact;

create table stg_order_fact as
select
  o.order_id,
  o.user_id,
  o.store_id,
  o.order_date,
  o.order_time,
  concat(o.order_date, ' ', o.order_time)                     as order_timestamp,
  cast(substr(o.order_time, 1, 2) as int)                     as order_hour,
  substr(o.order_date, 1, 7)                                  as order_month,
  o.pay_amount,
  o.discount_amount,
  p.pay_code,
  p.pay_name,
  s.status_code,
  s.status_name,
  s.is_paid,
  s.is_valid_revenue,
  c.channel_code,
  c.channel_name,
  c.is_online,
  o.pay_type,
  o.order_status,
  o.channel
from stg_order_fmt o
left join dim_pay_type     p on o.pay_type = p.pay_name
left join dim_order_status s on o.order_status = s.status_name
left join dim_channel      c on o.channel = c.channel_name;

-- ============================================================
-- 4. 校验
-- ============================================================
select '1) 编码映射表' as check_item;
select * from dim_member_level order by level_rank;
select * from dim_pay_type order by pay_code;
select * from dim_order_status order by status_code;
select * from dim_channel order by channel_code;

-- 4.1 编码关联是否全部命中（应全为 0）
select '2) 编码未命中数（应全为 0）' as check_item;
select sum(if(level_code is null, 1, 0)) as level_null from stg_user_dim;
select sum(if(pay_code is null, 1, 0))   as pay_null,
       sum(if(status_code is null, 1, 0)) as status_null,
       sum(if(channel_code is null, 1, 0)) as channel_null
from stg_order_fact;

-- 4.2 order_timestamp 格式（应全部为标准 yyyy-MM-dd HH:mm:ss）
select '3) order_timestamp 非标准数（应为 0）' as check_item;
select count(*) as bad_cnt from stg_order_fact
where not order_timestamp rlike '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$';

select '3b) order_timestamp 样例' as check_item;
select order_id, order_date, order_time, order_timestamp, order_month, order_hour
from stg_order_fact order by order_timestamp limit 5;

-- 4.3 region 合并结果
select '4) region 合并结果（前 10）' as check_item;
select region, region_area, count(*) as cnt
from stg_user_dim group by region, region_area order by cnt desc limit 10;

select '4b) 大区分布' as check_item;
select region_area, count(*) as cnt from stg_user_dim group by region_area order by cnt desc;

select '4c) region 空值数（应为 0）' as check_item;
select sum(if(region is null or region = '', 1, 0)) as region_bad,
       sum(if(region_area = '其他', 1, 0))          as area_other
from stg_user_dim;

-- 4.4 订单月份分布
select '5) 订单月份分布' as check_item;
select order_month, count(*) as cnt, round(sum(pay_amount), 2) as gmv
from stg_order_fact group by order_month order by order_month;