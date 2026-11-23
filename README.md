# 云购生活 · 企业级数据仓库与经营分析可视化系统

> 课程：企业项目实战实训 | 数据科学与大数据技术（本科）
> 团队：乐天　口号：加油

## 一、团队成员与分工

| 姓名 | 学号 | 角色 | 主要职责 |
|---|---|---|---|
|余天乐 |20230308098 | 项目经理（兼数仓工程师） | 统筹进度、数仓架构、Git 管理 |
|余天乐 |20230308098 | 数据工程师 | 数据导入、清洗、Hive 四层建模 |
|余天乐 |20230308098 | 数据分析师 / AI 工程师 | 探索性分析、预测建模、NL2SQL |
|余天乐 |20230308098 | 可视化 / 部署工程师 | Superset、ECharts、Docker 部署 |

## 二、项目目标

基于云购生活新零售企业的 6 张业务表（约 11.5 万条模拟数据），从 0 到 1 构建一套数据仓库与经营分析系统：

1. **数据层**：6 张业务表采集导入，识别清洗五大类脏数据
2. **数仓层**：Hive 搭建 ODS → DWD → DWS → ADS 四层
3. **分析层**：KPI 指标计算与探索性分析
4. **智能层**：大模型 API + NL2SQL 对话式查询
5. **展示层**：Superset 仪表板 + ECharts 数据大屏 + Streamlit 问答
6. **工程层**：Git 版本控制 + Docker Compose 一键部署 + 压测与查询优化

## 三、技术栈

| 类别 | 技术 | 用途 |
|---|---|---|
| 数据仓库 | Apache Hive 4.0.0（Tez 引擎） | 四层数仓建模与 ETL |
| 元数据库 | MySQL 8.0 | Metastore 元数据 + Superset 元数据 + 业务库快照 |
| 存储格式 | ORC + SNAPPY | DWD 层列式存储与压缩 |
| BI 可视化 | Apache Superset 4.1.2 | 交互式仪表板（6 图表 + 3 筛选器 + 交叉联动） |
| 前端可视化 | ECharts 5.5.1（本地化引入） | 7 类图表的 1920×1080 数据大屏 |
| 对话应用 | Streamlit 1.41 | NL2SQL 问答闭环 + 图表渲染 |
| 数据服务 | FastAPI + uvicorn | 10 个 JSON 接口 + 大屏静态托管 |
| 大模型 | 智谱 GLM-4-Flash（可切 DeepSeek / 硅基流动 / Ollama） | 自然语言 → SQL |
| OLAP 加速 | ClickHouse 24.8 | ADS 结果集服务层缓存（压测对比 + 大屏高频读取） |
| 容器化 | Docker Compose（9 服务 = 7 常驻 + 2 一次性） | 一键部署、健康检查、依赖编排 |
| 版本控制 | Git | 团队协作 |

## 四、目录结构

```
.
├── docker-compose.yml        # 9 个服务的一键编排（含 healthcheck / 依赖顺序）
├── .env.example              # 环境变量模板（复制成 .env 后填密钥）
├── data/                     # 数据目录（已 gitignore）
│   ├── csv/                  # 6 个 ODS 源 CSV
│   ├── mysql/                # MySQL 数据持久化
│   └── warehouse/            # Hive 数仓存储目录
├── lib/
│   └── mysql-connector-j-8.0.33.jar   # Hive 连接 MySQL 的 JDBC 驱动
├── 第1周/                     # 环境搭建 + ODS 贴源层 + 质量预评估
├── 第2周/                     # 清洗 + DWD 维度建模 + 探索性分析
├── 第3周/                     # DWS/ADS 建模 + KPI + 预测建模 + NL2SQL + AI 洞察
├── 第4周/                     # 可视化实现（Superset + ECharts + Streamlit）+ Docker 部署
│   ├── sql/ads/               # 2 张新增 ADS 表的建表 / 装载 / 校验
│   ├── py/                    # 数据服务、Streamlit、NL2SQL、导出、自检、一键运行
│   ├── web/                   # ECharts 大屏（含本地 echarts.min.js 与中国地图）
│   ├── docker/superset/       # Superset 镜像 + 自动初始化仪表板
│   ├── docker/app/            # 应用镜像与依赖
│   ├── stress/                # 压力测试脚本
│   ├── docs/                  # 5 篇文档 + 提交清单 + 4 张截图
│   ├── evidence/              # 真实运行输出
│   └── 一键运行/              # 9 个 bat，双击即可
├── 第5周/                     # 项目整合：端到端联调脚本、五大项目文档、证据
│   ├── py/                    # e2e_verify.py（39 项核对）、fetch_kpi.py、md2docx.py
│   ├── sql/                   # 逐层核对 SQL
│   ├── docs/                  # 需求/清洗/架构/部署/API 五篇 + 日志 + PR 记录
│   ├── evidence/              # 联调与取数证据
│   └── 一键运行/              # 端到端自检 bat
├── README.md                  # 中文 README
└── README.en.md               # 英文 README（国际化门面）
```

