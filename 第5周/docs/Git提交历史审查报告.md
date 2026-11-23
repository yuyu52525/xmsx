# 云购生活 · Git 提交历史审查报告（第 5 周）

| 项目 | 内容 |
|---|---|
| 审查对象 | `git@github.com:yuyu52525/xmsx.git` 本地仓库 `D:\xiangmushixun-bde` |
| 审查日期 | 2026-11-23 |
| 审查依据 | 《第 5 周任务书》子任务 3：检查提交网络图与分支结构、核对约定式提交、整理 PR / Issue 记录 |
| 审查方式 | `git log --oneline --graph --all`、`git branch -a`、`git ls-tree -r -l`、`git check-ignore -v`、`git request-pull` |
| 原始输出 | `第5周/evidence/git_review.txt` |
| 整改结果 | 本轮新增 1 个功能分支、6 个规范提交、1 条 PR 记录、1 条 Issue 记录 |

---

## 一、审查前的仓库状态

| 指标 | 数值 |
|---|---|
| 提交总数 | 37（第 1～4 周） |
| 分支 | `main` + 4 个历史分支（`docs/readme-index`、`docs/readme-week3`、`feat/ai-insight`、`feat/llm-multi-provider`） |
| PR 记录 | #12～#15（保存在 `第3周/docs/git/`，含一次真实 merge 冲突原文） |
| 被跟踪文件 | 208 个 |
| 最大文件 | `lib/mysql-connector-j-8.0.33.jar` 2.48 MB（Hive 连 MySQL 的 JDBC 驱动，必要依赖） |
| 工作区 | 干净，无未提交改动 |

---

## 二、提交类型分布（约定式提交自查）

统计 37 个历史提交的主题前缀：

| 前缀 | 数量 | 说明 |
|---|---|---|
| `feat` | 12 | 功能开发 |
| `docs` | 12 | 文档 |
| `chore` | 5 | 杂务、环境、忽略规则 |
| `merge` | 4 | 分支合并（PR #12～#15） |
| `refactor` | 2 | 目录重构、LLM 多供应商改造 |
| `fix` | 1 | metastore 字符集修复 |
| **无前缀** | **1** | `第4周：可视化实现（Superset + ECharts + Streamlit）与 Docker 一键部署`（`6f43b92`） |

**结论**：36/37 符合约定式提交，规范率 97.3%。唯一一个不符的 `6f43b92` 同时也是第 4 周"未走分支"的问题提交（见第五节）。

---

## 三、分支结构

### 3.1 审查前的网络图（节选）

```
* 00a0658 (HEAD -> main, origin/main) chore(第4周): 刷新重启后三界面自检证据
* 6f43b92 第4周：可视化实现（Superset + ECharts + Streamlit）与 Docker 一键部署
* 383ec4c feat(run): 增加一键运行启动器与运行说明
* 678a952 chore: 提交压缩包改为本地生成物，不再入库
* 57104bc feat(llm): 接入真实大模型，补齐 NL2SQL 与 AI 洞察的实测证据
* a29f7ff docs(week3): 完成第3周全部交付物文档与 Word/Excel 成品
*   3b93f20 merge: 解决 README 目录结构合并冲突 (PR #15)
|\
| * 1627270 docs(readme): 目录结构补入第3周，指到提交清单便于查阅
* |   6f59e6a merge: 合入 README 第3周目录（详细版）(PR #14)
...
| * 5d23604 refactor(llm): 配置改为多供应商通用，支持智谱/硅基流动/Ollama
|/
* 47919d1 feat(week3): DWS/ADS 九表建模、KPI 报表、GMV 预测与 NL2SQL 接口
```

**读图结论**：

- 第 1～3 周有真实的分叉—合并结构，4 个 PR 各留下一个 merge 提交，`git log --graph` 能看出"哪个模块在哪条分支上做"；
- 第 4 周（`383ec4c` → `6f43b92` → `00a0658`）是**直链**，没有分叉，说明没有走分支。

### 3.2 分支命名规范性

| 分支 | 命名 | 评价 |
|---|---|---|
| `feat/llm-multi-provider` | 类型/主题 | ✅ 规范 |
| `feat/ai-insight` | 类型/主题 | ✅ 规范 |
| `docs/readme-week3` | 类型/主题 | ✅ 规范 |
| `docs/readme-index` | 类型/主题 | ✅ 规范 |
| 第 4 周 | 无分支 | ❌ 缺失 |

---

## 四、PR / Issue 记录整理

