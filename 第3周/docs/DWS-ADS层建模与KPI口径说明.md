# 云购生活 · DWS / ADS 层建模与 KPI 口径说明（第 3 周）

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0（第 3 周） |
| 依据 | 《第 3 周任务书》子任务 1：DWS / ADS 层建设与 KPI 指标计算 |
| 上游文档 | 《第 2 周 · 数仓架构设计文档》第七章"DWS / ADS 层预留设计" |
| 代码位置 | `第3周/sql/dws/`、`第3周/sql/ads/` |
| 运行证据 | `第3周/evidence/dws_create.txt`、`dws_load.txt`、`dws_verify.txt`、`ads_create.txt`、`ads_load.txt`、`ads_verify.txt`、`kpi_report.txt` |

---

## 一、本周在四层架构中的位置

第 2 周结束时，仓库里只有 ODS 与 DWD 两层；本周补齐 DWS 与 ADS，四层架构才真正闭环。

| 层 | 库 | 本次变化 | 表数量 |
|---|---|---|---|
| ODS 贴源层 | `ydsh_ods` | 不变 | 6 |
| DWD 明细层 | `ydsh_dwd` | 不变（作为 DWS 的唯一上游） | 25 |
| **DWS 汇总层** | **`ydsh_dws`** | **本周新建** | **9** |
| **ADS 应用层** | **`ydsh_ads`** | **本周新建** | **9** |

分层铁律（沿用第 2 周架构文档 1.2 节）：

- **DWS 只读 DWD**，不碰 ODS；
- **ADS 只读 DWS / DWD**，不碰 ODS、不碰 `stg_` 中间表；
- 每层只依赖上一层，跨层取数视为设计缺陷。

> 为什么这次强调"只读上一层"？因为第 2 周踩过一个坑：如果为了省事让 DWS 直接读 ODS 的原始 CSV 文本表，等于绕过了整个清洗链路，脏数据会重新回到指标里。分层不是形式，是**防回退**的机制。

---

## 二、DWS 汇总层设计

### 2.1 表清单（9 张）

| 表名 | 粒度 | 主要指标 | 上游 | 行数 | 分区 |
|---|---|---|---|---|---|
| `dws_sales_day` | 日 × 渠道 | GMV、有效 GMV、订单数、买家数、件数、客单价 | `dwd_order` + `dwd_order_item` | 1,464 | 12 |
| `dws_sales_week` | 自然周 × 渠道 | 同上 + 周起止日期 | 同上 | 208 | 12 |
| `dws_sales_month` | 月 × 渠道 | 同上 | 同上 | 48 | 不分区 |
| `dws_category_month` | 月 × 品类 | 销售额、销量、订单数、买家数、SKU 数、件均价、占比 | `dwd_order_item` + `dim_product` | 96 | 12 |
| `dws_store_month` | 月 × 门店 | GMV、订单数、客单价、**坪效** | `dwd_order` + `dim_store` | 720 | 12 |
| `dws_province_month` | 月 × 用户所在省 | GMV、ARPU、占比 | `dwd_order` + `dim_user` | 180 | 12 |
| `dws_user_day` | 日 × 用户 | 当日订单数、GMV、是否首单 | `dwd_order` | 14,100 | 12 |
| `dws_user_month` | 月 × 用户 | 月订单数、月 GMV、**累计消费**、复购标记 | `dwd_order` + `dim_user` | 8,448 | 12 |
| `dws_behavior_day` | 日 × 行为类型 | PV / UV / 商品数 / 会话数 / 占比 | `dwd_user_behavior` | 368 | 3 |

> 行为表只有 3 个分区，不是漏了 9 个——原始行为日志只覆盖 2024-10 ~ 2024-12 三个月，这是数据边界。

### 2.2 三个关键设计取舍

#### 取舍一：为什么日 / 周 / 月三张表并存，而不是只做日表再向上汇总？

日表 1,464 行、周表 208 行、月表 48 行，数据量小到"存三份"几乎没有成本；但**查询路径短了一层**：月报直接扫 `dws_sales_month`（48 行），不用在 1,464 行上再 `group by`。这是典型的"用存储换查询复杂度"。

