# 第 4 周 AI 协同日志

> 项目：云购生活数仓 · 第 4 周（可视化实现 + Docker 部署）
> 协作周期：2026-11-17
> 说明：本周 AI 的参与度比前几周都高（大量基础设施代码由 AI 起草），但**几乎每一处都需要人工核对**——
> 因为第 4 周的错误不再表现为"数字算错"，而是"服务起不来""图表空白""口径悄悄错"，
> 这类问题不看日志、不做对照实验根本发现不了。

---

## 一、使用的 AI 工具 / 模型

| 项 | 内容 |
|---|---|
| 编码助手 | DeepSeek Harness（Agent 形态，可读写文件、执行命令、查网页） |
| 业务侧大模型 | 智谱 GLM-4-Flash（`glm-4-flash-250414`，免费档）——NL2SQL 与 Streamlit 问答使用 |
| 模型抽象 | `llm_client.py` 统一 `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL`，可切 DeepSeek / 硅基流动 / 本地 Ollama |
| 用量记录 | 每次调用写 `第4周/evidence/llm_usage.log`；一次 NL2SQL ≈ 3.5k tokens |

---

## 二、AI 协同记录表

| 序号 | 提问 / 任务描述 | AI 产出摘要 | 人工修改与验证 | 是否采纳 |
|---|---|---|---|---|
| 1 | 用 compose 加 Superset 服务，并自动建好 8 个数据集、6 个图表、1 个仪表板 | 给出 Superset Dockerfile（补 pyhive 四件套）、`superset_config.py`、`bootstrap.py`（REST API 全自动建） | 建数据源时一路报 422。查 Superset 日志才发现真因：`ParseException: cannot recognize input near 'SHOW' 'CATALOGS'` —— Hive 引擎规格继承了 Presto 的实现，建连接时会探测多目录，Hive 4.0.0 不认这条语法。AI 首选方案是在 `superset_config.py` 顶层 patch，实测报 `Working outside of application context`；改为 `FLASK_APP_MUTATOR`（app context 内执行）才真正生效 | 是（经两轮修正） |
| 2 | ClickHouse 容器持续报 `filesystem error: in rename: Permission denied`，数据一条都写不进去 | AI 最初按常规给了 `./data/clickhouse:/var/lib/clickhouse` 绑定挂载 | 我要求先看 CH 自己的报错原文，确认是 rename 分区目录失败；改为命名卷 `ydsh_clickhouse_data` 后一次通过。这是 Windows 下 Docker 的已知限制，AI 第一版方案照搬了 Linux 习惯 | 是（采纳修改后版本） |
| 3 | `docker compose up -d` 后 Superset 一直重启，日志只有 `Username [admin]:` | AI 在 compose 里写的 `superset fab create-admin --username ...` 被 `/bin/sh -c` 拆参数，退化成交互式提问，容器永远起不来 | 我要求把建管理员搬到 Python 里（`create_admin.py`，在 app context 调 FAB 接口）；顺带发现 `superset fab list-users` 为空，证明确实没建成。改完后日志出现"已创建管理员" | 是 |
| 4 | 仪表板 6 个位置全显示"没有找到相关图表的组件，是否已经删除" | AI 只把 chartId 写进了 `position_json`，没意识到图表与仪表板还有一张关联表 | 我用 API 查 `dashboard.charts` 发现是空数组；试 `PUT {"slices": [...]}` 返回 `Unknown field.`；最终用模型层写 `dashboard_slices` 解决（`link_dashboard_charts`）。同批还修了 `query_context` 缺失导致的 `Chart has no query context saved` | 是 |
| 5 | NL2SQL 问"2024 年 12 月各支付方式占比"，结果微信只有 2.43%，四个数加起来 9.4% | 提示词里 AI 写了个"占比"示例，分母写死成全年 GMV 常数 `36116687.06`；模型照抄了 | 我核对分子分母时间范围不一致（分子单月、分母全年），要求把示例改成 `sum(gmv) / sum(sum(gmv)) over ()`，并加硬约束"分母必须与问题限定的时间范围一致"。修复后 28.15/25.92/23.11/22.82，合计 100% | 是（示例被推翻重写） |
| 6 | 时段 × 品类热力图配色一出来就有深浅梯度，能不能写"夜间与午间双高峰"？ | AI 顺着图的观感给了"双高峰"的解读方向 | 我做了两个检验：卡方 χ²=62.74（df=23，临界值 35.17）虽拒绝均匀，但效应量极小（每小时 1,150~1,404 单，极差 19.75%）；再查 8 个品类的峰值时段，分别是 0/4/14/18/19 点，互不一致。结论改为"随机噪声，不能支撑业务结论"，并写进文档第七章 | 否（推翻，改写为技术验证结论） |
| 7 | Superset 门店 TopN 排行表第一位 GMV 1,321,107.24，看着偏高 | AI 按 `store_name` 分组聚合 | 我查 `dim_store` 发现同名不同店：60 个 `store_id` 只有 52 个名称，`云购生活·北京二店` 对应 S029(128㎡) 与 S039(780㎡) 两家。改为按 `store_id + store_name` 分组，同时把大屏排行条与接口一起改掉 | 是（口径修正） |
| 8 | 品类名次字段排出来是 1/25/49/73，不是 1~8 | AI 用了 `rank() over (order by cat_total desc)` | 我指出表的一行是"小时×品类"，同一品类 24 行合计相同会让 `rank()` 跳号，要求换 `dense_rank()`。重跑后 1~8，且 `category_order` 能正确给热力图排 Y 轴 | 是 |
| 9 | 压测 D2 组"预聚合 vs 现算"跑出来 3,111,746.74 与 875,880.76 差 3.5 倍，是不是预聚合把数算多了？ | AI 写的两条 SQL 其实不是一个口径：预聚合那条没带 `pay_code='P2'` | 我要求两条 SQL 必须同口径（都是 2024-12 微信支付），改完重跑：1.13s vs 3.25s，**结果都是 875,880.76**，差距才代表真实性能差 | 是（重跑） |
| 10 | ECharts 地图用哪个省名？ | AI 提醒两套命名不一致：我们数据是 `陕西省`（带省全称），Superset 内置中国地图是拼音 `Shaanxi`；同时确认 ECharts 侧用的 DataV GeoJSON 也是中文全称 | 我据此做了两套映射：Superset 用虚拟数据集 `case when` 转拼音，ECharts 直接对齐中文全称。两边都验证了 15 个省份能着色 | 是（提前避坑） |

