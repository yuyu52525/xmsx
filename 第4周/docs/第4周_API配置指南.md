# 云购生活数仓 · 第 4 周 API 配置指南

> 配套：《第4周_部署手册》　｜　涉及文件：`.env.example`、`docker-compose.yml`、`第4周/py/llm_client.py`
> 主题：密钥管理、大模型接入、权限最小化、轮换与应急

---

## 一、先分清：本项目有 5 类敏感信息

| 类别 | 变量 | 用途 | 存放 | 泄露后果 |
|---|---|---|---|---|
| 大模型 Key | `LLM_API_KEY` | NL2SQL 调模型 | 根目录 `.env` → 注入 app 容器 | 被盗刷额度（本项免费档，主要是额度耗尽） |
| Superset 会话密钥 | `SUPERSET_SECRET_KEY` | 签名 session / token | 根目录 `.env` | 可伪造登录态，等同拿到管理员 |
| MySQL root | `MYSQL_ROOT_PASSWORD` | 初始化元数据库、建库 | 根目录 `.env` | 元数据被改，Hive 直接打不开 |
| MySQL 只读账号 | `MYSQL_RO_PASSWORD` | Superset 连业务库 | 根目录 `.env` | 只能读快照表，影响有限（这正是不用 root 的原因） |
| ClickHouse 密码 | `CLICKHOUSE_PASSWORD` | 数据服务读缓存 | 根目录 `.env` | 缓存副本被读；不含源数据 |

**一句话原则**：密钥只存在于两处 —— 你本地的 `.env`，和容器的环境变量。**仓库里、代码里、镜像里都不出现明文。**

---

## 二、三层配置模型（为什么这样设计）

```
① 模板层   .env.example       ← 进 Git，只有占位符，给同学/老师看"需要填什么"
        ↓ 复制并填值
② 实例层   .env               ← 不进 Git（.gitignore 第 10 行已排除），只在本机
        ↓ docker compose 读取
③ 运行层   容器环境变量        ← docker compose up 时注入，容器内不落盘
```

三层各管一件事：

- 模板层让"换一台机器怎么配"有据可查，不用问人；
- 实例层把真实值隔离在版本库之外，`git status` 永远看不到；
- 运行层保证代码只读 `os.getenv()`，**任何一行代码都不含明文密钥**，也就不存在"把 Key 写进代码后被提交"的路径。

### 2.1 代码侧怎么取值

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

这样做的好处是**换供应商不改代码**：只要对方兼容 OpenAI 协议，改 `.env` 三个变量就能切换。

### 2.2 `.env` 多路径查找（本地开发与容器部署两不误）

```python
_ENV_CANDIDATES = [
    Path(__file__).resolve().parent / ".env",                      # 第4周/py/.env
    Path(__file__).resolve().parent.parent / ".env",               # 第4周/.env
    Path(__file__).resolve().parent.parent.parent / ".env",        # 仓库根 .env
    Path(__file__).resolve().parent.parent.parent / "第3周" / "py" / ".env",  # 复用第 3 周配置
]
```

容器里走第 3 条（根目录 `.env` 由 compose 注入环境变量，`.env` 文件本身不挂进容器）；本地开发走第 4 条，直接复用第 3 周已有的 Key，**不需要把 Key 复制到第 4 周目录**（少一份副本就少一个泄露点）。

---

## 三、配置项逐条说明

| 变量 | 默认 | 说明 | 修改后需要 |
|---|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `root` | MySQL root 密码 | 重建 mysql + superset + api |
| `MYSQL_USER` / `MYSQL_PASSWORD` | `hive` / `hive` | Hive 元数据库账号 | 重建 hive-metastore |
| `MYSQL_RO_PASSWORD` | `ydsh_ro_2024` | Superset 连业务库的**只读**账号 | `docker compose up -d mysql-init` 后重跑 superset-init |
| `SUPERSET_SECRET_KEY` | 无（必填） | 会话签名密钥，改动会让所有人掉登录 | 重启 superset |
| `SUPERSET_ADMIN_USER` / `_PASSWORD` | `admin` / `admin` | 管理员账号（答辩建议改） | 重启 superset（密码需在 UI 里改） |
| `CLICKHOUSE_USER` / `_PASSWORD` | `ydsh` / `ydsh123` | 数据服务连缓存库 | 重建 clickhouse + api |
| `DATA_BACKEND` | `auto` | `auto` 先试 CH、连不上回落 Hive；可强制 `hive` / `clickhouse` | 重启 api |
| `CACHE_TTL` | `10` | 接口进程内缓存秒数，`0` 关闭（压测用） | 重启 api |
| `LLM_API_KEY` | 空 | 大模型 Key，空则 Streamlit 走演示模式 | 重启 app |
| `LLM_BASE_URL` | 智谱地址 | OpenAI 兼容接口地址 | 重启 app |
| `LLM_MODEL` | `glm-4-flash-250414` | 模型名 | 重启 app |
| `ECHARTS_SRC` | `http://localhost:8000/assets/echarts.min.js` | Streamlit 内嵌图表加载的 js 地址（**浏览器**访问，不是容器名） | 重启 app |

