# 云购生活 · API 配置指南

| 项目 | 内容 |
|---|---|
| 项目名称 | 云购生活新零售企业 · 企业级数据仓库与经营分析可视化系统 |
| 团队 / 作者 | 乐天（余天乐，20230308098） |
| 文档版本 | v5.0（项目级：密钥配置 + 接口说明 + 调用示例 + 常见问题） |
| 编写日期 | 2026-11-23 |
| 前序版本 | 第 3 周《大模型API申请与配置教程》《NL2SQL接口说明》、第 4 周《第4周_API配置指南》 |
| 配套文件 | `.env.example`、`docker-compose.yml`、`第4周/py/llm_client.py`、`第4周/py/nl2sql.py`、`第4周/py/api_server.py` |

---

## 一、先分清：本项目有 5 类敏感信息

| 类别 | 变量 | 用途 | 存放 | 泄露后果 |
|---|---|---|---|---|
| 大模型 Key | `LLM_API_KEY` | NL2SQL 调模型 | 根目录 `.env` → 注入 app 容器 | 额度被刷（本项目用免费档，主要是耗尽） |
| Superset 会话密钥 | `SUPERSET_SECRET_KEY` | 签名 session / token | 根目录 `.env` | 可伪造登录态，等同拿到管理员 |
| MySQL root | `MYSQL_ROOT_PASSWORD` | 初始化元数据库、建库 | 根目录 `.env` | 元数据被改，Hive 直接打不开 |
| MySQL 只读账号 | `MYSQL_RO_PASSWORD` | Superset 连业务库 | 根目录 `.env` | 只能读 61 行快照表，影响有限（这正是不用 root 的原因） |
| ClickHouse 密码 | `CLICKHOUSE_PASSWORD` | 数据服务读缓存 | 根目录 `.env` | 缓存副本被读；不含源数据 |

> **一句话原则**：密钥只存在两处——你本地的 `.env` 和容器的环境变量。**仓库里、代码里、镜像里、日志里都不出现明文。**

---

## 二、三层配置模型

```
① 模板层   .env.example       ← 进 Git，只有占位符，说明"需要填什么"
        ↓ 复制并填值
② 实例层   .env               ← 不进 Git（.gitignore 已排除），只在本机
        ↓ docker compose 读取
③ 运行层   容器环境变量        ← docker compose up 时注入，容器内不落盘
```

三层各管一件事：模板层让"换机器怎么配"有据可查；实例层把真实值隔离在版本库外；运行层保证代码只读 `os.getenv()`，**任何一行代码都不含明文密钥**，也就不存在"把 Key 写进代码后被提交"的路径。

### 2.1 代码侧取值方式

所有入口统一走环境变量（`第4周/py/llm_client.py`）：

```python
def _pick(*names: str, default: str = "") -> str:
    """按顺序取第一个非空环境变量，便于新旧变量名共存。"""
    for name in names:
        val = os.getenv(name, "").strip()
        if val:
            return val
    return default

def _api_key() -> str:
    load_config()
    return _pick("LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ZHIPU_API_KEY")
```

好处是**换供应商不改代码**：只要对方兼容 OpenAI 协议，改 `.env` 三个变量就能切。

### 2.2 `.env` 多路径查找（本地开发与容器部署两不误）

```python
_ENV_CANDIDATES = [
    Path(__file__).resolve().parent / ".env",                      # 第4周/py/.env
    Path(__file__).resolve().parent.parent / ".env",               # 第4周/.env
    Path(__file__).resolve().parent.parent.parent / ".env",        # 仓库根 .env  ← 容器/本地都走这条
    Path(__file__).resolve().parent.parent.parent / "第3周" / "py" / ".env",  # 复用第 3 周配置
]
```

容器里走第 3 条（根目录 `.env` 由 compose 注入环境变量，`.env` 文件本身不挂进容器）；本地开发同样走第 3 条，**不需要把 Key 复制到各周目录**——少一份副本就少一个泄露点。

---

