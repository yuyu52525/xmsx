# 第 4 周 · 可视化实现与项目部署

> 主题：Superset 仪表板 + ECharts 数据大屏 + Streamlit 问答 + Docker 一键部署 + 压测优化
> 前置：第 1~3 周已完成四层数仓（`ydsh_ods` / `ydsh_dwd` / `ydsh_dws` / `ydsh_ads`）。本周**不重做数仓**，只在其上做展示与工程化。

## 一、本周做了什么

| 子任务 | 产出 | 位置 |
|---|---|---|
| 1. Superset 仪表板 | 2 数据源 + 8 数据集 + 6 图表 + 3 筛选器 + 交叉联动 | `docker/superset/`（自动初始化） |
| 2. ECharts 数据大屏 | 7 类图表、1920×1080 scale 自适应、离线可用 | `web/` |
| 3. Streamlit 问答 | NL2SQL 完整闭环 + 图表渲染 + 历史对话 | `py/streamlit_app.py` |
| 4. Docker Compose | 8 服务一键部署 + healthcheck + 密钥注入 | 仓库根 `docker-compose.yml` |
| 5. 密钥 / 优化 / 压测 | 三层密钥模型 + 4 项优化 + 4 组压测 | `docs/`、`stress/` |

## 二、5 分钟跑起来

```powershell
# 在仓库根目录
Copy-Item .env.example .env      # 填 SUPERSET_SECRET_KEY 和 LLM_API_KEY
docker compose build
docker compose up -d

# 初始化可视化数据（2 张新表 + CH 副本 + MySQL 快照）
cd 第4周\py
python run_w4.py data
```

然后打开三个入口：

- Superset：http://localhost:8088/superset/dashboard/ydgmv-overview/ （admin / admin）
- 大屏：http://localhost:8000/
- 问答：http://localhost:8501/

也可以直接双击 `一键运行/2_一键部署全部服务.bat`。

## 三、新增的两张 ADS 表（本周唯一动数仓的地方）

| 表 | 粒度 | 行数 | 口径 | 服务哪张图 |
|---|---|---|---|---|
| `ads_pay_type_month` | 月 × 支付方式 | 48 | 订单口径 `pay_amount`，合计 36,116,687.06 | 支付方式占比饼图 |
| `ads_hour_category` | 小时 × 品类 | 192 | 明细分摊 `alloc_amount`，合计 35,833,305.06 | 时段 × 品类热力图 |

两张表口径不同，**不可相加**（差额 283,382.65 元来自 114 张无明细订单）。

一键跑完建表 + 装载 + 29 条校验：

```powershell
python py\run_w4.py data
```

## 四、常用脚本

| 脚本 | 作用 |
|---|---|
| `py/run_w4.py` | 本周所有操作的统一入口（check / data / verify / stress / docs / docker-up） |
| `py/sql_runner.py` | 逐条执行 .sql 并计时，输出证据文件 |
| `py/api_server.py` | FastAPI 数据服务（10 接口 + 托管大屏） |
| `py/streamlit_app.py` | 对话式问答 |
| `py/export_to_clickhouse.py` | ADS → CH 副本，含一致性校验 |
| `py/export_to_mysql.py` | KPI 快照 → MySQL（供 Superset 跨源演示） |
| `py/ui_check.py` | 三界面自动上机自检 + 截图（CDP 驱动真实浏览器） |
| `py/dump_snapshot.py` | 生成大屏离线快照 |
| `py/md2docx.py` | Markdown 批量转 Word |
| `stress/stress_test.py` | 4 组压测实验 |

## 五、文档

- `docs/第4周_部署手册.docx` —— 8 服务、启动顺序、10 条真实踩坑、验收清单
- `docs/第4周_API配置指南.docx` —— 三层密钥模型、4 种大模型方案、只读账号、轮换 SOP
- `docs/第4周_压力测试记录.docx` —— 4 组实验数据与瓶颈分析
- `docs/第4周_可视化实现说明.docx` —— 三端实现细节 + 三端数字一致性核对 + 3 个负结果
- `docs/提交清单核对_第4周.docx` —— 与任务书交付物逐条对照
- `第4周_AI协同日志.docx` —— 10 条协同记录（8 条是"AI 给错 → 人工发现 → 改正"）

## 六、几个容易踩的点（详见部署手册）

1. **Superset 连 Hive 报 `SHOW CATALOGS`**：Hive 引擎规格继承了 Presto 的实现，Hive 4.0.0 不认这条语法 → 已在 `superset_config.py` 里关掉目录探测；
2. **ClickHouse 不能用 Windows 绑定挂载**：rename 分区目录会 Permission denied → 已改命名卷；
3. **仪表板图表全显示"已删除"**：图表与仪表板的关联表是空的 → bootstrap 用模型层写入；
4. **`ECHARTS_SRC` 必须写宿主机地址**：它由浏览器加载，写容器名在浏览器里 404。