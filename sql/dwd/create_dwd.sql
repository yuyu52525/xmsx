-- ============================================================
-- 数据仓库 · DWD 明细层建表脚本（星型模型）
-- ------------------------------------------------------------
-- 库：ydsh_dwd
-- 模型：以订单事实表 dwd_order 为中心，关联
--       dim_user / dim_product / dim_store / dim_date 四张维度表
-- 存储：ORC + SNAPPY；事实表按月份动态分区，订单事实表额外按 user_id 分 8 桶
-- 编码映射：会员等级 / 支付方式 / 订单状态 / 渠道 4 张微型维表（clean_split_merge.sql 已建）
-- ============================================================

create database if not exists ydsh_dwd;
use ydsh_dwd;

-- ============================================================
-- 一、维度表
-- ============================================================

-- 1. 用户维度
drop table if exists dim_user;
create table dim_user (
  user_id        string comment '用户编号（主键）',
  user_name      string comment '用户姓名',
  gender         string comment '性别：男/女/未知',
  age            int    comment '年龄',
  age_group      string comment '年龄段',
  city           string comment '城市',
  province       string comment '省份',
  region         string comment '省-市合并地区',
  region_area    string comment '七大区',
  register_date  string comment '注册日期 yyyy-MM-dd',
  level_code     string comment '会员等级编码（外键 -> dim_member_level）',
  member_level   string comment '会员等级名称',
  level_rank     int    comment '会员等级序号',
  level_imputed  int    comment '等级是否由缺失值补全',
  phone          string comment '手机号（11 位纯数字）',
  email          string comment '邮箱（允许为空）',
  email_missing  int    comment '邮箱缺失标记',
  age_filled     int    comment '年龄是否填充'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 2. 商品维度
drop table if exists dim_product;
create table dim_product (
  product_id        string comment '商品编号（主键）',
  product_name      string comment '商品名称',
  category          string comment '一级类目（已去空格）',
  sub_category      string comment '二级类目',
  brand             string comment '品牌',
  price             double comment '售价（异常值已按类目中位数修正）',
  price_fixed       int    comment '价格是否被修正',
  cost              double comment '成本价',
  stock             int    comment '库存',
  status            string comment '商品状态',
  launch_date       string comment '上架日期 yyyy-MM-dd',
  launch_date_filled int   comment '上架日期是否补全'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 3. 门店维度
drop table if exists dim_store;
create table dim_store (
  store_id    string comment '门店编号（主键）',
  store_name  string comment '门店名称',
  province    string comment '省份',
  city        string comment '城市',
  district    string comment '区县',
  address     string comment '详细地址',
  region      string comment '省-市合并地区',
  region_area string comment '七大区',
  open_date   string comment '开业日期 yyyy-MM-dd',
  area        int    comment '营业面积（㎡）',
  manager     string comment '店长'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 4. 时间维度（2023-01-01 ~ 2024-12-31，共 731 天）
drop table if exists dim_date;
create table dim_date (
  date_key     string comment '日期主键 yyyy-MM-dd',
  year         int    comment '年',
  quarter      int    comment '季度',
  month        int    comment '月',
  month_key    string comment '年月 yyyy-MM',
  day          int    comment '日',
  day_of_week  int    comment '星期几（周一=1）',
  weekday_name string comment '星期名称',
  is_weekend   int    comment '是否周末',
  week_of_year int    comment '年内第几周'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 二、事实表
-- ============================================================

-- 1. 订单事实表：粒度 = 一个订单一行
--    分区：order_month（按月，12 个分区，可分区裁剪）
--    分桶：按 user_id 分 8 桶（同一用户命中同一桶，便于用户级 JOIN / 抽样）
drop table if exists dwd_order;
create table dwd_order (
  order_id        string comment '订单编号（主键）',
  user_id         string comment '用户编号（外键 -> dim_user，分桶键）',
  store_id        string comment '门店编号（外键 -> dim_store）',
  order_date      string comment '下单日期 yyyy-MM-dd（外键 -> dim_date）',
  order_time      string comment '下单时间 HH:mm:ss',
  order_timestamp string comment '下单时间戳 yyyy-MM-dd HH:mm:ss',
  order_hour      int    comment '下单小时（0-23）',
  pay_amount      double comment '实付金额（度量）',
  discount_amount double comment '优惠金额（度量）',
  pay_code        string comment '支付方式编码（外键 -> dim_pay_type）',
  pay_name        string comment '支付方式名称',
  status_code     string comment '订单状态编码（外键 -> dim_order_status）',
  status_name     string comment '订单状态名称',
  is_paid         int    comment '是否已付款',
  is_valid_revenue int   comment '是否计入有效营收',
  channel_code    string comment '渠道编码（外键 -> dim_channel）',
  channel_name    string comment '渠道名称',
  is_online       int    comment '是否线上渠道'
)
partitioned by (order_month string comment '下单月份 yyyy-MM')
clustered by (user_id) into 8 buckets
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 2. 订单明细事实表：粒度 = 一个订单商品行
drop table if exists dwd_order_item;
create table dwd_order_item (
  item_id      string comment '明细编号（主键）',
  order_id     string comment '订单编号（外键 -> dwd_order）',
  user_id      string comment '用户编号（外键 -> dim_user）',
  product_id   string comment '商品编号（外键 -> dim_product）',
  store_id     string comment '门店编号（外键 -> dim_store）',
  order_date   string comment '下单日期（外键 -> dim_date）',
  quantity     int    comment '购买数量（度量）',
  unit_price   double comment '商品单价（度量）',
  discount     double comment '折扣率 0~1（度量）',
  item_amount  double comment '明细原值 = 数量×单价×(1-折扣)（度量）',
  alloc_amount double comment '按明细占比分摊后的实付金额（度量，可加总到订单实付）'
)
partitioned by (order_month string comment '下单月份 yyyy-MM')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 3. 用户行为事实表：粒度 = 一条行为日志
drop table if exists dwd_user_behavior;
create table dwd_user_behavior (
  behavior_id   string comment '行为编号（主键）',
  user_id       string comment '用户编号（外键 -> dim_user）',
  product_id    string comment '商品编号（外键 -> dim_product）',
  behavior_type string comment '行为类型：浏览/加购/收藏/购买',
  behavior_time string comment '行为时间 yyyy-MM-dd HH:mm:ss',
  behavior_date string comment '行为日期（外键 -> dim_date）',
  session_id    string comment '会话编号'
)
partitioned by (behavior_month string comment '行为月份 yyyy-MM')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 三、查看模型结构
-- ============================================================
show tables;
describe formatted dim_user;
describe formatted dwd_order;