## 三、配置项逐条说明

### 3.1 数据库与服务

| 变量 | 默认 | 说明 | 修改后需要 |
|---|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `root` | MySQL root 密码 | 重建 `mysql`（依赖它的 `hive-metastore`/`superset`/`api` 一起重建） |
| `MYSQL_USER` / `MYSQL_PASSWORD` | `hive` / `hive` | Hive 元数据库账号 | 重建 `hive-metastore` |
| `MYSQL_RO_PASSWORD` | `ydsh_ro_2024` | Superset 连业务库的**只读**账号 | 重建 `mysql-init` 后重跑 `superset-init` |
| `CLICKHOUSE_USER` / `_PASSWORD` | `ydsh` / `ydsh123` | 数据服务连缓存库 | 重建 `clickhouse` + `api` |
| `CLICKHOUSE_DB` | `ydsh_ads` | 副本库名 | 重跑导出脚本 |
| `DATA_BACKEND` | `auto` | `auto` 先试 CH、连不上回落 Hive；可强制 `hive` / `clickhouse` | 重启 `api` |
| `CACHE_TTL` | `10` | 接口进程内缓存秒数，`0` 关闭（压测用） | 重启 `api` |
| `API_PORT` | `8000` | 本地直跑 `api_server.py` 时的端口 | 重启进程 |

### 3.2 Hive 连接（脚本侧）

| 变量 | 默认 | 说明 |
|---|---|---|
| `HIVE_HOST` / `HIVE_PORT` | `localhost` / `10000` | 宿主机直连；容器内为 `hive-server` / `10000` |
| `HIVE_USER` | `hive` | — |
| `HIVE_AUTH` | `NONE` | **必须是 NONE**；填 `NOSASL` 会报 `TSocket read 0 bytes` |
| `HIVE_DB` | `ydsh_ads` | 默认库 |
| `HIVE_TIMEOUT` | `120` | 单次查询超时（秒），Hive 冷启动第一条要放宽 |

### 3.3 大模型

| 变量 | 默认 | 说明 | 修改后需要 |
|---|---|---|---|
| `LLM_API_KEY` | 空 | 大模型 Key；**空则 Streamlit 走演示模式** | 重启 `app` |
| `LLM_BASE_URL` | 智谱地址 | OpenAI 兼容接口地址 | 重启 `app` |
| `LLM_MODEL` | `glm-4-flash-250414` | 模型名（各家命名不同，别照抄） | 重启 `app` |
| `ECHARTS_SRC` | `http://localhost:8000/assets/echarts.min.js` | Streamlit 嵌图用，**由浏览器加载** | 重启 `app` |

> `ECHARTS_SRC` 最容易配错：它由**浏览器**去加载，必须是宿主机可达地址。写成 `http://api:8000/...` 在容器内能通、在浏览器里 404，表现为"Streamlit 图表空白"。

---

## 四、大模型接入：四种方案与切换

只要兼容 OpenAI 协议即可，不绑定任何一家：

| 方案 | `LLM_BASE_URL` | `LLM_MODEL` | 获取地址 | 特点 |
|---|---|---|---|---|
| 智谱 GLM-4-Flash | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash-250414` | open.bigmodel.cn | 免费档，**本项目采用**；一次 NL2SQL 约 3.5k tokens |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` | platform.deepseek.com | 中文 SQL 强，按量计费 |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` | siliconflow.cn | 有免费额度，可选模型多 |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` | ollama.com | 完全离线，无需 Key（填占位串） |

### 4.1 切换步骤（以切到 DeepSeek 为例）

1. 编辑 `.env`：