更重要的是**可校验**：三张表都由 DWD 独立聚合而来，如果三者总额对不上，说明聚合逻辑有问题。实测三张表 GMV 合计完全相等：

```
by_day     36,116,687.06
by_week    36,116,687.06
by_month   36,116,687.06
```

（证据：`第3周/evidence/dws_verify.txt` 第 126–140 行）

#### 取舍二：为什么在 `dws_sales_day` 之外还要一张 `dws_user_day`？

这是本周**最容易做错、也最容易被忽略**的一点。

`dws_sales_day` 的粒度是"日 × 渠道"，按渠道分组时用的是 `count(distinct user_id)`，得到的是**当天该渠道**的买家数。但把 4 个渠道的买家数**直接相加**，会重复计算"同一天在 APP 和小程序都下过单"的用户。

实测差异：

| 算法 | 全年"日 × 渠道买家数"合计 |
|---|---|
| 各渠道 `buyer_cnt` 直接相加 | **14,328** |
| `dws_user_day` 按"日 × 用户"去重 | **14,100** |
| 差异 | **228 人次** |

差 228 人次的来源：全年有 **227 个"用户-日"跨了 2 个及以上渠道**（其中 1 个跨 3 个渠道，所以多算 2 人次，226×1 + 1×2 = 228）。

所以凡是"当日购买人数 / DAU"这类指标，**一律以 `dws_user_day` 为准**，`dws_sales_day.buyer_cnt` 只在"单渠道视角"下使用。`ads_sales_daily` 的 `buyer_cnt` 就是 join `dws_user_day` 得到的。

> 顺带澄清一个容易混淆的点：全周期去重用户数（1,000）是**跨 366 天**去重的结果，和上面的 14,328 / 14,100（"日 × 用户"人次）不是同一层聚合，两者不能直接比大小。

#### 取舍三：为什么 DWS 全部按月分区、却一张都不分桶？

第 2 周给 `dwd_order` 分了 8 桶，是因为它要按 `user_id` 高频 JOIN；DWS 是**预聚合结果**，最大的 `dws_user_day` 也只有 14,100 行。分桶会强制写入走 reduce，对这点数据量是纯负担，还会产生一堆小文件。

只保留按月分区，实测裁剪效果：

| 查询 | 扫描行数 |
|---|---|
| `where stat_month = '2024-12'` | **124** |
| 不带分区条件 | **1,464** |

扫描量下降 **91.5%**，与 DWD 层的 91.4% 基本一致（证据：`dws_verify.txt` 第 188–237 行）。

### 2.3 建表与装载脚本

| 脚本 | 作用 | 说明 |
|---|---|---|
| `第3周/sql/dws/create_dws.sql` | 9 张表 DDL | ORC + SNAPPY，全字段中文注释 |
| `第3周/sql/dws/load_dws.sql` | ETL 装载 | 含 2 张临时映射表（订单件数、日期→周） |
| `第3周/sql/dws/verify_dws.sql` | 10 组校验 | 行数 / 分区 / 口径回滚 / 占比闭合 / 分区裁剪 / 主键唯一性 |

**执行顺序（必须成对）**：

```powershell
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/dws/create_dws.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/dws/load_dws.sql
```

> ⚠️ 与 DWD 层同样的注意点：Hive 4 建出来的是 `EXTERNAL_TABLE`，但 `external.table.purge=TRUE`，**`DROP TABLE` 会连数据文件一起删**。所以 `create_dws.sql` 之后必须紧跟 `load_dws.sql`，中间不能停。

实测耗时：建表约 15 秒，装载约 270 秒（9 张表，Tez 逐条执行）。

### 2.4 校验结果

10 组校验全部通过（完整输出见 `dws_verify.txt`）：

