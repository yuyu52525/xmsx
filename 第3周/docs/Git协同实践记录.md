# 云购生活 · Git 协同实践记录（第 3 周）

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0（第 3 周） |
| 依据 | 《第 3 周任务书》交付物 6：PR / Code Review / Issue 记录（Git 协同） |
| 仓库 | `git@github.com:yuyu52525/xmsx.git` |
| 分支 | `main` + 4 条特性分支（已全部推送） |
| 证据目录 | `第3周/docs/git/` |

---

## 一、本周协同做了什么

第 2 周的问题是**所有工作都堆在 `main` 上直接提交**——出了错只能回滚，也没法"先做一版给别人看看再合"。

本周改成**特性分支 + PR + 合并**的流程，并真实演练了一次合并冲突。具体做了四件事：

1. 用 4 条特性分支承载不同模块的改动，每条分支单独提交；
2. 每条分支合入 `main` 时用 `--no-ff` 保留合并节点（不搞快进合并，否则历史里看不出"这里曾经是一个 PR"）；
3. 故意让两条分支修改 README 的同一段，**产生真实冲突并手工解决**；
4. 用 `git request-pull` 生成 PR 摘要（真实命令输出，不是手写的），留存为 PR 记录。

---

## 二、分支策略

采用简化的 Git Flow：`main` 保持随时可交付，功能改动一律走 `feat/*` 或 `docs/*` 分支。

| 分支名 | 类型 | 内容 | 最终状态 |
|---|---|---|---|
| `feat/llm-multi-provider` | feat | LLM 配置改为多供应商通用 | 已合入（PR #12） |
| `feat/ai-insight` | feat | 量价拆解归因 + AI 反思文档 | 已合入（PR #13） |
| `docs/readme-week3` | docs | README 目录树展开第 3 周 | 已合入（PR #14） |
| `docs/readme-index` | docs | README 目录树只加索引行 | 冲突后合入（PR #15） |

分支命名规则：`类型/简短主题`，类型用 `feat` / `fix` / `docs` / `refactor` / `chore`。

---

## 三、提交记录

```
*   3b93f20 merge: 解决 README 目录结构合并冲突 (PR #15)
|\
| * 1627270 docs(readme): 目录结构补入第3周，指到提交清单便于查阅
* |   6f59e6a merge: 合入 README 第3周目录（详细版）(PR #14)
|\ \
| |/
|/|
| * 5385f37 docs(readme): 目录结构补入第3周，标注 dws/ads/py 子目录
|/
*   8e9aca6 merge: 合入 AI 洞察量价拆解与反思文档 (PR #13)
|\
| * cd471ad feat(insight): 增加量价拆解归因与 AI 反思文档
* |   b02aa55 merge: 合入 LLM 多供应商改造 (PR #12)
|\ \
| |/
|/|
| * 5d23604 refactor(llm): 配置改为多供应商通用，支持智谱/硅基流动/Ollama
|/
* 47919d1 feat(week3): DWS/ADS 九表建模、KPI 报表、GMV 预测与 NL2SQL 接口
* e31bfa4 refactor: 按周拆分目录，第 1 周与第 2 周各自独立
```

提交信息采用 Conventional Commits 格式：`类型(范围): 简述` + 空行 + 详细说明。

| 提交号 | 类型 | 说明 |
|---|---|---|
| `47919d1` | feat | 本周主体：18 张表建模、KPI、预测、NL2SQL |
| `5d23604` | refactor | LLM 多供应商改造 |
| `b02aa55` | merge | PR #12 合并节点 |
| `cd471ad` | feat | AI 洞察量价拆解 |
| `8e9aca6` | merge | PR #13 合并节点 |
| `5385f37` | docs | README 详细版 |
| `6f59e6a` | merge | PR #14 合并节点 |
| `1627270` | docs | README 索引版 |
| `3b93f20` | merge | PR #15 合并节点（含冲突解决） |

> 为什么坚持 `--no-ff`：如果允许快进合并，`main` 的历史会变成一条直线，事后无法回答"这批改动当初是作为一个整体评审过的吗"。`--no-ff` 强制留下 merge commit，`git log --graph` 能直接看出分支结构。

---

## 四、PR 记录

### PR #12 · LLM 配置改为多供应商通用

| 字段 | 内容 |
|---|---|
| 分支 | `feat/llm-multi-provider` → `main` |
| 提交 | `5d23604` |
| 变更 | 3 文件，+136 / -44 |
| 状态 | 已合并（`b02aa55`） |

