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
| 数据仓库 | Apache Hive 4.0.0（Tez 引擎） | 四层数仓建模与 ETL |
| 元数据库 | MySQL 8.0 | Metastore 元数据存储 |
| 存储格式 | ORC + SNAPPY | DWD 层列式存储与压缩 |
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
│   │   ├── assess_quality.sql         # 第 1 周：五维度质量评估
│   │   └── assess_week2.sql           # 第 2 周：清洗前后修复率对比（24 项指标）
│   ├── clean/                # 清洗脚本
│   │   ├── clean_missing.sql          # 清洗一：缺失值
│   │   ├── clean_duplicate.sql        # 清洗一：重复值
│   │   ├── clean_enum.sql             # 清洗二：枚举标准化 + 文本规范化
│   │   ├── clean_format.sql           # 清洗二：异常值 + 格式标准化
│   │   └── clean_split_merge.sql      # 清洗二：字段拆分合并 + 编码映射维表
│   ├── dwd/                  # DWD 层建模与加载
│   │   ├── create_dwd.sql             # 11 张正式表 DDL（含分区表、分桶表）
│   │   ├── load_dwd.sql               # ETL 加载 + 加载校验
│   │   └── verify_dwd.sql             # 分桶信息、分区裁剪、金额闭合校验
│   └── analysis/
│       └── eda.sql                    # 探索性分析 19 组查询
├── docs/
│   ├── 数仓架构设计文档.md / .docx      # 四层架构 + 星型模型 + 命名规范
│   ├── 数据质量清洗报告.md / .docx      # 五类脏数据修复率（第 2 周）
│   ├── 探索性分析简报.md / .docx        # KPI 与 8 个维度分析
│   ├── 数据质量对比表.xlsx              # 修复率 / 枚举收敛 / 行数变化 / 核心指标
│   ├── 数据质量预评估表.md / .xlsx      # 第 1 周五维度评估
│   ├── 环境搭建笔记.md / .docx
│   ├── 乐天_第1周_AI协同日志.md
│   ├── 乐天_第2周_AI协同日志.md
│   ├── 提交清单核对.md / 提交清单核对_第2周.md
│   ├── evidence/                       # 全部 SQL 的真实运行输出（可复核）
│   └── images/第2周/                    # 架构图 2 张 + 运行截图 6 张
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

**跑完整链路（ODS → 清洗 → DWD → 分析）**

```bash
for f in ods/create_ods.sql ods/load_ods.sql \
         clean/clean_missing.sql clean/clean_duplicate.sql \
         clean/clean_enum.sql clean/clean_format.sql clean/clean_split_merge.sql \
         dwd/create_dwd.sql dwd/load_dwd.sql dwd/verify_dwd.sql \
         quality/assess_week2.sql analysis/eda.sql; do
  docker exec hive-server beeline -u jdbc:hive2://localhost:10000 -f /sql/$f
done
```

## 六、当前进度与核心成果

### 6.1 库表规模

| 库 | 表数 | 说明 |
|---|---|---|
| `ydsh_ods` | 9 | 6 张贴源表 + 3 张清洗一中间表 |
| `ydsh_dwd` | 25 | 11 张正式表（4 维 + 3 事实 + 4 编码维）+ 14 张清洗中间表 |
| `ydsh_dws` | 0 | 第 3 周建设（已规划 4 张汇总表） |
| `ydsh_ads` | 0 | 第 4 周建设（已规划 4 张指标表） |

### 6.2 数据规模变化

| 阶段 | 行数 |
|---|---|
| ODS 原始导入 | 114,809 |
| DWD 清洗后 | 111,037（−3.28%，删除项均有业务依据） |

### 6.3 核心指标（DWD 层，2024 全年）

| 指标 | 数值 |
|---|---|
| 总用户 / 下单用户 | 1,000 / 1,000 |
| 总订单量 | 14,398 |
| GMV（全量） | 36,116,687.06 元 |
| GMV（有效营收） | 24,185,272.59 元 |
| 客单价 | 2,508.45 元 |
| 人均下单次数 | 14.40 次 |

### 6.4 质量治理成果

| 类别 | 修复率 |
|---|---|
| 完整性（缺失） | 100%（邮箱 193 条保留并标记） |
| 唯一性（重复） | 100%（600 条重复订单） |
| 一致性（格式） | 100%（日期 2,027 + 手机号 102 + 行为时间 6,088） |
| 准确性（异常值） | 100%（金额 622 + 数量 1,081 + 单价 798 + 年龄 27 + 商品价 36） |
| 有效性（枚举） | 100%（7 个字段取值种类收敛到 3–8 个） |

## 七、阶段计划

| 周次 | 内容 | 状态 |
|---|---|---|
| 第 1 周 | 项目启动、环境搭建、Git、数据导入、质量预评估、清洗（一） | 已完成 |
| 第 2 周 | 清洗（二）、四层架构设计、DWD 维度建模、探索性分析 | 已完成 |
| 第 3 周 | DWS 汇总层、指标计算、预测建模 | 待开始 |
| 第 4 周 | NL2SQL、Superset 可视化、部署与答辩 | 待开始 |