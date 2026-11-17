-- ============================================================
-- 数据仓库 · 第 4 周 ADS 增量建表脚本
-- ------------------------------------------------------------
-- 库：ydsh_ads（在第 3 周 9 张 ADS 表基础上新增 2 张）
-- 目的：补齐第 4 周可视化交付物的两个数据缺口
--   缺口 ①  支付方式占比饼图：原 ADS 无任何按支付方式汇总的表
--   缺口 ②  时段 × 品类热力图：原 ADS / DWS 均无小时粒度
-- 上游：ydsh_dwd.dwd_order / dwd_order_item / dim_product
--       （ADS 允许读 DWD 明细：这两张表是"小时 × 维度"的细粒度汇总，
--         DWS 层没有对应粒度的现成表，硬从 DWS 拼会失真）
-- 存储：ORC + SNAPPY，不分区、不分桶（表最大 192 行）
-- 金额口径：见各表字段注释，两张表口径不同，不可相加
-- ============================================================

create database if not exists ydsh_ads;
use ydsh_ads;

-- ============================================================
-- 一、ads_pay_type_month —— 支付方式占比饼图数据源
-- ------------------------------------------------------------
-- 粒度：stat_month × pay_code（12 个月 × 4 种支付方式 = 48 行）
-- 口径：订单口径 pay_amount（与 GMV 36,116,687.06 一致）
-- 用途：支付方式占比饼图 / 支付方式月度趋势 / 支付结构明细表
-- 校验：select sum(gmv) from ads_pay_type_month 应等于 36,116,687.06
-- ============================================================
drop table if exists ads_pay_type_month;
create table ads_pay_type_month (
  stat_month     string comment '统计月份 yyyy-MM',
  pay_code       string comment '支付方式编码（外键 -> dim_pay_type）',
  pay_name       string comment '支付方式名称：微信支付/支付宝/银行卡/货到付款',
  order_cnt      int    comment '该支付方式订单量',
  buyer_cnt      int    comment '该支付方式下单用户数（当月去重）',
  gmv            double comment '该支付方式 GMV（订单口径 pay_amount 合计，元）',
  valid_gmv      double comment '该支付方式有效 GMV（元）',
  aov            double comment '该支付方式客单价 = gmv / order_cnt（元）',
  gmv_share      double comment '该支付方式 GMV 占当月比例（0~1）',
  order_share    double comment '该支付方式订单量占当月比例（0~1）',
  rank_no        int    comment '当月 GMV 排名（1 为最高）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 二、ads_hour_category —— 时段 × 品类热力图数据源
-- ------------------------------------------------------------
-- 粒度：order_hour × category（24 小时 × 8 个一级类目 = 192 行）
-- 口径：明细分摊口径 alloc_amount（与 ads_category_rank 一致，
--       合计 35,833,305.06；与订单口径差额 283,382.65 元来自 114 张无明细订单）
-- 用途：时段 × 品类热力图 / 品类时段偏好分析
-- 注意：小时取自订单（dwd_order.order_hour），品类取自商品维度
--       （dwd_order_item -> dim_product.category），两者通过 order_id 关联；
--       一件商品属于一个订单，故小时归属唯一，不存在拆单歧义。
-- ============================================================
drop table if exists ads_hour_category;
create table ads_hour_category (
  hour_of_day            int    comment '下单小时（0~23，整数，不是 HH 字符串）',
  category               string comment '一级类目（8 个：运动户外/数码家电/…）',
  order_cnt              int    comment '该时段该品类订单数（去重订单号）',
  item_qty               int    comment '该时段该品类销售件数',
  buyer_cnt              int    comment '该时段该品类下单用户数（全年去重）',
  sales_amt              double comment '销售额（明细分摊 alloc_amount 合计，元）',
  avg_item_price         double comment '件均价 = sales_amt / item_qty（元/件）',
  hour_share_of_category double comment '该时段销售额占该品类全年比例（0~1），用于看品类自己的时段曲线',
  category_share_of_hour double comment '该品类销售额占该时段全品类比例（0~1），用于看时段内的结构',
  category_order         int    comment '品类全年销售额排名（1 为最高），供图表按业务量排序 Y 轴'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 三、建表结果核对
-- ============================================================
show tables;
describe ads_pay_type_month;
describe ads_hour_category;