| 编号 | 类型 | 主题 | 分支 | 记录文件 |
|---|---|---|---|---|
| #12 | PR | LLM 多供应商改造（智谱 / 硅基流动 / Ollama） | `feat/llm-multi-provider` | `第3周/docs/git/pull_request_12_llm.txt` |
| #13 | PR | AI 洞察量价拆解与反思文档 | `feat/ai-insight` | `第3周/docs/git/pull_request_13_insight.txt` |
| #14 | PR | README 第 3 周目录（详细版） | `docs/readme-week3` | `第3周/docs/git/pull_request_14_readme.txt` |
| #15 | PR | README 第 3 周目录（冲突解决） | `docs/readme-index` | `第3周/docs/git/pull_request_14_readme.txt` + `merge_conflict_raw.txt` |
| **#16** | **PR** | **第 5 周整合：联调脚本 + 五篇文档 + 英文 README + 口径统一** | **`docs/week5-integration`** | **`第5周/docs/git/pull_request_16_week5_integration.txt`** |
| **#16-I** | **Issue** | **整合期四类口径不一致（服务数 / 剔除率 / 门店 / 周数）** | — | **`第5周/docs/git/issue_16_week5_scope.txt`** |

> #15 与 #14 的编号复用是当时的一次记录疏漏（两个 PR 共用一个文本文件），本轮不再回改历史，如实列在这里。

---

## 五、发现的问题与整改

| # | 问题 | 严重度 | 整改 |
|---|---|---|---|
| 1 | 第 4 周三个提交直接进 `main`，无分支、无 PR | 高（直接对应评分项） | 补写成因说明 `week4_direct_to_main_explained.txt`；第 5 周恢复分支流程；**不重写已推送历史** |
| 2 | `6f43b92` 不符合约定式提交，且一次提交 60+ 文件 | 中 | 记录在案；第 5 周起"一件事一个提交" |
| 3 | PR #14 / #15 共用一份记录文件 | 低 | 如实列出，不回改 |
| 4 | 第 4 周批量提交使日志看不出模块边界 | 中 | 第 5 周 6 个提交按模块拆分（docker / 脚本 / 文档 / README / Git 记录 / 证据） |
| 5 | `docker-compose.yml` 注释与 README 写"8 个服务"，实际 9 个 | 中 | 本轮 `chore(docker)` 提交统一为 9，并同步 README 中英双版 |

---

## 六、安全与仓库卫生自查

| 检查项 | 命令 | 结果 |
|---|---|---|
| `.env` 是否被跟踪 | `git check-ignore -v .env` | ✅ 输出 `.gitignore:10:.env`，未被跟踪 |
| 仓库内是否有明文 Key | `git grep -n "sk-" -- .` | ✅ 5 处命中全部是占位符或文档示例（`sk-your-key-here`、`sk-你的DeepSeekKey`），无真实 Key |
| 是否有 zip / 数据文件入库 | `git ls-files` | ✅ 无 `*.zip`、无 `data/` 内容 |
| 大文件 | `git ls-tree -r -l HEAD` | ✅ 最大为 2.48 MB 的 JDBC 驱动（必要依赖），其余为前端本地化资源（echarts.min.js 1.03 MB、china.json 0.58 MB）与文档图片 |

---

## 七、本轮执行的提交（第 5 周）

| 序号 | 提交 | 内容 |
|---|---|---|
| 1 | `chore(docker)` | 服务数统一为 9；挂载 `第5周` 目录；重写启动顺序注释 |
| 2 | `feat(integration)` | `e2e_verify.py`（39 项）、`fetch_kpi.py`、`check_docx.py`、`md2docx.py`（含图片支持）、`integrity_check.sql`、2 个 bat、3 份证据 |
| 3 | `docs(week5)` | 需求文档 / 数据质量清洗报告 / 架构设计文档 / 部署手册 / API 配置指南 / 端到端联调记录 / AI 协同日志 / 项目反思日志（md + docx） |
| 4 | `docs(readme)` | `README.en.md` 新增；`README.md` 中英互链与口径同步 |
| 5 | `docs(git)` | PR #16 记录、Issue #16 记录、第 4 周直提 main 说明、本审查报告 |
| 6 | `chore(evidence)` | 刷新 `git_review.txt`（含以上提交的完整网络图） |

合并方式：`docs/week5-integration` → `main`，使用 `--no-ff` 合并以保留分支痕迹（与 PR #12～#15 的做法一致）。

---

## 八、结论

1. **主干历史清晰**：43 个提交、5 个功能分支、5 条 PR 记录，`git log --graph` 能看出模块边界（第 4 周那段除外，已单独说明）。
2. **约定式提交规范率**：37 个历史提交 97.3%，本轮 6 个提交 100%。
3. **无敏感信息泄露**：`.env` 未入库，仓库内无真实 Key，无 zip / 数据文件。
4. **已知缺口已留痕**：第 4 周未走分支是本项目 Git 规范上的明确退步，选择记录成因与整改而不是重写历史——**能说清为什么错，比看起来没错更有价值**。
5. 复跑方式：`python 第5周/py/e2e_verify.py`（39 项）+ `git log --oneline --graph --all`（网络图）。