> `ECHARTS_SRC` 是最容易配错的一项：它由浏览器去加载，所以必须是宿主机可达地址。写成 `http://api:8000/...` 在容器里能通、在浏览器里 404。

---

## 四、大模型接入：四种方案与切换方法

本项目不绑定任何一家，只要兼容 OpenAI 协议即可。`.env.example` 里给出了四个模板：

| 方案 | `LLM_BASE_URL` | `LLM_MODEL` | 获取地址 | 特点 |
|---|---|---|---|---|
| 智谱 GLM-4-Flash | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash-250414` | open.bigmodel.cn | 免费档，**本项目采用**；实测一次 NL2SQL 约 3.4k tokens |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` | platform.deepseek.com | 中文 SQL 能力强，按量计费 |
| 硅基流动 | `https://api.siliconflow.cn/v1` | `Qwen/Qwen2.5-7B-Instruct` | siliconflow.cn | 有免费额度，模型可选多 |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:7b` | ollama.com | 完全离线，无需 Key（填占位串） |

### 4.1 切换步骤（以切到 DeepSeek 为例）

1. 编辑 `.env`：

```ini
LLM_API_KEY=sk-你的deepseek密钥
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

2. 重启提问服务：

```powershell
docker compose up -d app
```

3. 连通性自检（不消耗多少 token，只问一句"只回复两个字：连通"）：

```powershell
cd 第4周/py
python llm_client.py
```

期望输出包含：`[结论] 连通正常，返回格式符合预期`。

4. 跑一次真实链路：

```powershell
python nl2sql.py "各支付方式的销售额占比是多少？"
```

### 4.2 用量与成本控制

- 每次调用都写 `第4周/evidence/llm_usage.log`（时间、模型、输入、输出、合计）；
- 汇总：`python llm_client.py --usage`；
- 实测：一次 NL2SQL ≈ 3,457 输入 + 94 输出 = 3,551 tokens（Schema 占了绝大部分）；
- 想省 token：把 `nl2sql.py` 的 `SYSTEM_PROMPT` 里 Few-shot 从 4 条减到 2 条，或改用 `第4周/evidence/nl2sql_schema.json` 里只保留 ADS 表。

---

## 五、权限最小化（不是口号，是具体配置）

### 5.1 Superset 连 MySQL 用只读账号

`mysql-init` 服务建库时同步建账号：

```sql
CREATE USER IF NOT EXISTS 'ydsh_ro'@'%' IDENTIFIED BY '<MYSQL_RO_PASSWORD>';
GRANT SELECT ON ydsh_mysql.* TO 'ydsh_ro'@'%';
```

Superset 的数据源 URI 因此是：

```
mysql+pymysql://ydsh_ro:<MYSQL_RO_PASSWORD>@mysql:3306/ydsh_mysql?charset=utf8mb4
```

为什么值得单独建一个账号：Superset 的连接串是**存在元数据库里、能在 UI 里被管理员看到**的。用 root 等于把 root 密码摊开给所有能进 Superset 的人；用只读账号，最坏情况也只是读到 61 行 KPI 快照。

> 注意：Superset 自己的元数据库（`superset_meta`）必须用可写账号，这是它存图表定义的地方，与"数据源只读"是两件事。

### 5.2 Hive 侧

