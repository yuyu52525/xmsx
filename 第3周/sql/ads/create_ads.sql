-- ============================================================
-- 数据仓库 · ADS 应用层建表脚本（第 3 周）
-- ------------------------------------------------------------
-- 库：ydsh_ads
-- 上游：ydsh_dws（ADS 只读 DWS / DWD，不跨层读 ODS）
-- 设计原则：一张表只服务一类图表，指标口径写死在表里，
--           下游 BI（Superset / 自研看板）直接取数，不再做二次计算。
-- 存储：ORC + SNAPPY
-- 分区：ADS 表数据量都很小（最大 366 行），不分区、不分桶；
--       分区开销在这里没有收益，反而让 BI 取数多一层 where。
-- ============================================================

create database if not exists ydsh_ads;
use ydsh_ads;

-- ============================================================
-- 一、核心 KPI：总览 + 月度
-- ============================================================

-- 1. KPI 总览（单行）：全周期核心指标，服务"经营驾驶舱"顶部数字卡
drop table if exists ads_kpi_overview;
create table ads_kpi_overview (
  stat_scope          string comment '统计范围说明',
  gmv                 double comment 'GMV = 全部订单实付金额合计（元）',
  valid_gmv           double comment '有效 GMV = 计入营收订单实付合计（元）',
  order_cnt           int    comment '订单量（去重订单号）',
  valid_order_cnt     int    comment '有效订单量',
  buyer_cnt           int    comment '下单用户数（全周期去重）',
  aov                 double comment '客单价 = gmv / order_cnt（元）',
  arpu                double comment 'ARPU = gmv / buyer_cnt（元/人）',
  repurchase_rate     double comment '复购率 = 下单>=2次用户数 / 下单用户数（0~1）',
  valid_revenue_rate  double comment '有效营收占比 = valid_gmv / gmv（0~1）',
  cancel_rate         double comment '取消率 = 已取消订单数 / 订单量（0~1）',
  refund_rate         double comment '退款中占比 = 退款中订单数 / 订单量（0~1）',
  avg_order_items     double comment '件单价口径：平均每单件数 = 件数 / 订单量',
  calc_time           string comment '计算时间'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 2. 月度 KPI（含环比 / 同比）：服务"月度趋势"折线图与指标卡
drop table if exists ads_kpi_month;
create table ads_kpi_month (
  stat_month          string comment '统计月份 yyyy-MM',
  gmv                 double comment 'GMV（元）',
  valid_gmv           double comment '有效 GMV（元）',
  order_cnt           int    comment '订单量',
  valid_order_cnt     int    comment '有效订单量',
  buyer_cnt           int    comment '下单用户数（当月去重）',
  aov                 double comment '客单价（元）',
  arpu                double comment 'ARPU（元/人）',
  repurchase_rate     double comment '当月复购率（当月下单>=2次用户 / 当月下单用户）',
  gmv_mom             double comment 'GMV 环比（0.0521 = +5.21%；首月为 NULL）',
  order_cnt_mom       double comment '订单量环比（首月为 NULL）',
  gmv_yoy             double comment 'GMV 同比（本数据集仅 2024 一年，恒为 NULL，见报告说明）',
  prev_month_gmv      double comment '上月 GMV（首月为 NULL）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 二、销售日报：服务"日销售趋势 + 7 日移动平均"
-- ============================================================

drop table if exists ads_sales_daily;
create table ads_sales_daily (
  order_date          string comment '日期 yyyy-MM-dd',
  gmv                 double comment '当日 GMV（元）',
  valid_gmv           double comment '当日有效 GMV（元）',
  order_cnt           int    comment '当日订单量',
  buyer_cnt           int    comment '当日下单用户数（跨渠道去重）',
  item_qty            int    comment '当日销售件数',
  aov                 double comment '当日客单价（元）',
  gmv_ma7             double comment 'GMV 7 日移动平均（含当日；月初不足 7 天时按已有天数计算）',
  gmv_dod             double comment 'GMV 日环比（首日为 NULL）',
  month_cum_gmv       double comment '当月累计 GMV（含当日）',
  is_weekend          int    comment '是否周末（1 是 / 0 否）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 三、维度排名：品类 TopN / 省份 / 门店 / 渠道
-- ============================================================

-- 3. 品类月榜：服务"品类 TopN 柱状图""品类销售占比饼图"
drop table if exists ads_category_rank;
create table ads_category_rank (
  stat_month          string comment '统计月份 yyyy-MM',
  category            string comment '一级类目',
  sales_amt           double comment '品类销售额（明细分摊 alloc_amount 合计，元）',
  item_qty            int    comment '品类销量（件）',
  order_cnt           int    comment '包含该类目的订单数',
  buyer_cnt           int    comment '购买该类目的用户数',
  avg_item_price      double comment '件均价（元/件）',
  sales_share         double comment '品类销售额占当月比例（0~1）',
  rank_no             int    comment '当月销售额排名（1 为最高）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 4. 省份月榜：服务"区域销售地图""省份 ARPU 对比"
drop table if exists ads_province_sales;
create table ads_province_sales (
  stat_month          string comment '统计月份 yyyy-MM',
  province            string comment '用户所在省份',
  region_area         string comment '所属大区',
  gmv                 double comment 'GMV（元）',
  order_cnt           int    comment '订单量',
  buyer_cnt           int    comment '下单用户数',
  aov                 double comment '客单价（元）',
  arpu                double comment 'ARPU（元/人）',
  gmv_share           double comment '该省 GMV 占当月比例（0~1）',
  rank_no             int    comment '当月 GMV 排名（1 为最高）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 5. 门店月榜：服务"门店排名 + 坪效"柱状图
drop table if exists ads_store_rank;
create table ads_store_rank (
  stat_month          string comment '统计月份 yyyy-MM',
  store_id            string comment '门店编号',
  store_name          string comment '门店名称',
  province            string comment '省份',
  city                string comment '城市',
  gmv                 double comment 'GMV（元）',
  order_cnt           int    comment '订单量',
  buyer_cnt           int    comment '下单用户数',
  aov                 double comment '客单价（元）',
  sales_per_sqm       double comment '坪效 = gmv / 营业面积（元/㎡）',
  rank_no             int    comment '当月 GMV 排名（1 为最高）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 6. 渠道月占比：服务"渠道结构"堆叠图 / 占比环形图
drop table if exists ads_channel_month;
create table ads_channel_month (
  stat_month          string comment '统计月份 yyyy-MM',
  channel_code        string comment '渠道编码',
  channel_name        string comment '渠道名称',
  is_online           int    comment '是否线上渠道',
  gmv                 double comment 'GMV（元）',
  order_cnt           int    comment '订单量',
  buyer_cnt           int    comment '下单用户数',
  aov                 double comment '客单价（元）',
  gmv_share           double comment '渠道 GMV 占当月比例（0~1）',
  order_share         double comment '渠道订单量占当月比例（0~1）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 四、用户价值分层（RFM）与行为漏斗
-- ============================================================

-- 7. 用户 RFM 分层：服务"用户价值分布"柱状图 / 分层明细表
drop table if exists ads_user_rfm;
create table ads_user_rfm (
  user_id             string comment '用户编号',
  user_name           string comment '用户姓名',
  member_level        string comment '会员等级',
  last_order_date     string comment '最近一次下单日期 yyyy-MM-dd',
  recency_days        int    comment 'R：距最近一次下单的天数（以数据最大日期为基准）',
  frequency           int    comment 'F：全周期订单数',
  monetary            double comment 'M：全周期累计消费（元）',
  r_score             int    comment 'R 分（1~5，5 表示最近有购买）',
  f_score             int    comment 'F 分（1~5，5 表示下单最频繁）',
  m_score             int    comment 'M 分（1~5，5 表示消费最高）',
  rfm_score           string comment 'RFM 三位组合分，如 "543"',
  rfm_segment         string comment '客户分层：重要价值/重要保持/重要发展/重要挽留/一般价值/一般保持/一般发展/一般挽留'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 8. 行为漏斗（月）：服务"浏览→加购→收藏→购买"漏斗图
drop table if exists ads_behavior_funnel;
create table ads_behavior_funnel (
  stat_month          string comment '统计月份 yyyy-MM',
  browse_pv           int    comment '浏览行为次数',
  cart_pv             int    comment '加购行为次数',
  fav_pv              int    comment '收藏行为次数',
  buy_pv              int    comment '购买行为次数',
  browse_pv_avg       double comment '日均浏览次数 = browse_pv / 当月天数',
  buy_pv_avg          double comment '日均购买次数',
  cart_rate           double comment '加购/浏览（0~1）',
  fav_rate            double comment '收藏/浏览（0~1）',
  buy_rate            double comment '购买/浏览（0~1）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 五、建表结果核对
-- ============================================================
show tables;