**变更动机**：初版把 `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` 写死在代码里。老师在课上提到"作业可以用免费模型"，而不同同学拿到的 Key 来源不同（智谱、硅基流动、学校统一发的），写死意味着换一家就要改代码。

**改动要点**：

1. 统一为 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`；
2. 保留 `DEEPSEEK_*` / `OPENAI_*` 作为兼容别名（按顺序查找），老配置不用改；
3. `selftest()` 增加错误分类：401 认证失败 / 404 模型名不对 / 429 限流 / 连不上；
4. `.env.example` 给出 4 种方案的复制粘贴块（含 2 个免费方案）。

**Review 意见**（自审 + 复核）：

- ✅ 兼容逻辑用 `_pick(*names)` 实现，顺序查找，没有 if-else 堆叠；
- ⚠️ **提出但未改**：`_pick` 会同时读 `OPENAI_API_KEY`，如果用户机器上恰好有 OpenAI 的 Key，可能误用。风险低（Base URL 默认还是 DeepSeek，会 401），记录为已知限制；
- ✅ 脱敏函数 `mask_key` 只露前 6 后 4，`--mask` 模式不发起网络请求。

### PR #13 · 量价拆解归因 + AI 反思文档

| 字段 | 内容 |
|---|---|
| 分支 | `feat/ai-insight` → `main` |
| 提交 | `cd471ad` |
| 变更 | 3 文件，+329 / -2 |
| 状态 | 已合并（`8e9aca6`） |

**变更动机**：初版归因只做了"渠道拆解"，结论停留在"四个渠道都降了"，等于没解释。补上 `GMV = 订单量 × 客单价` 的拆解后，才发现三个下滑日里有**两个是量跌（订单量掉到 56%）、一个是价跌（客单价掉到 67%）**——这是性质完全不同的两类问题。

**Review 意见**：

- ✅ 修正了归因表"占整体降幅比重"误用正号的问题（降幅贡献显示成 `+24.7%`，容易误读为"增长"）；
- ✅ 量价指数以全年均值为 100%，判定阈值写死为 0.8 / 1.15，阈值选择在文档里说明了理由；
- ⚠️ **遗留**：判定规则是硬编码的 if-else，新增异常类型时要改代码。后续应抽成配置表。

### PR #14 / #15 · README 目录结构（含冲突）

见第六节。

---

## 五、Code Review 记录

本周做的是**自审 + 复核**（单人项目，没有第二个人类 reviewer，这一点必须如实说明）。评审对象是本周边写边改的代码，下面是真实发现的问题，不是编的。

### 5.1 发现的 6 个问题

| # | 文件 | 问题 | 严重度 | 处理 |
|---|---|---|---|---|
| 1 | `forecast_gmv.py` | `dropna()` 无差别判空，把画图用的 `ma30` 也当特征判空，白扔开头 29 天，训练集从 322 缩到 307 | 中 | 已修：改 `dropna(subset=FEATURES)` |
| 2 | `ai_insight.py` | 归因表"占降幅比重"用了 `+{:.1f}%`，降幅显示成正数 | 中 | 已修：去掉正号，列名改"占整体降幅比重" |
| 3 | `load_dws.sql` | 末尾 9 路 `union all` 校验触发 `Too many counters: 121 max=120` | 高 | 已修：拆成一条语句一张表 |
| 4 | `load_dws.sql` | 直接用 `dim_date.week_of_year` 导致 `2024-W01` 覆盖全年 | 高 | 已修：自建 `tmp_date_week` 推导周键 |
| 5 | `nl2sql.py` | `guard_sql` 正则挡不住"合法 SELECT 写出笛卡尔积" | 中 | **未修**，记录为已知限制，建议加超时/行数阈值 |
| 6 | `llm_client.py` | 缺 Key 时原实现返回空串，调用方无法区分"没配"和"模型返回空" | 中 | 已修：抛 `LLMNotConfigured` |

### 5.2 问题 1 的复盘（最有价值的一个）

这个 bug 是**指标对不上才暴露的**：报告里写"训练集 322 天"，但脚本输出是 307 天。

排查过程：
1. 先怀疑数据有缺失 → 查 `count(1)`，366 天、无空值；
2. 再怀疑特征构造 → 单独跑 `add_features` + `dropna`，得到 352 行，与 366-14=352 吻合；
3. 那 307 从哪来？352-30=322 才对 → 回头看 `main()`，发现 `df["ma7"]`/`df["ma30"]` 先加进了 df，再传入 `add_features`，`dropna()` 把 `ma30` 的 29 个空也算进去了。

**教训**：`dropna()` 不带参数是最危险的写法之一，它会把你**不打算用于建模**的列也纳入判空。生产代码应该永远写 `subset=`。

### 5.3 评审结论

- 代码可读性：函数职责清晰，注释写"为什么"而不是"是什么"，符合要求；
- 可复现性：每个产出都有对应脚本 + evidence 输出，可重跑；
- **主要短板**：单人项目，Review 是自己看自己，天然存在盲区。这条已写进第八节反思。

---

## 六、合并冲突：一次真实的冲突与解决

### 6.1 冲突是怎么造出来的

两条分支都从 `main`（`8e9aca6`）拉出，都要在 README 的目录树里加"第 3 周"这一段：

- `docs/readme-week3`：展开写 4 个子目录（sql/py/docs/evidence）；
- `docs/readme-index`：只写一行索引，指向提交清单。

两者修改的是**同一段连续行**（`│   └── 第2周_AI协同日志.md` 之后、`└── README.md` 之前），所以第二个合并必然冲突。

先合 `docs/readme-week3`（快进不行，用 `--no-ff` 成功），再合 `docs/readme-index`：

```
$ git merge --no-ff docs/readme-index -m "merge: 合入 README 第3周目录（索引版）(PR #15)"
Auto-merging README.md
CONFLICT (content): Merge conflict in README.md
Automatic merge failed; fix conflicts and then commit the result.