## 五、环境启动（一键部署）

### 5.1 首次部署

```bash
# 1. 准备环境变量（至少填 SUPERSET_SECRET_KEY 与 LLM_API_KEY）
cp .env.example .env          # Windows: Copy-Item .env.example .env
#    生成随机密钥：docker run --rm python:3.12-slim python -c "import secrets;print(secrets.token_urlsafe(42))"

# 2. 构建镜像（Superset 补 Hive 驱动；应用镜像装 FastAPI/Streamlit/LangChain）
docker compose build

# 3. 一键启动 9 个服务
docker compose up -d
docker compose ps            # 期望：7 个 healthy + 2 个 Exited(0)（* -init 是一次性任务）

# 4. 初始化可视化数据（建 2 张新表 → 校验 → 导 ClickHouse → 导 MySQL）
cd 第4周/py
python sql_runner.py ../sql/ads/create_ads_w4.sql
python sql_runner.py ../sql/ads/load_ads_w4.sql
python sql_runner.py ../sql/ads/verify_ads_w4.sql
python export_to_clickhouse.py
python export_to_mysql.py
```

### 5.2 访问入口

| 入口 | 地址 | 账号 |
|---|---|---|
| Superset 仪表板 | http://localhost:8088/superset/dashboard/ydgmv-overview/ | admin / admin |
| ECharts 数据大屏 | http://localhost:8000/ | 免登录 |
| Streamlit 问答 | http://localhost:8501/ | 免登录 |
| 数据服务接口文档 | http://localhost:8000/api/docs | 免登录 |
| 服务健康检查 | http://localhost:8000/api/health | 免登录 |

### 5.3 常用命令

```bash
docker compose ps                                   # 状态
docker compose logs -f --tail 100 superset          # 日志
docker compose down                                  # 停止（保留数据）
docker compose build api && docker compose up -d api # 改代码后重建

# 三界面自动上机自检（无头浏览器真点 + 截图）
python 第4周/py/ui_check.py
# Superset 图表取数校验
docker compose run --rm --entrypoint python superset-init /app/check_superset.py
```

> **Hive 建表注意**：官方 metastore 把注释列定义成 `latin1`，中文字段注释会被静默替换成 `?`。本项目已改造为 `utf8mb4`，新环境重跑请先执行 `第1周/docs/环境搭建笔记.md` 第六节的 6 条 `ALTER TABLE`。
>
> **容器重启注意**：`docker restart hive-server` 会因容器内 pid 文件残留陷入重启循环，需改用 `docker compose up -d --force-recreate hive-server`（数据在 bind mount，不会丢）。

## 六、当前进度与核心成果

### 6.1 库表规模

| 库 | 表数 | 说明 |
|---|---|---|
| `ydsh_ods` | 6 | 贴源层，TextFile |
| `ydsh_dwd` | 25 | 11 张正式表（8 维 + 3 事实）+ 14 张清洗中间表，ORC + SNAPPY |
| `ydsh_dws` | 9 | 汇总层，按月分区 |
| `ydsh_ads` | **11** | 应用层：第 3 周 9 张 + 第 4 周新增 2 张（支付方式、时段×品类） |

### 6.2 数据规模变化

| 阶段 | 行数 |
|---|---|
| ODS 原始导入 | 114,809 |
| DWD 清洗后 | 111,037（−3.28%，删除项均有业务依据） |
| ADS 可视化结果集 | 2,666（11 张表，供三端图表直接取用） |

### 6.3 核心指标（2024 全年，订单口径）