> 共 10 条，其中第 1、2、3、4、5、6、7、9 条都属于**AI 先给了错的东西，人工发现后推翻或重做**。
> 本周的一个体会：基础设施类错误的"错误信息"和"真实原因"往往隔了几层（422 → 400 → ParseException → 继承关系），不追到最里层就会一直在外层打补丁。

---

## 三、AI 产出成果清单

**由 AI 生成、我核对后采纳的内容**

- `第4周/sql/ads/`：2 张新 ADS 表的建表、装载、29 条校验 SQL
- `第4周/py/`：`hive_client.py`、`api_server.py`（FastAPI 10 个接口）、`streamlit_app.py`、`ch_client.py`、`sql_runner.py`、`export_to_clickhouse.py`、`export_to_mysql.py`、`screenshot.py`、`ui_check.py`、`md2docx.py`
- `第4周/web/`：ECharts 大屏（HTML/CSS/JS 共 ~1,000 行，含 7 类图表与 scale 自适应）
- `第4周/docker/`：Superset 镜像与 `bootstrap.py`（约 500 行 API 编排）、应用镜像
- `docker-compose.yml`：8 服务编排 + healthcheck + 密钥注入
- `第4周/stress/stress_test.py`：4 组压测实验
- 5 篇文档的初稿结构

**由我人工完成的内容**

- 所有口径判断：两张新表用哪个金额口径、支付表用订单口径而热力表用明细口径、两张表不可相加
- 全部"数字必须能指回字段"的核对（支付表 GMV = KPI GMV、热力表 = 品类榜、抽样回 DWD 复算）
- 三个负结果的定性：时段热力图是噪声、分桶 join 无收益、模型/缓存的作用边界
- 门店同名问题的发现与唯一键决策
- 交付物清单与任务书逐条对照、提交包组织、Git 提交策略
- 部署验收的 11 项清单，以及现场演示流程设计（先 down 再 up 才有"一键部署"的效果）

**人机协作完成的内容**

- Superset 自动化：AI 写 API 编排，我负责"每一层报错都追到根因"，四个坑全部是追日志追出来的
- 压测：AI 写脚本，我要求把 D2 改成同口径、并增加"Hive vs ClickHouse"对照，才有了可引用的相对倍数
- 文档：AI 起草，我补业务判断、负结果与自我批评