本项目的 HiveServer2 是教学环境，未开认证（`hive.server2.authentication=NONE`），这是有意的：本地单机、只在自己的机器上跑。
生产环境应做三件事（本手册给出方向，不在本周范围内实施）：开 Kerberos/LDAP 认证、用 Ranger 做库表级授权、给分析账号只授 `SELECT`。项目里的 `nl2sql.guard_sql()` 已经在应用层做了第一道防线（只允许 `SELECT`/`WITH`、禁止写关键字、强制带库名、自动补 `LIMIT 200`）。

### 5.3 ClickHouse 侧

只存 ADS 结果集副本，且 `clickhouse` 容器不对外暴露除 8123/9000 之外的端口。生产可再加 `readonly=1` 的 profile 账号，本周未做（缓存库丢失可随时重建，风险低）。

---

## 六、密钥轮换 SOP

以"怀疑 LLM Key 泄露"为例，标准动作 5 步：

| 步骤 | 动作 | 验证 |
|---|---|---|
| 1 | 供应商控制台作废旧 Key，生成新 Key | 旧 Key 调用返回 401 |
| 2 | 更新本机 `.env` 的 `LLM_API_KEY` | `python llm_client.py --mask` 显示新 Key 前 6 位 |
| 3 | 重启受影响服务 | `docker compose up -d app` |
| 4 | 跑连通性 + 业务链路 | `python llm_client.py`、`python nl2sql.py "..."` |
| 5 | 检查历史是否已泄露 | `git log -S "旧Key前6位" --oneline`（应为空） |

数据库密码轮换同理，但要按依赖顺序：改 `.env` → `docker compose up -d mysql`（或 `ALTER USER`）→ 重建依赖它的服务（hive-metastore / superset / api）。Superset 元数据库密码变了要重跑 `superset db upgrade`，本项目把它放在容器启动命令里，所以重启即生效。

---

## 七、泄露应急：如果 Key 已经进了 Git

仅删除文件再提交是**无效**的——历史里还在。正确顺序：

1. 立刻在供应商侧作废该 Key（这一步最重要，别先忙着改代码）；
2. 从工作区删除：`git rm --cached .env`；
3. 确认 `.gitignore` 已包含 `.env`（本项目第 10 行）；
4. 若已推送到远端，用 `git filter-repo` 或 BFG 清理历史，然后强制推送；
5. 通知所有克隆过仓库的人重新拉取（他们的本地历史里仍有旧 Key）；
6. 复盘：为什么会被提交？本项目已通过"密钥只走环境变量 + 模板文件不含真实值"从机制上避免。

---

## 八、配置自检清单

| 序号 | 检查 | 命令 | 期望 |
|---|---|---|---|
| 1 | `.env` 未被 Git 跟踪 | `git check-ignore -v .env` | 输出 `.gitignore:10:.env` |
| 2 | 仓库内无明文 Key | `git grep -n "sk-" -- .` | 无结果（除文档示例） |
| 3 | Key 已就位 | `python 第4周/py/llm_client.py --mask` | `Key 已配置：True　脱敏：xxxxxx...xxxx` |
| 4 | 模型可用 | `python 第4周/py/llm_client.py` | `连通正常，返回格式符合预期` |
| 5 | 服务身份正确 | http://localhost:8000/api/health | `backend` 为 clickhouse/hive |
| 6 | Superset 数据源只读 | Superset → 设置 → 数据库连接 → 编辑 MySQL | 用户名为 `ydsh_ro` |
| 7 | 容器内无 `.env` | `docker exec ydsh-app ls /app` | 列表里没有 `.env` |

---

## 九、常见错误码与处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `401 Not authorized`（调用模型） | Key 错、过期，或与 Base URL 不匹配 | 核对 Key 与供应商；别把智谱 Key 配到 DeepSeek 地址 |
| `404 model not found` | `LLM_MODEL` 名字不对（各家命名不同） | 按第四节表格核对模型名 |
| `429 rate limit` | 免费档限流或额度用尽 | 降并发、换 Key 或换供应商；压测不要打模型接口 |
| `APIConnectionError` | 网络不通（本地 Ollama 未启动最常见） | 本地先 `ollama serve`；云端检查代理 |
| Streamlit 里图表空白 | `ECHARTS_SRC` 指向了容器名而非宿主机地址 | 改成 `http://localhost:8000/...` |
| Superset 里看不到 MySQL 表 | 只读账号没授权到该库 | 重新执行 `GRANT SELECT ON ydsh_mysql.*` |