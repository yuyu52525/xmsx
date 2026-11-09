# 云购生活 · NL2SQL 接口说明（第 3 周）

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0（第 3 周） |
| 依据 | 《第 3 周任务书》交付物 4：NL2SQL 接口代码（Schema 抽取 + LangChain + Prompt） |
| 代码目录 | `第3周/py/` |
| 入口 | `nl2sql.py` |
| 运行证据 | `第3周/evidence/nl2sql_schema.json`、`nl2sql_schema.md`、`nl2sql_demo.txt`、`llm_selftest.txt` |

---

## 一、目标与设计原则

**目标**：让不懂 SQL 的业务同事用中文提问，系统自动生成 Hive SQL 并返回结果。

设计上遵守三条原则：

1. **Schema 必须自动抽取，不能手写**——表结构每周都在变（本周就新增 18 张表），手写描述一定会和真实结构脱节，而脱节的后果是模型生成"看起来对、跑起来错"的 SQL。
2. **只读、必须有边界**——生成的 SQL 只允许 `SELECT`，自动补 `LIMIT`，执行前再做一次正则校验。**不信任模型输出**是这个模块的第一原则。
3. **查询范围限定在 ADS 层**——ADS 已经按业务场景聚合好、维度名已贴好，模型不需要写 JOIN。这是把"模型容易出错的地方"从设计上消除掉，而不是靠 Prompt 祈祷它别错。

---

## 二、整体链路

```
用户中文提问
      │
      ▼
① 抽取元信息      schema_extract.py  →  Hive metastore（describe）
      │                                产出 13 张表 / 151 个字段
      ▼
② 组装 Prompt     ChatPromptTemplate（系统约束 7 条 + 真实 Schema + 2 个 Few-shot）
      │
      ▼
③ 调大模型        RunnableLambda → llm_client.chat()（DeepSeek，OpenAI 兼容）
      │
      ▼
④ 解析输出        StrOutputParser
      │
      ▼
⑤ SQL 清洗        cleanse_sql()  去 ``` 围栏 / 去 "SQL：" 前缀 / 只取第一条
      │
      ▼
⑥ 安全校验        guard_sql()    只读白名单 / 禁止写操作 / 必须有库名前缀 / 无 LIMIT 自动补 200
      │
      ▼
⑦ 执行            pyhive → HiveServer2 → DataFrame → 打印
```

链路由 **LangChain LCEL**（`prompt | RunnableLambda | StrOutputParser`）组织，LangChain 版本 1.4.9。

第 ③ 步被包成 `RunnableLambda`，好处是**换模型只改这一个函数**：DeepSeek、Qwen、本地 vLLM，只要兼容 OpenAI 协议就能直接替换，链路的其余部分不动。

---

## 三、文件说明

| 文件 | 职责 |
|---|---|
| `hive_client.py` | pyhive 连接封装：`get_conn()` / `query_df()` / `ping()` |
| `llm_client.py` | 大模型调用 + 密钥管理 + 连通性自检（`python llm_client.py`） |
| `schema_extract.py` | 从 metastore 抽 Schema，输出 JSON / Markdown 两份 |
| `nl2sql.py` | 主入口：Prompt + 链路 + 校验 + 执行 |
| `.env.example` | 配置模板（复制为 `.env` 使用，`.env` 已在 `.gitignore`） |

---

## 四、Schema 抽取（第 ① 步）

### 4.1 抽取范围

只暴露"业务可直接问"的 13 张表：

| 库 | 表 | 说明 |
|---|---|---|
| `ydsh_ads` | 9 张 ADS | 已经聚合好，**提问优先用这些** |
| `ydsh_dwd` | `dim_user` / `dim_product` / `dim_store` / `dim_date` | 需要按地区、品类、门店下钻时用 |

**故意不暴露**：ODS 层原始表、`stg_` 中间表。原因：这些表字段是英文缩写或原样落库的编码（如 `province_code`），没有业务语义，模型极易拼错；即便拼音对了，也绕过了清洗逻辑，查出来的可能是脏数据。

### 4.2 抽取结果

实测：**13 张表、151 个字段**，全部字段的中文注释直接来自 `describe` 的 comment 列，没有人工转写。

```
抽取 ydsh_ads.ads_kpi_overview ... (13 张表)
完成：13 张表、151 个字段
```

产物：

- `evidence/nl2sql_schema.json` —— 程序读取，含表名、描述、行数、字段（名/类型/注释）
- `evidence/nl2sql_schema.md` —— 人看，每表一段表格

### 4.3 拼进 Prompt 的格式

```
### ydsh_ads.ads_kpi_month  —— 月度 KPI，含环比与同比，约 12 行
  stat_month string  -- 统计月份 yyyy-MM
  gmv double  -- GMV（元）
  ...