$ git status --short
UU README.md
```

`UU` = both modified，两边都改了同一处。

### 6.2 冲突现场（原始内容，见 `git/merge_conflict_raw.txt`）

```
<<<<<<< HEAD
├── 第3周/                     # 第 3 周：DWS/ADS 建模 + KPI + 预测 + NL2SQL
│   ├── sql/
│   │   ├── dws/               # 建表、装载、校验
│   │   └── ads/               # 建表、装载、校验、KPI 报表
│   ├── py/                    # 预测建模、NL2SQL、AI 洞察
│   ├── docs/
│   └── evidence/
=======
├── 第3周/                     # 第 3 周（交付物见 第3周/docs/提交清单核对_第3周.md）
>>>>>>> docs/readme-index
└── README.md
```

### 6.3 解决思路（不是简单二选一）

按"谁的方案更好"来选是错的——**两份改动各自解决了一个问题**：

- 展开版解决了"看得出第 3 周有什么"；
- 索引版解决了"知道去哪找交付物"。

所以解决方式是**合并两者意图**：保留展开结构，同时把索引信息塞进 `docs/` 那一行的注释里：

```
├── 第3周/                     # 第 3 周：DWS/ADS 建模 + KPI + 预测 + NL2SQL
│   ├── sql/
│   │   ├── dws/               # 建表、装载、校验
│   │   └── ads/               # 建表、装载、校验、KPI 报表
│   ├── py/                    # 预测建模、NL2SQL、AI 洞察
│   ├── docs/                  # 含提交清单核对_第3周.md、git/ 协同记录
│   └── evidence/
└── README.md
```

提交信息里写清了冲突原因和解决依据：

```
merge: 解决 README 目录结构合并冲突 (PR #15)

冲突原因：docs/readme-week3 与 docs/readme-index 都修改了目录树末尾
「第2周 之后」这一段，前者展开 第3周 的四个子目录，后者只写一行索引。

解决方式：以展开版为主体（信息量更大），吸收索引版的指引作用——
在 docs/ 行注释里注明「含提交清单核对_第3周.md、git/ 协同记录」，
使两份改动的意图都得到保留，而不是简单二选一取其一。
```

### 6.4 过程中的一个插曲

第一次在 `docs/readme-index` 上做文本替换时提示 `nothing to commit`——原因是 README 被 Git 以 **CRLF** 检出（`core.autocrlf=true`），而替换脚本里用的是 `\n`，匹配不上。

第一次在 `docs/readme-week3` 上却成功了，是因为那时文件还是 LF 状态。**同一个脚本，两次结果不同**，根因是行尾符。

处理：把匹配串改成 `\r\n` 后正常。这个坑值得记下来——**跨平台协作时，行尾符会让"看起来一样的文本"匹配失败**。

---

## 七、Issue 记录

本周实际遇到并解决的技术问题（编号为本周内序号，全部已关闭）。

| # | 标题 | 现象 | 根因 | 解决 | 状态 |
|---|---|---|---|---|---|
| 1 | Tez 计数器超限 | 9 路 `union all` 报 `Too many counters: 121 max=120` | 每个 union 分支各起一个 DAG，计数器累加 | 拆成单语句；实测 `tez.counters.max` 等参数无效 | 已关闭 |
| 2 | 周键跨年错乱 | `2024-W01` 的 `week_start`/`week_end` 变成 1/1~12/31 | `dim_date.week_of_year` 把 12/30、12/31 也标为第 1 周 | 自建 `tmp_date_week`：周一 = `date_sub(d, dow-1)`，周序 = `(周一-1月1日)/7+1` | 已关闭 |
| 3 | 中文别名报错 | `cannot recognize input near 'as'` | Hive 标识符只认 `[a-zA-Z_]`，中文别名需反引号 | 全部改 `` as `统计栏名` `` | 已关闭 |
| 4 | 浮点噪声 | GMV 显示 `28757.559999999998` | double 二进制表示误差 | 落库 `round(sum(...),2)`，展示 `cast as decimal(18,2)` | 已关闭 |
| 5 | 动态分区列位置 | 报"分区列必须在 select 末尾" | `insert overwrite ... partition(x)` 要求分区键在最后 | 调整字段顺序 | 已关闭 |
| 6 | 训练集缩水 | 报告写 322 天，脚本输出 307 天 | `dropna()` 把画图列 `ma30` 也算进去了 | 改 `dropna(subset=FEATURES)` | 已关闭 |
| 7 | 归因符号错误 | 降幅贡献显示 `+24.7%` | 格式化用了 `+` 号 | 去掉符号，改列名 | 已关闭 |
| 8 | pyhive 连不上 | `TSocket read 0 bytes` | 该镜像用 SASL PLAIN，不是 NOSASL | `HIVE_AUTH=NONE` | 已关闭 |
| 9 | hive-server 崩溃循环 | 容器反复 Restarting | `/tmp` 残留上次 pid 文件，启动脚本误判"已有实例在跑" | `docker compose up -d --force-recreate hive-server`（数据在 bind mount，不丢） | 已关闭 |
| 10 | 正则拦不住大查询 | `guard_sql` 放过合法但极重的 SELECT | 正则只做语法层校验 | **未修**，记录为已知限制 | 待跟进 |

---

## 八、反思：这套流程哪里还不到位

| 问题 | 说明 | 改进 |
|---|---|---|
| **单人项目，"协同"名不副实** | 没有第二个人类 reviewer，Code Review 是自己看自己，盲区必然存在 | 找同学互换 review；或至少隔一天再看自己的 diff |
| **PR 没有真正走 GitHub Web 界面** | 分支已推送到远端，但未在 GitHub 上点"New pull request"（本机无 `gh` CLI，也没有配置 token） | 用 `git request-pull` 生成了真实摘要作为替代证据；如需真实 PR，可在 GitHub 网页手动创建 |
| **Issue 没有用 GitHub Issues** | 同上原因，记录在文档里而非 Issue 系统 | 后续可把本表直接导入 Issues |
| **合并冲突是"设计"出来的** | 不是自然发生的，是为了演练流程 | 真实多人协作时冲突会自然出现，但解决方法是同一套 |
| **提交粒度偏粗** | `47919d1` 一次提交了 18 张表 + 4 个脚本 + 4 篇文档 | 应按"建表 / 装载 / 校验 / 文档"拆成 4~5 个提交 |

---

## 九、为什么这些记录值得留

答辩时最容易被问的问题不是"你会不会 git"，而是**"你怎么证明这些东西是你一步步做出来的，不是最后一次性堆上去的"**。

这套记录能回答：

- `git log --graph` 能看到 4 条分支和 5 个合并节点；
- 每个 merge commit 都能追到具体的 PR 编号；
- `git request-pull` 的输出是命令生成的真实差异摘要，不是手写；
- 冲突的原始标记（`<<<<<<<`）留在 `git/merge_conflict_raw.txt` 里，能证明冲突真实发生过；
- Issue 表里 10 个问题，每一个都能在代码或文档里找到对应的修改痕迹。

**唯一不能证明的是"有两个人在协作"**——这一点如实写在第八节，不粉饰。

---

## 十、复现方式

```powershell
cd D:\xiangmushixun-bde

# 看分支结构
git log --oneline --graph -12

# 看某次 PR 的完整改动
git show 5d23604 --stat
git show cd471ad

# 看冲突是怎么解决的
git show 3b93f20

# 重新生成 PR 摘要
git request-pull 47919d1 origin feat/ai-insight
```

远端分支：`main`、`feat/llm-multi-provider`、`feat/ai-insight`、`docs/readme-week3`、`docs/readme-index`（均已推送）。