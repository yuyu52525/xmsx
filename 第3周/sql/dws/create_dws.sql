-- ============================================================
-- 数据仓库 · DWS 汇总层建表脚本（第 3 周）
-- ------------------------------------------------------------
-- 库：ydsh_dws
-- 上游：ydsh_dwd（DWS 只读 DWD，不跨层读 ODS）
-- 存储：ORC + SNAPPY，与 DWD 保持一致
-- 分区：除 dws_sales_month 外，全部按 stat_month 动态分区
--       （12 个分区，日表按月裁剪，便于"只看某月"的报表场景）
--
-- 分区/分桶取舍说明：
--   DWS 是"预聚合"结果集，日表最大也只有 366×4≈1,464 行，
--   分桶（强制走 reduce）对这点数据量是纯负担，故一律不分桶；
--   只保留按月分区，让"按月份筛选"的报表能命中分区裁剪。
--
-- 注意：本环境 Hive 4 建的表是 EXTERNAL_TABLE 但 external.table.purge=TRUE，
--       DROP TABLE 会连数据文件一起删。重建请 create_dws.sql 后紧跟 load_dws.sql。
-- ============================================================

create database if not exists ydsh_dws;
use ydsh_dws;

set hive.exec.dynamic.partition = true;
set hive.exec.dynamic.partition.mode = nonstrict;
set hive.exec.max.dynamic.partitions = 1000;
set hive.exec.max.dynamic.partitions.pernode = 200;

-- ============================================================
-- 一、时间维度汇总：日 / 周 / 月
-- ============================================================

-- 1. 销售日汇总：粒度 = 日 × 渠道
--    服务"销售日报""渠道趋势"两类图表
drop table if exists dws_sales_day;
create table dws_sales_day (
  order_date        string comment '下单日期 yyyy-MM-dd',
  channel_code      string comment '渠道编码（外键 -> dim_channel）',
  channel_name      string comment '渠道名称：APP/PC官网/小程序/门店',
  is_online         int    comment '是否线上渠道（1 线上 / 0 线下）',
  week_key          string comment '自然周 yyyy-Wnn（周一为起点，年内第几周，2024 年为 W01~W53）',
  day_of_week       int    comment '星期几（周一=1）',
  is_weekend        int    comment '是否周末（1 是 / 0 否）',
  order_cnt         int    comment '订单数（全部状态）',
  valid_order_cnt   int    comment '有效订单数（is_valid_revenue=1）',
  gmv               double comment 'GMV = 当日该渠道全部订单实付金额合计',
  valid_gmv         double comment '有效 GMV = 计入营收订单的实付金额合计',
  discount_amount   double comment '优惠金额合计',
  buyer_cnt         int    comment '下单用户数（去重，非订单数）',
  item_qty          int    comment '销售件数（明细 quantity 合计，无明细订单记 0）',
  cancel_cnt        int    comment '已取消订单数',
  refund_cnt        int    comment '退款中订单数',
  aov               double comment '客单价 = gmv / order_cnt（元）'
)
partitioned by (stat_month string comment '统计月份 yyyy-MM（分区键，= 下单月份）')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 2. 销售周汇总：粒度 = 自然周 × 渠道
--    服务"周环比""周度经营看板"
drop table if exists dws_sales_week;
create table dws_sales_week (
  week_key          string comment '自然周 yyyy-Wnn',
  week_start        string comment '本周第一天（周一）yyyy-MM-dd',
  week_end          string comment '本周最后一天（周日）= week_start + 6 天',
  year              int    comment '周所在的年份（按周一所在年归属）',
  week_of_year      int    comment '年内第几周（1~53，按周一起点推导）',
  channel_code      string comment '渠道编码',
  channel_name      string comment '渠道名称',
  is_online         int    comment '是否线上渠道',
  order_cnt         int    comment '订单数（全部状态）',
  valid_order_cnt   int    comment '有效订单数',
  gmv               double comment 'GMV = 本周该渠道全部订单实付金额合计',
  valid_gmv         double comment '有效 GMV',
  discount_amount   double comment '优惠金额合计',
  buyer_cnt         int    comment '下单用户数（去重）',
  item_qty          int    comment '销售件数',
  cancel_cnt        int    comment '已取消订单数',
  refund_cnt        int    comment '退款中订单数',
  aov               double comment '客单价 = gmv / order_cnt（元）'
)
partitioned by (stat_month string comment '统计月份 yyyy-MM（= 本周第一天所在月）')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 3. 销售月汇总：粒度 = 月 × 渠道
--    数据量极小（12×4=48 行），不分区；服务"月度趋势""渠道占比"
drop table if exists dws_sales_month;
create table dws_sales_month (
  stat_month        string comment '统计月份 yyyy-MM',
  channel_code      string comment '渠道编码',
  channel_name      string comment '渠道名称',
  is_online         int    comment '是否线上渠道',
  order_cnt         int    comment '订单数（全部状态）',
  valid_order_cnt   int    comment '有效订单数',
  gmv               double comment 'GMV = 本月该渠道全部订单实付金额合计',
  valid_gmv         double comment '有效 GMV',
  discount_amount   double comment '优惠金额合计',
  buyer_cnt         int    comment '下单用户数（去重）',
  item_qty          int    comment '销售件数',
  cancel_cnt        int    comment '已取消订单数',
  refund_cnt        int    comment '退款中订单数',
  aov               double comment '客单价 = gmv / order_cnt（元）'
)
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 二、业务维度汇总：品类 / 门店 / 省份
-- ============================================================