```ini
LLM_API_KEY=sk-你的deepseek密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

2. 重启提问服务：`docker compose up -d app`

3. 连通性自检（只问一句"只回复两个字：连通"，几乎不耗额度）：

```powershell
python 第4周/py/llm_client.py
```

期望输出包含：`[结论] 连通正常，返回格式符合预期`

4. 跑一次真实链路：

```powershell
python 第4周/py/nl2sql.py "各支付方式的销售额占比是多少？"
```

### 4.2 首次申请 Key 的流程（智谱）

1. 注册并实名 → 控制台"API Keys" → 新建；
2. 复制 Key（只显示一次）；
3. 填入 `.env` 的 `LLM_API_KEY`，`LLM_BASE_URL` 用上表默认值；
4. `docker compose up -d app`；
5. 按 4.1 第 3、4 步验收。

### 4.3 用量与成本控制

- 每次调用写 `第4周/evidence/llm_usage.log`（时间、模型、输入、输出、合计）；
- 汇总：`python 第4周/py/llm_client.py --usage`；
- 实测：一次 NL2SQL ≈ **3,457 输入 + 94 输出 = 3,551 tokens**（Schema 占绝大部分）；
- 省 token 的办法：把 `nl2sql.py` 的 Few-shot 从 4 条减到 2 条，或只保留 ADS 表进 Schema。

---

## 五、数据服务接口说明（FastAPI，端口 8000）

### 5.1 通用约定

- 所有数据接口返回同一外壳：

```json
{
  "ok": true,
  "backend": "clickhouse",
  "elapsed_ms": 12.4,
  "cached": false,
  "data": [ { ... } ]
}
```

- `backend` 表示本次数据来自哪个引擎（`clickhouse` / `hive`），便于排障；
- 进程内缓存 10 秒（`CACHE_TTL`），`cached: true` 表示命中缓存；
- 交互式文档：http://localhost:8000/api/docs （OpenAPI，可直接点"Try it out"）。

### 5.2 接口清单

| # | 方法 | 路径 | 参数 | 数据源 | 返回行数（实测） |
|---|---|---|---|---|---|
| 1 | GET | `/api/health` | — | — | 1（含 Hive/CH 版本、各表行数） |
| 2 | GET | `/api/kpi` | — | `ads_kpi_overview` | 1 |
| 3 | GET | `/api/month` | — | `ads_kpi_month` | 12 |
| 4 | GET | `/api/daily` | — | `ads_sales_daily` | 366 |
| 5 | GET | `/api/category` | — | `ads_category_rank` | 8 |
| 6 | GET | `/api/province` | — | `ads_province_sales` | 15 |
| 7 | GET | `/api/paytype` | — | `ads_pay_type_month` | 4 |
| 8 | GET | `/api/hour_category` | — | `ads_hour_category` | 192 |
| 9 | GET | `/api/store` | `top`（1–20，默认 10） | `ads_store_rank` | 10 |
| 10 | GET | `/api/rfm` | — | `ads_user_rfm` | 1,000 |
| 11 | GET | `/api/channel` | — | `ads_channel_month` | 4 |
| 12 | GET | `/api/all` | `nocache`（0/1） | 上表 10 项并发 | 全部一次返回 |
| 13 | POST | `/api/ask` | body `{"question": "..."}` | NL2SQL → Hive | 视问题而定 |
| 14 | GET | `/` | — | 静态大屏 `web/index.html` | — |

> `/api/all` 把 10 个请求合成 1 个并在服务端并发执行；`nocache=1` 绕过缓存，**压测必须用它**，否则测到的是缓存耗时。

### 5.3 调用示例

**PowerShell**

```powershell
# 健康检查
Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json -Depth 5

# 门店 Top5
Invoke-RestMethod "http://localhost:8000/api/store?top=5" | ConvertTo-Json -Depth 4