| 指标 | 数值 |
|---|---|
| 总用户 / 下单用户 | 1,000 / 1,000 |
| 总订单量 | 14,398 |
| GMV | 36,116,687.06 元 |
| 有效 GMV（有效营收） | 24,185,272.59 元（66.96%） |
| 客单价 | 2,508.45 元 |
| ARPU | 36,116.69 元 |
| 品类销售合计（明细分摊口径） | 35,833,305.06 元 |
| 支付方式第一 | 微信支付 9,668,087.14 元（26.77%） |
| 省份第一 | 陕西省 2,851,136.58 元（7.89%） |
| 门店第一（按 store_id） | S029 云购生活·北京二店 708,051.42 元（⚠ 按名称聚合会把 S029 与 S039 合并成 1,321,107.24 元，本项目统一按编号） |

### 6.4 质量治理成果

| 类别 | 修复率 |
|---|---|
| 完整性（缺失） | 100%（邮箱 193 条保留并标记） |
| 唯一性（重复） | 100%（600 条重复订单） |
| 一致性（格式） | 100%（日期 2,027 + 手机号 102 + 行为时间 6,088） |
| 准确性（异常值） | 100%（金额 622 + 数量 1,081 + 单价 798 + 年龄 27 + 商品价 36） |
| 有效性（枚举） | 100%（7 个字段取值种类收敛到 3–8 个） |

### 6.5 第 4 周关键成果

| 项 | 结果 |
|---|---|
| Superset 仪表板 | 6 个图表（指标卡/折线/柱状/地图/饼图/排行表）+ 3 个原生筛选器 + 交叉联动，6/6 取数验证通过 |
| ECharts 数据大屏 | 7 类图表（折线/柱状/散点/热力/地图/饼图/排行条），1920×1080 scale 自适应，离线快照兜底 |
| Streamlit 问答 | 提问 → SQL → 只读校验 → 执行 → 表格 + 图表，含历史/加载/错误提示 |
| 一键部署 | 8 服务 `up -d` 全绿，密钥全走 `.env` |
| 查询优化 | 分区裁剪 6.0×、ADS 预聚合 2.9×、服务缓存 6.5×、ClickHouse 读取 113× |
| 压测 | 4 组实验，20 并发下 p50 381 ms、失败率 0% |

## 七、阶段计划

| 周次 | 内容 | 状态 |
|---|---|---|
| 第 1 周 | 项目启动、环境搭建、Git、数据导入、质量预评估、清洗（一） | 已完成 |
| 第 2 周 | 清洗（二）、四层架构设计、DWD 维度建模、探索性分析 | 已完成 |
| 第 3 周 | DWS 汇总层、ADS 指标层、KPI 计算、预测建模、NL2SQL、AI 洞察 | 已完成 |
| 第 4 周 | Superset 仪表板、ECharts 大屏、Streamlit 问答、Docker 一键部署、压测与优化 | 已完成 |
| 第 5 周 | 端到端联调、五大项目文档、英文 README、Git 历史治理、综合答辩 | 已完成（答辩 PPT 待做） |

### 6.6 第 5 周关键成果

| 项 | 结果 |
|---|---|
| 端到端联调 | 第5周/py/e2e_verify.py 39 项核对全部 PASS（服务/四层行数/指标口径/两份副本/10 接口） |
| 五大文档 | 需求文档、数据质量清洗报告、架构设计文档、部署手册、API 配置指南（md + docx） |
| 英文 README | README.en.md（11 节，含架构图、快速开始、指标体系、已知局限） |
| Git 治理 | 第 5 周走 docs/week5-integration 分支 + PR 记录，补第 4 周漏走分支的说明 |
| 口径统一 | 服务数统一为 9；剔除率统一为 3.29%；门店排名统一按 store_id |

## 八、文档索引

| 文档 | 位置 |
|---|---|
| 第 4 周部署手册 | `第4周/docs/第4周_部署手册.docx` |
| 第 4 周 API 配置指南 | `第4周/docs/第4周_API配置指南.docx` |
| 第 4 周压力测试记录 | `第4周/docs/第4周_压力测试记录.docx` |
| 第 4 周可视化实现说明 | `第4周/docs/第4周_可视化实现说明.docx` |
| 第 4 周提交清单核对 | `第4周/docs/提交清单核对_第4周.docx` |
| 第 4 周 AI 协同日志 | `第4周/第4周_AI协同日志.docx` |
| 前三周文档 | 各周 `docs/` 目录 |