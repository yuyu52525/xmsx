# NL2SQL 可查询表结构（自动抽取）

> 由 `第3周/py/schema_extract.py` 从 Hive metastore 实时抽取，
> 字段注释直接取 `describe` 的 comment，不做人工转写。

## ydsh_ads.ads_kpi_overview

- 说明：全周期核心 KPI 总览（单行）
- 行数：1

| 字段 | 类型 | 注释 |
|---|---|---|
| `stat_scope` | string | 统计范围说明 |
| `gmv` | double | GMV = 全部订单实付金额合计（元） |
| `valid_gmv` | double | 有效 GMV = 计入营收订单实付合计（元） |
| `order_cnt` | int | 订单量（去重订单号） |
| `valid_order_cnt` | int | 有效订单量 |
| `buyer_cnt` | int | 下单用户数（全周期去重） |
| `aov` | double | 客单价 = gmv / order_cnt（元） |
| `arpu` | double | ARPU = gmv / buyer_cnt（元/人） |
| `repurchase_rate` | double | 复购率 = 下单>=2次用户数 / 下单用户数（0~1） |
| `valid_revenue_rate` | double | 有效营收占比 = valid_gmv / gmv（0~1） |
| `cancel_rate` | double | 取消率 = 已取消订单数 / 订单量（0~1） |
| `refund_rate` | double | 退款中占比 = 退款中订单数 / 订单量（0~1） |
| `avg_order_items` | double | 件单价口径：平均每单件数 = 件数 / 订单量 |
| `calc_time` | string | 计算时间 |

## ydsh_ads.ads_kpi_month

- 说明：月度 KPI，含环比与同比
- 行数：12

| 字段 | 类型 | 注释 |
|---|---|---|
| `stat_month` | string | 统计月份 yyyy-MM |
| `gmv` | double | GMV（元） |
| `valid_gmv` | double | 有效 GMV（元） |
| `order_cnt` | int | 订单量 |
| `valid_order_cnt` | int | 有效订单量 |
| `buyer_cnt` | int | 下单用户数（当月去重） |
| `aov` | double | 客单价（元） |
| `arpu` | double | ARPU（元/人） |
| `repurchase_rate` | double | 当月复购率（当月下单>=2次用户 / 当月下单用户） |
| `gmv_mom` | double | GMV 环比（0.0521 = +5.21%；首月为 NULL） |
| `order_cnt_mom` | double | 订单量环比（首月为 NULL） |
| `gmv_yoy` | double | GMV 同比（本数据集仅 2024 一年，恒为 NULL，见报告说明） |
| `prev_month_gmv` | double | 上月 GMV（首月为 NULL） |

## ydsh_ads.ads_sales_daily

- 说明：销售日报（每日 GMV/订单/客单价/7日移动平均）
- 行数：366

| 字段 | 类型 | 注释 |
|---|---|---|
| `order_date` | string | 日期 yyyy-MM-dd |
| `gmv` | double | 当日 GMV（元） |
| `valid_gmv` | double | 当日有效 GMV（元） |
| `order_cnt` | int | 当日订单量 |
| `buyer_cnt` | int | 当日下单用户数（跨渠道去重） |
| `item_qty` | int | 当日销售件数 |
| `aov` | double | 当日客单价（元） |
| `gmv_ma7` | double | GMV 7 日移动平均（含当日；月初不足 7 天时按已有天数计算） |
| `gmv_dod` | double | GMV 日环比（首日为 NULL） |
| `month_cum_gmv` | double | 当月累计 GMV（含当日） |
| `is_weekend` | int | 是否周末（1 是 / 0 否） |

## ydsh_ads.ads_category_rank

- 说明：品类月度榜单与销售占比
- 行数：96

| 字段 | 类型 | 注释 |
|---|---|---|
| `stat_month` | string | 统计月份 yyyy-MM |
| `category` | string | 一级类目 |
| `sales_amt` | double | 品类销售额（明细分摊 alloc_amount 合计，元） |
| `item_qty` | int | 品类销量（件） |
| `order_cnt` | int | 包含该类目的订单数 |
| `buyer_cnt` | int | 购买该类目的用户数 |
| `avg_item_price` | double | 件均价（元/件） |
| `sales_share` | double | 品类销售额占当月比例（0~1） |
| `rank_no` | int | 当月销售额排名（1 为最高） |

## ydsh_ads.ads_province_sales

- 说明：省份月度销售与 ARPU
- 行数：180

| 字段 | 类型 | 注释 |
|---|---|---|
| `stat_month` | string | 统计月份 yyyy-MM |
| `province` | string | 用户所在省份 |
| `region_area` | string | 所属大区 |
| `gmv` | double | GMV（元） |
| `order_cnt` | int | 订单量 |
| `buyer_cnt` | int | 下单用户数 |
| `aov` | double | 客单价（元） |
| `arpu` | double | ARPU（元/人） |
| `gmv_share` | double | 该省 GMV 占当月比例（0~1） |
| `rank_no` | int | 当月 GMV 排名（1 为最高） |

## ydsh_ads.ads_store_rank

- 说明：门店月度榜单与坪效
- 行数：720

| 字段 | 类型 | 注释 |
|---|---|---|
| `stat_month` | string | 统计月份 yyyy-MM |
| `store_id` | string | 门店编号 |
| `store_name` | string | 门店名称 |
| `province` | string | 省份 |
| `city` | string | 城市 |
| `gmv` | double | GMV（元） |
| `order_cnt` | int | 订单量 |
| `buyer_cnt` | int | 下单用户数 |
| `aov` | double | 客单价（元） |
| `sales_per_sqm` | double | 坪效 = gmv / 营业面积（元/㎡） |
| `rank_no` | int | 当月 GMV 排名（1 为最高） |