| 校验项 | 期望 | 实测 | 结论 |
|---|---|---|---|
| 9 张表行数 | 见 2.1 表 | 1,464 / 208 / 48 / 96 / 720 / 180 / 14,100 / 8,448 / 368 | ✅ |
| 分区数 | 12（行为表 3） | 12 / 12 / 12 / 12 / 12 / 12 / 12 / 3 | ✅ |
| GMV 回滚 | 36,116,687.06 | 36,116,687.06 | ✅ |
| 有效 GMV 回滚 | 24,185,272.59 | 24,185,272.59 | ✅ |
| 订单量回滚 | 14,398 | 14,398 | ✅ |
| 买家数回滚 | 1,000 | 1,000 | ✅ |
| 日/周/月同源 | 三者相等 | 均 36,116,687.06 | ✅ |
| 品类汇总 = 明细分摊 | 35,833,305.06 | 35,833,305.06 | ✅ |
| 主键重复 | 0 | 0 | ✅ |
| 累计消费单调性 | 0 违反 | 0 | ✅ |

---

## 三、ADS 应用层设计

### 3.1 表清单（9 张）

设计原则：**一张表只服务一类图表，指标口径写死在表里**，下游 BI 直接取数，不做二次计算。

| 表名 | 粒度 | 服务的图表 | 行数 |
|---|---|---|---|
| `ads_kpi_overview` | 全周期单行 | 经营驾驶舱顶部数字卡 | 1 |
| `ads_kpi_month` | 月 | 月度趋势折线、指标卡 | 12 |
| `ads_sales_daily` | 日 | 日销售趋势 + 7 日移动平均 | 366 |
| `ads_category_rank` | 月 × 品类 | 品类 TopN 柱状图、占比饼图 | 96 |
| `ads_province_sales` | 月 × 省份 | 区域销售地图、ARPU 对比 | 180 |
| `ads_store_rank` | 月 × 门店 | 门店排名、坪效柱状图 | 720 |
| `ads_channel_month` | 月 × 渠道 | 渠道结构堆叠图 | 48 |
| `ads_behavior_funnel` | 月 | 浏览→加购→收藏→购买漏斗 | 3 |
| `ads_user_rfm` | 用户 | 用户价值分布、分层明细 | 1,000 |

### 3.2 为什么 ADS 能"不 JOIN 就能答"

这是本周设计上最省事、也最容易被质疑的一点：`ads_province_sales` 直接存了省份名，`ads_category_rank` 直接存了品类名，`ads_user_rfm` 直接存了会员等级——**维度名称在 DWS 阶段就已经贴好**，ADS 里没有任何需要 JOIN 的编码字段。

好处：

1. NL2SQL 不需要模型去猜 JOIN 关系（这是大模型生成 SQL 最常见的错误来源）；
2. BI 建数据集时不用配关联，拖字段就能出图；
3. 口径唯一——同一个"品类销售额"，全公司只有一种算法。

代价是维度变更时要回溯刷新 ADS。对 600 个 SKU、8 个类目这种稳定的维度，这个代价可以接受；如果类目天天变，就该改成"ADS 存编码 + 维表 JOIN"。

### 3.3 执行

```powershell
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/ads/create_ads.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/ads/load_ads.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/ads/verify_ads.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/ads/kpi_report.sql
```

实测：建表约 8 秒，装载 63.3 秒，校验约 40 秒。

---

## 四、KPI 口径（本周最核心的一节）

### 4.1 金额的三个口径——不统一就会算出三个 GMV

同一个订单金额，在数仓里有三种算法，**三者互不相等**：

| 口径 | 字段 | 合计（元） | 覆盖订单 | 适用场景 |
|---|---|---|---|---|
| 订单实付口径 | `dwd_order.pay_amount` | **36,116,687.06** | 14,398 | GMV、客单价、ARPU、省份/门店/渠道分析 |
| 明细分摊口径 | `dwd_order_item.alloc_amount` | **35,833,305.06** | 14,284 | 品类/商品维度分析（必须落到明细） |
| 明细原值口径 | `dwd_order_item.item_amount` | 402,816,786.63 | 14,284 | **不可用于任何金额指标** |

三个数字的差异来源必须说清楚，否则答辩时一定被追问：