-- 4. 品类月汇总：粒度 = 月 × 品类（一级类目）
--    口径：销售额取明细分摊金额 alloc_amount（不是 item_amount，见文档"金额三口径"）
drop table if exists dws_category_month;
create table dws_category_month (
  category          string comment '一级类目（来自 dim_product）',
  sales_amt         double comment '品类销售额（明细 alloc_amount 合计，与订单实付同口径）',
  item_qty          int    comment '品类销量（明细 quantity 合计）',
  order_cnt         int    comment '包含该类目商品的订单数（去重）',
  buyer_cnt         int    comment '购买该类目商品的用户数（去重）',
  sku_cnt           int    comment '有销量的 SKU 数',
  avg_item_price    double comment '件均价 = sales_amt / item_qty（元）',
  sales_share       double comment '品类销售额占比（0~1，同月 8 个类目合计为 1）'
)
partitioned by (stat_month string comment '统计月份 yyyy-MM')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 5. 门店月汇总：粒度 = 月 × 门店
--    含坪效（销售额 / 营业面积），服务"门店排名""坪效分析"
drop table if exists dws_store_month;
create table dws_store_month (
  store_id          string comment '门店编号',
  store_name        string comment '门店名称',
  province          string comment '所在省份',
  city              string comment '所在城市',
  region_area       string comment '所属大区',
  store_area        int    comment '营业面积（㎡）',
  order_cnt         int    comment '订单数（全部状态）',
  valid_order_cnt   int    comment '有效订单数',
  gmv               double comment 'GMV = 本月该门店全部订单实付金额合计',
  valid_gmv         double comment '有效 GMV',
  buyer_cnt         int    comment '下单用户数（去重）',
  aov               double comment '客单价 = gmv / order_cnt（元）',
  sales_per_sqm     double comment '坪效 = gmv / store_area（元/㎡）'
)
partitioned by (stat_month string comment '统计月份 yyyy-MM')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 6. 省份月汇总：粒度 = 月 × 用户所在省份
--    注意：省份取自 dim_user（用户归属地），不是 dim_store（门店所在地）
drop table if exists dws_province_month;
create table dws_province_month (
  province          string comment '用户所在省份',
  region_area       string comment '所属大区',
  order_cnt         int    comment '订单数（全部状态）',
  valid_order_cnt   int    comment '有效订单数',
  gmv               double comment 'GMV = 本月该省用户全部订单实付金额合计',
  valid_gmv         double comment '有效 GMV',
  buyer_cnt         int    comment '下单用户数（去重）',
  aov               double comment '客单价 = gmv / order_cnt（元）',
  arpu              double comment 'ARPU = gmv / buyer_cnt（元/人）',
  gmv_share         double comment '该省 GMV 占当月总 GMV 比例（0~1）'
)
partitioned by (stat_month string comment '统计月份 yyyy-MM')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 三、用户粒度汇总：日 × 用户 / 月 × 用户
-- ============================================================

-- 7. 用户日汇总：粒度 = 日 × 用户
--    解决"跨渠道去重"问题：日汇总表按渠道相加会把同一用户算多次，
--    DAU / 当日购买人数以本表为准
drop table if exists dws_user_day;
create table dws_user_day (
  order_date        string comment '下单日期 yyyy-MM-dd',
  user_id           string comment '用户编号',
  order_cnt         int    comment '当日订单数',
  gmv               double comment '当日实付金额合计',
  valid_gmv         double comment '当日有效 GMV',
  item_qty          int    comment '当日购买件数',
  is_first_order    int    comment '是否该用户的首单日（1 是 / 0 否）'
)
partitioned by (stat_month string comment '统计月份 yyyy-MM')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- 8. 用户月汇总：粒度 = 月 × 用户
--    服务复购率、用户价值分层（RFM 的 F/M 直接由本表汇总）
drop table if exists dws_user_month;
create table dws_user_month (
  user_id           string comment '用户编号',
  user_name         string comment '用户姓名',
  member_level      string comment '会员等级名称',
  level_rank        int    comment '会员等级序号（1~4）',
  province          string comment '用户所在省份',
  order_cnt         int    comment '本月订单数',
  gmv               double comment '本月实付金额合计',
  valid_gmv         double comment '本月有效 GMV',
  first_order_date  string comment '本月首单日期 yyyy-MM-dd',
  last_order_date   string comment '本月末单日期 yyyy-MM-dd',
  avg_order_amt     double comment '本月客单价 = gmv / order_cnt（元）',
  cum_gmv           double comment '截至本月累计消费（元，按用户跨月累加）',
  is_repurchase     int    comment '本月是否复购（本月订单数>=2 记 1）'
)
partitioned by (stat_month string comment '统计月份 yyyy-MM')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 四、行为汇总：日 × 行为类型
-- ============================================================

-- 9. 行为日汇总：粒度 = 日 × 行为类型
--    服务"转化漏斗""行为趋势"；不含购买金额（金额走订单链路）
drop table if exists dws_behavior_day;
create table dws_behavior_day (
  behavior_date     string comment '行为日期 yyyy-MM-dd',
  behavior_type     string comment '行为类型：浏览/加购/收藏/购买',
  pv_cnt            int    comment '行为次数（PV）',
  uv_cnt            int    comment '去重用户数（UV）',
  product_cnt       int    comment '涉及商品数（去重）',
  session_cnt       int    comment '会话数（去重 session_id）',
  pv_share          double comment '该行为 PV 占当日全部行为 PV 的比例（0~1）'
)
partitioned by (stat_month string comment '统计月份 yyyy-MM')
stored as orc
tblproperties ('orc.compress' = 'snappy');

-- ============================================================
-- 五、建表结果核对
-- ============================================================
show tables;
describe formatted dws_sales_day;
describe formatted dws_user_month;