## ydsh_ads.ads_channel_month

- 说明：渠道月度 GMV 与占比
- 行数：48

| 字段 | 类型 | 注释 |
|---|---|---|
| `stat_month` | string | 统计月份 yyyy-MM |
| `channel_code` | string | 渠道编码 |
| `channel_name` | string | 渠道名称 |
| `is_online` | int | 是否线上渠道 |
| `gmv` | double | GMV（元） |
| `order_cnt` | int | 订单量 |
| `buyer_cnt` | int | 下单用户数 |
| `aov` | double | 客单价（元） |
| `gmv_share` | double | 渠道 GMV 占当月比例（0~1） |
| `order_share` | double | 渠道订单量占当月比例（0~1） |

## ydsh_ads.ads_behavior_funnel

- 说明：月度行为漏斗（浏览/加购/收藏/购买）
- 行数：3

| 字段 | 类型 | 注释 |
|---|---|---|
| `stat_month` | string | 统计月份 yyyy-MM |
| `browse_pv` | int | 浏览行为次数 |
| `cart_pv` | int | 加购行为次数 |
| `fav_pv` | int | 收藏行为次数 |
| `buy_pv` | int | 购买行为次数 |
| `browse_pv_avg` | double | 日均浏览次数 = browse_pv / 当月天数 |
| `buy_pv_avg` | double | 日均购买次数 |
| `cart_rate` | double | 加购/浏览（0~1） |
| `fav_rate` | double | 收藏/浏览（0~1） |
| `buy_rate` | double | 购买/浏览（0~1） |

## ydsh_ads.ads_user_rfm

- 说明：用户 RFM 价值分层
- 行数：1,000

| 字段 | 类型 | 注释 |
|---|---|---|
| `user_id` | string | 用户编号 |
| `user_name` | string | 用户姓名 |
| `member_level` | string | 会员等级 |
| `last_order_date` | string | 最近一次下单日期 yyyy-MM-dd |
| `recency_days` | int | R：距最近一次下单的天数（以数据最大日期为基准） |
| `frequency` | int | F：全周期订单数 |
| `monetary` | double | M：全周期累计消费（元） |
| `r_score` | int | R 分（1~5，5 表示最近有购买） |
| `f_score` | int | F 分（1~5，5 表示下单最频繁） |
| `m_score` | int | M 分（1~5，5 表示消费最高） |
| `rfm_score` | string | RFM 三位组合分，如 \"543\" |
| `rfm_segment` | string | 客户分层：重要价值/重要保持/重要发展/重要挽留/一般价值/一般保持/一般发展/一般挽留 |

## ydsh_dwd.dim_user

- 说明：用户维度（性别/年龄/省市/会员等级）
- 行数：1,000

| 字段 | 类型 | 注释 |
|---|---|---|
| `user_id` | string | 用户编号（主键） |
| `user_name` | string | 用户姓名 |
| `gender` | string | 性别：男/女/未知 |
| `age` | int | 年龄 |
| `age_group` | string | 年龄段 |
| `city` | string | 城市 |
| `province` | string | 省份 |
| `region` | string | 省-市合并地区 |
| `region_area` | string | 七大区 |
| `register_date` | string | 注册日期 yyyy-MM-dd |
| `level_code` | string | 会员等级编码（外键 -> dim_member_level） |
| `member_level` | string | 会员等级名称 |
| `level_rank` | int | 会员等级序号 |
| `level_imputed` | int | 等级是否由缺失值补全 |
| `phone` | string | 手机号（11 位纯数字） |
| `email` | string | 邮箱（允许为空） |
| `email_missing` | int | 邮箱缺失标记 |
| `age_filled` | int | 年龄是否填充 |

## ydsh_dwd.dim_product

- 说明：商品维度（类目/品牌/价格）
- 行数：600

| 字段 | 类型 | 注释 |
|---|---|---|
| `product_id` | string | 商品编号（主键） |
| `product_name` | string | 商品名称 |
| `category` | string | 一级类目（已去空格） |
| `sub_category` | string | 二级类目 |
| `brand` | string | 品牌 |
| `price` | double | 售价（异常值已按类目中位数修正） |
| `price_fixed` | int | 价格是否被修正 |
| `cost` | double | 成本价 |
| `stock` | int | 库存 |
| `status` | string | 商品状态 |
| `launch_date` | string | 上架日期 yyyy-MM-dd |
| `launch_date_filled` | int | 上架日期是否补全 |

## ydsh_dwd.dim_store

- 说明：门店维度（省市/大区/面积）
- 行数：60

| 字段 | 类型 | 注释 |
|---|---|---|
| `store_id` | string | 门店编号（主键） |
| `store_name` | string | 门店名称 |
| `province` | string | 省份 |
| `city` | string | 城市 |
| `district` | string | 区县 |
| `address` | string | 详细地址 |
| `region` | string | 省-市合并地区 |
| `region_area` | string | 七大区 |
| `open_date` | string | 开业日期 yyyy-MM-dd |
| `area` | int | 营业面积（㎡） |
| `manager` | string | 店长 |

## ydsh_dwd.dim_date

- 说明：日期维度（年/季/月/周/是否周末）
- 行数：731

| 字段 | 类型 | 注释 |
|---|---|---|
| `date_key` | string | 日期主键 yyyy-MM-dd |
| `year` | int | 年 |
| `quarter` | int | 季度 |
| `month` | int | 月 |
| `month_key` | string | 年月 yyyy-MM |
| `day` | int | 日 |
| `day_of_week` | int | 星期几（周一=1） |
| `weekday_name` | string | 星期名称 |
| `is_weekend` | int | 是否周末 |
| `week_of_year` | int | 年内第几周 |