1. **订单口径 vs 分摊口径差 283,382.65 元**：有 **114 张订单没有对应的明细行**（清洗二阶段删掉了全部明细，但订单主表保留）。这 114 单的实付合计恰好是 283,382.65 元，两项相加正好等于 36,116,687.06。
2. **明细原值是分摊口径的约 11.2 倍**：`item_amount = 数量 × 单价 × (1-折扣)`，而分摊口径是按"明细原值占订单原值的比例"把 `pay_amount` 摊回明细。实测单笔订单即可看出差异——订单 `O2024000001` 实付 4,374.46 元，其 4 行明细原值合计却是 52,836.35 元。**说明模拟数据里"商品单价"与"订单实付"不同源**，原值只能当权重用，不能当金额用。

> 结论（写进团队规范）：
> - 做**订单级**指标 → 用 `pay_amount`；
> - 做**品类/商品级**指标 → 用 `alloc_amount`；
> - `item_amount` **只作为分摊权重**，绝不进报表。
>
> 第 2 周"分摊闭合误差 0.65 元"的结论正是基于 `alloc_amount`，本周继续沿用，没有推翻。

### 4.2 指标定义与本周结果

| 指标 | 口径公式 | 本周结果 | 说明 |
|---|---|---|---|
| GMV | `sum(pay_amount)`（全部状态） | **36,116,687.06 元** | 含待支付/已取消/退款中 |
| 有效 GMV | `sum(pay_amount) where is_valid_revenue=1` | **24,185,272.59 元** | 已完成 + 已支付 |
| 有效营收占比 | 有效 GMV / GMV | **66.96%** | 与第 2 周一致 |
| 订单量 | `count(distinct order_id)` | **14,398** | 去重订单号 |
| 有效订单量 | `count(1) where is_valid_revenue=1` | 9,598 | |
| 下单用户数 | `count(distinct user_id)` | **1,000** | 全周期去重 |
| 客单价 AOV | GMV / 订单量 | **2,508.45 元** | 订单口径 |
| ARPU | GMV / 下单用户数 | **36,116.69 元** | 年人均，不是月人均 |
| 月均 ARPU | 月 GMV / 月下单用户 | 4,042.57 ~ 4,467.76 元 | 12 个月区间 |
| 复购率 | 下单≥2 次用户 / 下单用户 | **100%** | ⚠️ 见 4.3 陷阱一 |
| 月度复购率 | 当月下单≥2 次 / 当月下单用户 | 45.82% ~ 50.85% | 有区分度，建议用这个 |
| 取消率 | 已取消订单 / 订单量 | 13.87% | |
| 退款中占比 | 退款中订单 / 订单量 | 5.42% | |
| 件单价口径 | 件数 / 订单量 | 7.32 件/单 | |
| 品类销售占比 | 品类 `alloc_amount` / 当月总 `alloc_amount` | 11.12% ~ 14.91% | 8 个类目合计 = 1 |
| 坪效 | 门店 GMV / 营业面积 | 134.13 ~ 269.73 元/㎡/月 | 见 `ads_store_rank` |

### 4.3 四个必须写进报告的口径陷阱

#### 陷阱一：复购率恒为 100%，这个指标在本数据集上失效

`ads_kpi_overview.repurchase_rate = 1.0`，乍看像"用户忠诚度极高"，实际是数据特性：

```
每用户订单数：最小 4，最大 27，平均 14.4（1,000 人全部 ≥ 4 次）
```

2024 年只有 1,000 个用户、14,398 笔订单，平均每人 14.4 单——**不存在"只买一次"的用户**，所以"下单≥2 次用户占比"必然是 100%。

处理方式：口径不改（公式本身没错），但在报表上**改用月度复购率**（45.82%~50.85%），它才有区分度；同时在文档里注明"全周期复购率不适用于本数据集"。

#### 陷阱二：同比全为 NULL，不是算错，是没数据

`ads_kpi_month.gmv_yoy` 整列为 NULL。原因：数据集只有 2024-01-01 ~ 2024-12-31，没有 2023 年可比。`lag(gmv, 12)` 在 12 行上取不到前一年，返回 NULL。

