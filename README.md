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
4. **智能层**：大模型 API + NL2SQL
5. **展示层**：Superset 仪表板 + ECharts 大屏
6. **工程层**：Git 版本控制 + Docker Compose 一键部署

## 三、技术栈

| 类别 | 技术 | 用途 |
|---|---|---|
| 数据仓库 | Apache Hive 4.0.0 | 四层数仓建模与 ETL |
| 元数据库 | MySQL 8.0 | Metastore 元数据存储 |
| 容器化 | Docker Desktop + WSL2 | 环境隔离与一键部署 |
| 版本控制 | Git | 团队协作 |

## 四、目录结构

```
.
├── docker-compose.yml        # 环境编排：mysql + hive-metastore + hive-server
├── data/                     # 数据目录（已 gitignore）
│   ├── csv/                  # 6 个 ODS 源 CSV
│   ├── mysql/                # MySQL 数据持久化
│   └── warehouse/            # Hive 数仓存储目录
├── lib/
│   └── mysql-connector-j-8.0.33.jar   # Hive 连接 MySQL 的 JDBC 驱动
├── sql/
│   ├── ods/                  # ODS 建表与导入脚本
│   │   ├── create_ods.sql
│   │   └── load_ods.sql
│   ├── quality/
│   │   └── assess_quality.sql         # 数据质量五维度评估
│   └── clean/                # 清洗脚本（缺失值 / 重复值）
│       ├── clean_missing.sql
│       └── clean_duplicate.sql
├── docs/
│   ├── 数据质量预评估表.md
│   └── 环境搭建笔记.md
└── README.md
```

## 五、环境启动

```bash
# 1. 启动三个服务
docker compose up -d

# 2. 查看状态（应看到 mysql、hive-metastore、hive-server 均为 Up）
docker ps

# 3. 进入 Hive 客户端
docker exec -it hive-server beeline -u jdbc:hive2://localhost:10000

# 4. 建库建表（脚本目录已挂载到容器 /sql）
-- 在 beeline 中执行
!run /sql/ods/create_ods.sql
```

## 六、阶段计划

| 周次 | 内容 | 状态 |
|---|---|---|
| 第 1 周 | 项目启动、环境搭建、Git、数据导入、质量预评估、清洗（一） | 已完成 |
| 第 2 周 | 数仓分层建模（DWD/DWS/ADS） | 待开始 |
| 第 3 周 | 指标计算、探索性分析、预测建模 | 待开始 |
| 第 4 周 | NL2SQL、Superset 可视化、部署与答辩 | 待开始 |