```

**带上行数**（"约 12 行"）是有意的：它能让模型判断"这张表是不是月度粒度"，避免在 12 行的月表上写日级过滤条件。

---

## 五、Prompt 设计（第 ② 步）

### 5.1 系统约束（7 条硬性规则）

| # | 约束 | 解决的问题 |
|---|---|---|
| 1 | 只能生成 `SELECT` / `WITH` | 防止 DROP / DELETE |
| 2 | 只能用 Schema 里出现的字段 | 防止幻觉字段名 |
| 3 | 表名必须带库名 | 防止在 `default` 库瞎查、防止同名表歧义 |
| 4 | 金额用 `cast(round(x,2) as decimal(18,2))` | 防止输出 `3.611668706E7` 这种科学计数法 |
| 5 | 说明数据只有 2024 年 1—12 月 | 防止模型编造 2025 年数据 |
| 6 | 必须带 LIMIT（≤200） | 防止一问就全表扫 |
| 7 | 只输出 SQL，不要解释、不要代码块 | 减少解析成本（后面还有兜底清洗） |

### 5.2 Few-shot 示例（2 个）

示例不是随便选的，覆盖了两类最容易出错的问题：

**示例 1（单值聚合 + 中文过滤条件）**

```
问题：广东省 2024 年 12 月的销售额是多少？
SQL：select cast(round(sum(gmv), 2) as decimal(18, 2)) as gmv
     from ydsh_ads.ads_province_sales
     where province = '广东省' and stat_month = '2024-12';
```

它教会模型：中文字段值要加单引号、月份格式是 `yyyy-MM`、结果要 `cast`。

**示例 2（分组 + 排序 + 取前 N）**

```
问题：销量最高的前 5 个品类是哪些？
SQL：select category, sum(item_qty) as total_qty
     from ydsh_ads.ads_category_rank
     group by category
     order by total_qty desc
     limit 5;