# 自然语言提问
$body = @{ question = "各支付方式的销售额占比是多少？" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/ask `
  -ContentType "application/json; charset=utf-8" -Body $body | ConvertTo-Json -Depth 4
```

**curl（Windows 10+ 自带 `curl.exe`）**

```bash
curl.exe "http://localhost:8000/api/kpi"
curl.exe -X POST "http://localhost:8000/api/ask" -H "Content-Type: application/json" ^
  -d "{\"question\":\"广东省 2024 年 12 月销售额是多少？\"}"
```

**Python**

```python
import requests

r = requests.get("http://localhost:8000/api/kpi", timeout=30).json()
print(r["backend"], r["data"][0]["gmv"])          # clickhouse 36116687.06

r = requests.post("http://localhost:8000/api/ask",
                  json={"question": "各渠道的 GMV 占比是多少？"}, timeout=120).json()
print(r["sql"])                                    # 模型生成的 SQL（可审计）
for row in r["data"]:
    print(row)
```

### 5.4 错误码

| 状态码 | 含义 | 处理 |
|---|---|---|
| 200 | 正常 | — |
| 400 | `/api/ask` 的 `question` 为空 | 传非空字符串 |
| 422 | 参数校验失败（如 `top=0`） | 按约束传参 |
| 500 | NL2SQL 内部异常（模型返回不可解析） | 看 `docker compose logs api`，换更明确的问题 |
| 503 | 后端查询失败（Hive/CH 不可用） | 看 `/api/health`，确认后端与容器状态 |

---

## 六、NL2SQL 的配置与边界

### 6.1 三种调用方式

| 方式 | 命令 | 场景 |
|---|---|---|
| 命令行 | `python 第4周/py/nl2sql.py "问题"` | 调试、出证据 |
| REST | `POST /api/ask` | 大屏/外部系统集成 |
| 网页 | http://localhost:8501 | 业务方自助 |

### 6.2 `guard_sql` 的四条硬规则（配置在 `nl2sql.py`）

1. 必须以 `SELECT` 或 `WITH` 开头；
2. 禁止 `insert / update / delete / drop / alter / create / truncate / grant / revoke / load / insert overwrite` 等写关键字；
3. 表名必须带库前缀（`ydsh_ads.` 等），防止落到 `default` 库；
4. 自动补 `LIMIT 200`，防止误拉全表。

被拦下时返回的是"拒绝原因 + 原始 SQL"，不会静默改写成另一句话。

### 6.3 一个必须记住的坑：占比分母

第 3 周出现过"12 月微信占比算成 2.43%，四种支付加起来才 9.4%"。原因是示例 SQL 里把分母写死成**全年**常数，模型照抄。修法是：**用窗口函数现算当月分母，并在 System Prompt 里加硬约束**。这类"看起来对、加起来不对"的问题，一定要有"各分项加总 = 100%"的校验。

---

## 七、权限最小化（不是口号，是具体配置）

### 7.1 Superset 连 MySQL 用只读账号

`mysql-init` 建库时同步建账号：

```sql
CREATE USER IF NOT EXISTS 'ydsh_ro'@'%' IDENTIFIED BY '<MYSQL_RO_PASSWORD>';
GRANT SELECT ON ydsh_mysql.* TO 'ydsh_ro'@'%';
```

数据源 URI：

```
mysql+pymysql://ydsh_ro:<MYSQL_RO_PASSWORD>@mysql:3306/ydsh_mysql?charset=utf8mb4
```

为什么值得单独建账号：Superset 的连接串**存在元数据库里、能在 UI 里被管理员看到**。用 root 等于把 root 密码摊开给所有能进 Superset 的人；用只读账号，最坏情况也只是读到 61 行 KPI 快照。

> Superset 自己的元数据库（`superset_meta`）必须用可写账号，那是它存图表定义的地方，与"数据源只读"是两件事。

### 7.2 Hive 侧

教学环境未开认证（`hive.server2.authentication=NONE`），这是有意的：本地单机、只在自己机器上跑。生产环境应做三件事：开 Kerberos/LDAP、用 Ranger 做库表级授权、给分析账号只授 `SELECT`。本项目已在应用层做了第一道防线（`guard_sql`）。

### 7.3 ClickHouse 侧

只存 ADS 结果集副本，除 8123/9000 外不暴露端口。生产可加 `readonly=1` 的 profile 账号；本期未做（缓存库丢失可随时重建，风险低）。

---

## 八、密钥轮换 SOP

以"怀疑 LLM Key 泄露"为例，标准 5 步：

| 步骤 | 动作 | 验证 |
|---|---|---|
| 1 | 供应商控制台作废旧 Key，生成新 Key | 旧 Key 调用返回 401 |
| 2 | 更新本机 `.env` 的 `LLM_API_KEY` | `python 第4周/py/llm_client.py --mask` 显示新 Key 前 6 位 |
| 3 | 重启受影响服务 | `docker compose up -d app` |
| 4 | 跑连通性 + 业务链路 | `llm_client.py`、`nl2sql.py "..."` |
| 5 | 检查历史是否已泄露 | `git log -S "旧Key前6位" --oneline`（应为空） |

数据库密码轮换同理，但要按依赖顺序：改 `.env` → 重建 `mysql`（或 `ALTER USER`）→ 重建依赖它的 `hive-metastore` / `superset` / `api`。

---

## 九、泄露应急：如果 Key 已经进了 Git

仅删除文件再提交是**无效**的——历史里还在。正确顺序：

1. **立刻在供应商侧作废该 Key**（最重要，别先改代码）；
2. 从工作区删除：`git rm --cached .env`；
3. 确认 `.gitignore` 已含 `.env`；
4. 已推送远端则用 `git filter-repo` 或 BFG 清理历史后强制推送；
5. 通知所有克隆过仓库的人重新拉取（他们本地历史仍有旧 Key）；
6. 复盘：本项目通过"密钥只走环境变量 + 模板不含真实值"从机制上避免。

---

## 十、配置自检清单

| # | 检查 | 命令 | 期望 |
|---|---|---|---|
| 1 | `.env` 未被 Git 跟踪 | `git check-ignore -v .env` | 输出 `.gitignore:N:.env` |
| 2 | 仓库内无明文 Key | `git grep -n "sk-" -- .` | 无结果（除文档示例） |
| 3 | Key 已就位 | `python 第4周/py/llm_client.py --mask` | `Key 已配置：True` |
| 4 | 模型可用 | `python 第4周/py/llm_client.py` | `连通正常，返回格式符合预期` |
| 5 | 服务身份正确 | `/api/health` | `backend` 为 `clickhouse` 或 `hive` |
| 6 | Superset 数据源只读 | Superset → 设置 → 数据库连接 | 用户名为 `ydsh_ro` |
| 7 | 容器内无 `.env` | `docker exec ydsh-app ls -a /app` | 列表里没有 `.env` |
| 8 | 端口连通 | `Test-NetConnection 127.0.0.1 -Port 8000` | `TcpTestSucceeded : True` |

---

## 十一、常见错误码与处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `401 Not authorized`（调模型） | Key 错/过期，或与 Base URL 不匹配 | 核对 Key 与供应商；别把智谱 Key 配到 DeepSeek 地址 |
| `404 model not found` | `LLM_MODEL` 名字不对 | 按第四节表格核对模型名 |
| `429 rate limit` | 免费档限流或额度用尽 | 降并发、换 Key 或换供应商；**压测不要打模型接口** |
| `APIConnectionError` | 网络不通（本地 Ollama 未启最常见） | 本地先 `ollama serve`；云端检查代理 |
| Streamlit 图表空白 | `ECHARTS_SRC` 指向容器名 | 改成 `http://localhost:8000/...` |
| Superset 看不到 MySQL 表 | 只读账号未授权到该库 | 重跑 `GRANT SELECT ON ydsh_mysql.*` |
| `/api/*` 返回 503 | 后端不可用 | 看 `/api/health`；`docker compose ps` 确认 hive-server/clickhouse |
| `TSocket read 0 bytes` | `HIVE_AUTH` 不是 `NONE` | 改回 `NONE` |
| `No module named 'thrift_sasl'` | 依赖不全 | 装 `thrift_sasl` + `pure-sasl` |
| ClickHouse `516 Authentication failed` | 脚本没加载 `.env`，用 `default` 空密码连 | 入口处 `load_dotenv(仓库根/.env)` |