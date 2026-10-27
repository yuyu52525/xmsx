-- ============================================================
-- 云购生活 · 数据仓库 ODS 贴源层建表脚本
-- 数据库：ydsh_ods
-- 说明：6 张表，字段与 CSV 严格对应，分隔符为英文逗号，跳过表头
-- ============================================================

create database if not exists ydsh_ods;
use ydsh_ods;

-- ------------------------------------------------------------
-- 1. 用户信息表
-- ------------------------------------------------------------
create table if not exists ods_user (
  user_id       string comment '用户编号',
  user_name     string comment '用户姓名',
  gender        string comment '性别（含异常值）',
  age           int    comment '年龄（含缺失/异常）',
  city          string comment '城市',
  province      string comment '省份',
  register_date string comment '注册日期（格式不一致）',
  member_level  string comment '会员等级（中英文混用）',
  phone         string comment '手机号（格式不一致）',
  email         string comment '邮箱（部分缺失）'
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- ------------------------------------------------------------
-- 2. 商品信息表
-- ------------------------------------------------------------
create table if not exists ods_product (
  product_id    string comment '商品编号',
  product_name  string comment '商品名称',
  category      string comment '一级类目',
  sub_category  string comment '二级类目',
  brand         string comment '品牌',
  price         double comment '售价（含负数/异常高价）',
  cost          double comment '成本价',
  stock         int    comment '库存数量',
  status        string comment '状态',
  launch_date   string comment '上架日期（部分缺失）'
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- ------------------------------------------------------------
-- 3. 门店信息表
-- ------------------------------------------------------------
create table if not exists ods_store (
  store_id      string comment '门店编号',
  store_name    string comment '门店名称',
  province      string comment '省份',
  city          string comment '城市',
  district      string comment '区县',
  address       string comment '详细地址',
  open_date     string comment '开业日期',
  area          int    comment '营业面积（㎡）',
  manager       string comment '店长姓名'
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- ------------------------------------------------------------
-- 4. 订单主表
-- ------------------------------------------------------------
create table if not exists ods_order (
  order_id        string comment '订单编号',
  user_id         string comment '用户编号',
  store_id        string comment '门店编号',
  order_date      string comment '下单日期（格式不一致）',
  order_time      string comment '下单时间',
  pay_amount      double comment '实付金额（含负数/异常）',
  discount_amount double comment '优惠金额',
  pay_type        string comment '支付方式（中英文混用）',
  order_status    string comment '订单状态（取值不规范）',
  channel         string comment '下单渠道（大小写混用）'
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- ------------------------------------------------------------
-- 5. 订单明细表
-- ------------------------------------------------------------
create table if not exists ods_order_item (
  item_id     string comment '明细编号',
  order_id    string comment '所属订单编号',
  product_id  string comment '商品编号',
  quantity    int    comment '购买数量（含 0/负数/超大值）',
  unit_price  double comment '商品单价',
  discount    double comment '折扣率（0~1）'
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');

-- ------------------------------------------------------------
-- 6. 用户行为日志表
-- ------------------------------------------------------------
create table if not exists ods_user_behavior (
  behavior_id   string comment '行为编号',
  user_id       string comment '用户编号',
  product_id    string comment '商品编号',
  behavior_type string comment '行为类型（中英文混用）',
  behavior_time string comment '行为发生时间（格式不一致）',
  session_id    string comment '会话编号'
)
row format delimited fields terminated by ','
tblproperties ('skip.header.line.count' = '1');