处理方式：保留该列（口径是对的），文档里明确"需补 2023 年数据才能算"，**不用 0 或均值填充**——填充会造出一个假数字，比空着危险得多。

#### 陷阱三：漏斗"购买率 > 加购率"，说明这不是真漏斗

| 指标 | 2024 全年 |
|---|---|
| 浏览次数 | 34,160 |
| 加购次数 | 8,286（24.26%） |
| 收藏次数 | 5,585（16.35%） |
| 购买次数 | 11,969（**35.04%**） |

购买次数比加购次数还多——真实漏斗里不可能出现。根因在第 2 周已查明：`dwd_user_behavior` 是**并列的行为事件日志**，不是"同一会话内的步骤序列"。抽查会话可见同一 `session_id` 下只有"浏览,购买"两条事件，没有加购环节。

处理方式：`ads_behavior_funnel` 保留 PV 绝对值与"相对浏览的比例"，但**不称其为"转化率"**；报表标题写"行为量分布"，不写"转化漏斗"。

#### 陷阱四：占比合计是 1.000001 而不是 1

`dws_category_month.sales_share` 保留 6 位小数，8 个类目相加会出现 ±1e-6 的舍入误差（实测 0.999998 ~ 1.000001）。

处理方式：这是**正常舍入**，不是 bug。校验时用 `abs(sum - 1) < 1e-5` 判断，不要用 `= 1`。如果报表要求严格等于 100%，应在展示层做"最大余数法"配平，而不是改存储层精度。

---

## 五、本周踩到的坑（已解决，记在这里备查）

| # | 现象 | 根因 | 解决 |
|---|---|---|---|
| 1 | 9 路 `union all` 查询报 `Counters limit exceeded: Too many counters: 121 max=120` | 每个 `union` 分支各起一个 Tez DAG，计数器累加超过 120 上限 | 拆成"一条语句一张表"；顺带实测 `set tez.counters.max` / `tez.counters.limit` **均无效**（该 Tez 版本在 AM 侧固定 120） |
| 2 | `dws_sales_week` 里 `2024-W01` 的 `week_start`/`week_end` 变成 2024-01-01 ~ 2024-12-31 | `dim_date.week_of_year` 把 2024-12-30/31 也标成"第 1 周"，与 1 月第 1 周撞键 | 不再用 `dim_date.week_of_year`，改为自己推导：周一 = `date_sub(日期, 星期几-1)`，年内第几周 = `(周一 - 当年1月1日)/7 + 1` |
| 3 | `create_ads.sql` 里中文别名报 `cannot recognize input near 'as'` | Hive 标识符只认 `[a-zA-Z_][a-zA-Z0-9_]*`，中文别名必须加反引号 | 全部改成 `` as `统计范围` `` |
| 4 | GMV 明细行显示 `28757.559999999998` | double 二进制表示误差 | 落库时统一 `round(sum(...), 2)`，展示时 `cast(... as decimal(18,2))`（第 1 周老坑，本周在 DWS 层复发） |
| 5 | 动态分区写入报"分区列不在末尾" | `insert overwrite ... partition (stat_month)` 要求分区列表达式是 select 列表**最后一个** | 调整字段顺序，把 `stat_month` 放最后 |

---

## 六、可复现执行顺序（新环境从零跑一遍）

```powershell
# 0. 起容器
cd D:\xiangmushixun-bde
docker compose up -d

# 1. 确认 DWD 就绪（第 2 周产物）
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 --silent=true `
  --outputformat=tsv2 -e "select count(1) from ydsh_dwd.dwd_order;"   # 期望 14398

# 2. 建 DWS + 装载 + 校验
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/dws/create_dws.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/dws/load_dws.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/dws/verify_dws.sql

# 3. 建 ADS + 装载 + 校验 + 出 KPI 报表
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/ads/create_ads.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/ads/load_ads.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/ads/verify_ads.sql
docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /repo/第3周/sql/ads/kpi_report.sql
```

> 前提：`docker-compose.yml` 已挂载 `./第3周:/repo/第3周:ro`。若挂载后容器已存在，需要 `docker compose up -d` 重建 hive-server（数据在 bind mount，不受影响）。