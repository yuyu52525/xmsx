-- ============================================================
-- 数据清洗（一）缺失值处理
-- 策略：
--   ods_user.age           -> 用有效年龄（1~120）的均值填充，异常值一并修正
--   ods_user.email         -> 保留空值，新增 email_missing 标记位
--   ods_product.launch_date-> 缺失补全为全表最早上架日期，新增 filled 标记
-- 输出：dwd_user、dwd_product
-- ============================================================
use ydsh_ods;

-- ------------------------------------------------------------
-- 1. 用户表：年龄均值填充 + 邮箱缺失标记
-- ------------------------------------------------------------
drop table if exists dwd_user;

create table dwd_user as
select
  user_id,
  user_name,
  gender,
  cast(round(coalesce(valid_age, avg_valid_age)) as int) as age,
  city,
  province,
  register_date,
  member_level,
  phone,
  email,
  case when email is null or email = '' then 1 else 0 end as email_missing,
  case when valid_age is null and age is not null then 1
       when age is null then 1 else 0 end            as age_filled
from (
  select
    t.*,
    case when age between 1 and 120 then age else null end as valid_age,
    avg(case when age between 1 and 120 then age else null end) over () as avg_valid_age
  from ods_user t
) s;

-- ------------------------------------------------------------
-- 2. 商品表：上架日期缺失补全
-- ------------------------------------------------------------
drop table if exists dwd_product;

create table dwd_product as
select
  product_id, product_name, category, sub_category, brand,
  price, cost, stock, status,
  nvl(nullif(trim(launch_date), ''), min_date) as launch_date,
  case when launch_date is null or trim(launch_date) = '' then 1 else 0 end as launch_date_filled
from (
  select p.*, min(nullif(trim(launch_date), '')) over () as min_date
  from ods_product p
) t;

-- ------------------------------------------------------------
-- 3. 校验
-- ------------------------------------------------------------
select 'dwd_user' as tbl, count(*) as cnt,
       sum(if(age is null,1,0))  as age_null,
       sum(if(age < 0 or age > 120,1,0)) as age_abnormal,
       sum(if(email_missing = 1,1,0)) as email_missing_cnt
from dwd_user;

select 'dwd_product' as tbl, count(*) as cnt,
       sum(if(launch_date is null,1,0)) as launch_null,
       sum(launch_date_filled) as filled_cnt
from dwd_product;