```

它教会模型：ADS 表是月度的，问"全年"要 `group by` 汇总；排序要用别名。

### 5.3 一个刻意的设计：不给 JOIN 示例

因为 ADS 层已经把维度名贴好了，**这个场景下正确的 SQL 里根本不该出现 JOIN**。给 JOIN 示例等于暗示"可以 JOIN"，反而会诱导模型去拼 `dim_product`，把简单问题复杂化。**约束的正确用法是"不给错误留示范"。**

---

## 六、SQL 安全校验（第 ⑥ 步）

模型输出不可信，所以执行前有独立的 `guard_sql()`：

| 检查 | 规则 | 失败处理 |
|---|---|---|
| 只读 | 必须以 `select` / `with` 开头 | 抛 `ValueError`，不执行 |
| 禁写 | 正则匹配 `insert/update/delete/drop/alter/truncate/create/merge/grant/revoke/load/overwrite` | 抛 `ValueError` |
| 库名前缀 | `from` / `join` 后面不能是裸表名 | 抛 `ValueError` |
| 行数上限 | 无 `limit` 时自动追加 `limit 200` | 自动补全 |

实测：5 个测试用例**全部被自动补上了 `limit 200`**，说明这条兜底确实在工作。

> 局限性要说清楚：这套校验是**正则层面的**，能挡住"直接写 DROP"和"忘记加 LIMIT"，但挡不住"用合法 SELECT 写出笛卡尔积把集群拖垮"。生产环境应当再加查询超时、扫描行数阈值、以及独立的只读账号（Hive 侧 `SET ROLE` 或 Ranger 授权）。**代码里的正则只是第一道闸，不是唯一一道。**

---

## 七、测试结果

### 7.1 链路验证方式（重要说明）

**当前环境没有配置大模型 API Key**，因此第 ③ 步（真实调用模型）**未能端到端验证**。为不阻塞其余环节的验证，`nl2sql.py` 提供了两种模式：

| 模式 | 命令 | 验证了什么 | 没验证什么 |
|---|---|---|---|
| `--demo` | `python nl2sql.py --demo` | ①Schema 抽取 ⑤清洗 ⑥校验 ⑦执行 全通 | **③模型生成**（用预置 SQL 代替） |
| 真实模式 | `python nl2sql.py "问题"` | 全链路 | 需先配 Key |

`--demo` 模式在输出开头就明确打印"生成的 SQL 是人工预置的参考答案，不是大模型输出"，**不冒充模型结果**。

填入 Key 后的验证方式：

```powershell
copy .env.example .env      # 然后把 DEEPSEEK_API_KEY 改成真实 Key
python llm_client.py        # 先验证连通性（会打印 usage 与 finish_reason）
python nl2sql.py "广东省上月销售额是多少？"
```

`llm_client.py` 的自检会打印 `id / model / finish_reason / usage`，能区分"Key 错"、"模型名错"、"额度耗尽"三种情况，不用盲猜。

### 7.2 五个测试用例（`--demo` 实测结果）

| # | 问题 | 生成的 SQL（要点） | 返回结果 |
|---|---|---|---|
| 1 | 广东省上月销售额是多少？ | `ads_province_sales where province='广东省' and stat_month='2024-12'` | **171,556.38 元**，73 单 |
| 2 | 销量最高的前 5 个品类是哪些？ | `ads_category_rank group by category order by total_qty desc limit 5` | 运动户外 15,790 件 / 数码家电 14,650 / 图书文娱 13,227 / 服饰鞋包 13,170 / 食品生鲜 13,027 |
| 3 | 2024 年 12 月的 GMV、订单量和客单价是多少？ | `ads_kpi_month where stat_month='2024-12'` | GMV **3,111,746.74**，订单 1,236，客单价 **2,517.59** |
| 4 | 哪个省的人均消费（ARPU）最高？ | 子查询 `avg(arpu) group by province order by desc limit 5` | 上海市 4,440.43 / 安徽省 4,420.75 / 山东省 4,403.61 / 四川省 4,374.93 / 浙江省 4,354.26 |
| 5 | 各渠道在 12 月的销售额占比是多少？ | `ads_channel_month where stat_month='2024-12' order by gmv desc` | 小程序 826,020.64（26.55%）/ 门店 773,904.28（24.87%）/ APP 763,425.08（24.53%）/ PC官网 748,396.74（24.05%） |

全部命中，无 SQL 报错。第 3 题的结果与 `KPI指标结果表.md` 第二节 2024-12 行完全一致（3,111,746.74 / 1,236 / 2,517.59），说明 NL2SQL 取数与人工写 SQL 口径一致。

### 7.3 一个值得注意的模糊问题

第 4 题"哪个省的人均消费（ARPU）最高"，示例用了 `avg(arpu)`（对 12 个月的月 ARPU 再平均），得到上海市 4,440.43。但也可以理解为"该省全年 GMV ÷ 该省全年买家数"，结果会不同。

**这不是 SQL 生成错误，是自然语言本身的歧义。** 处理这类问题的正确做法不是让模型猜，而是：

- 在该省/该指标的 Prompt 上下文里写清口径定义；或
- 让 NL2SQL 在遇到多口径指标时**主动反问**，而不是直接给一个可能答非所问的数。

后者需要多轮对话能力，本周未实现，列为改进项。

---

## 八、密钥管理（本周安全要求）

| 规范 | 落地方式 |
|---|---|
| Key 不进代码 | 全部从 `.env` / 环境变量读取，源码里没有任何真实 Key |
| `.env` 不进 Git | 仓库根 `.gitignore` 第 7 行已有 `.env` |
| 提供模板 | `.env.example` 只放占位符 `sk-your-key-here` |
| 缺 Key 明确报错 | `LLMNotConfigured` 异常 + 提示复制模板，不静默返回空串 |
| 可脱敏查看 | `python llm_client.py --mask` 只显示前 6 位与后 4 位 |
| 泄露可自查 | `git status` 看不到 `.env`；`git log -p` 搜不到 `sk-` |

---

## 九、局限与改进方向

| 局限 | 影响 | 改进 |
|---|---|---|
| **未做真实 LLM 调用验证** | 只能证明链路通，不能证明模型生成质量 | 配 Key 后跑 20 条问题集，人工评估准确率 |
| 单轮问答，无上下文 | 追问"那上个月呢"无法理解 | 引入对话历史（`ChatPromptTemplate` 的 `MessagesPlaceholder`） |
| 无多口径澄清机制 | ARPU 这类模糊指标只能给一种解释 | 置信度低时主动反问 |
| 正则校验可被绕开 | 合法 SELECT 也可能写出超大查询 | 加超时、扫描行数阈值、只读账号 |
| 无结果解释 | 只给表格不给结论 | 接 `ai_insight.py`，把结果喂给模型写一句话解读 |
| Schema 全量塞进 Prompt | 151 字段约 3K token，表变多会爆上下文 | 按问题先做表召回，只塞相关 2~3 张表 |

---

## 十、复现方式

```powershell
cd D:\xiangmushixun-bde\第3周\py

# 1. 抽取 Schema（约 40 秒，写 evidence/）
python schema_extract.py

# 2. 看链路是否通（无需 Key）
python nl2sql.py --demo

# 3. 看拼好的 Schema 文本长什么样
python nl2sql.py --schema

# 4. 配 Key 后走真实链路
copy .env.example .env
python llm_client.py                      # 连通性自检
python nl2sql.py "广东省上月销售额是多少？"
```

> 依赖：`pyhive`、`thrift`、`openai`、`langchain-core`、`python-dotenv`、`pandas`。