---

## 四、问题与解决（按代价排序）

### 4.1 最贵的问题：Superset 连 Hive 的 422

**表象**：`Database could not be created.`
**排查路径**（4 层）：

1. 422 只说"创建失败"，没有细节 → 开 `docker compose logs -f superset`，看到 `DatabaseCreateFailedError`；
2. 再往上翻，真正的 SQLAlchemy 异常是 `OperationalError: cannot recognize input near 'SHOW' 'CATALOGS'`；
3. 但 `grep SHOW CATALOGS /app/superset/db_engine_specs/hive.py` 没有结果 → 说明不是 Hive 规格自己发的；
4. 查 `HiveEngineSpec.__mro__` 才明白它继承 `PrestoEngineSpec`，而 Presto 的 `get_catalog_names()` 正是执行 `SHOW CATALOGS`。

**修复**：`supports_catalog = False` + `get_catalog_names` 返回空集。第一次放在 `superset_config.py` 顶层失败（`Working outside of application context`），最终用 `FLASK_APP_MUTATOR`。

**教训**：依赖"继承"的框架里，一个引擎的怪行为可能来自另一个引擎的代码。查问题要顺着 MRO 走，而不是只 grep 当前文件。

### 4.2 最隐蔽的问题：占比分母

数字看起来"有值"，但四个占比加起来 9.4%。**只有把 4 个数加一遍才能发现**。
这类错误比"报错"危险得多：页面正常、图表正常、只有业务含义是错的。

**教训**：占比类字段必须做"分组内求和 = 1"的自检。这条已经固化进 `verify_ads_w4.sql`：

```sql
select '支付表 每月 GMV 占比求和偏差' as `检查项`,
       cast(round(max(abs(s - 1)), 4) as decimal(8, 4)) as `值`
from (select stat_month, sum(gmv_share) as s from ads_pay_type_month group by stat_month) x;
```

### 4.3 最容易误判的问题：热力图的"梯度"

配色本身就会制造"有规律"的错觉。这次靠统计检验避免了在答辩时说错话。

**教训**：图表能画出差异 ≠ 数据有规律。凡是"看起来有趋势"的结论，都要问三句：效应量多大？换个子集还成立吗？机制上讲得通吗？

### 4.4 最浪费时间的问题：compose 里的 shell 引号

`superset fab create-admin` 在 `/bin/sh -c "多行字符串"` 里退化成交互模式，表现是"容器一直不健康但日志看不出错"。

**教训**：编排文件里不要写需要多行参数的 shell 命令。复杂逻辑一律搬进 Python 脚本，compose 只负责启动。

---

## 五、反思与总结

**这一周 AI 帮我省下的是什么**
不是"写代码"，而是"写我不熟的那部分代码"：Superset 的 REST API 参数、ECharts 的 option 结构、docker healthcheck 的写法。这些靠查文档要花几小时，AI 一遍就能给出八成正确的骨架，剩下两成靠实测修。

**这一周 AI 帮不了的是什么**
全部是"判断"：这个数能不能用、这个结论能不能说、这个优化有没有收益、这个口径是否自洽。
第 6 条（热力图）和第 7 条（门店重名）尤其典型：AI 给出的是**看起来合理的答案**，只有人去核对字段、做统计检验，才能发现它是错的。

**本周新增的一条工作纪律**
凡是 AI 给出的"性能提升 X 倍"，必须附上**同口径**的对照实验。第 9 条就是反例：口径不同，跑出来的倍数毫无意义。

---

## 六、下周改进计划

1. **把自检脚本变成 CI**：现在 `ui_check.py`、`check_superset.py`、`verify_ads_w4.sql`、`export_to_clickhouse.py --verify-only` 都是手动跑，下一步串成一条 `make verify`，每次改完必跑；
2. **把"口径自检"模板化**：本周只对 2 张新表做了占比求和检查，下一步给所有含 share/rate 字段的表生成统一校验；
3. **Superset 也接 ClickHouse**：目前只有大屏走 CH，Superset 一个仪表板要打 6 次 Hive（每次 1 s+），换数据源能立刻见效；
4. **压测脚本加"资源观测"**：现在只测响应时间，不测 CPU/内存占用，说不出"瓶颈在哪一层"的硬证据；
5. **补一份数据字典**：本周 2 张新表的字段注释写得比前几周细，但还缺一份"哪个字段对应哪张图"的索引，答辩时不好快速定位。