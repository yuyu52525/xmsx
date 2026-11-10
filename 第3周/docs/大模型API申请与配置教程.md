# 大模型 API 申请与配置教程

> 适用对象：本项目（云购生活数仓）的 NL2SQL 与 AI 洞察模块
> 目标：花 5~10 分钟拿到一个可用的 Key，让 `nl2sql.py` 和 `ai_insight.py --llm` 真正跑起来
> 编写日期：2026-11-10

---

## 一、先说清楚：为什么 Key 必须你自己申请

| 我做不到的事 | 原因 |
|---|---|
| 替你注册账号 | 需要手机号接收短信验证码，我没有手机号，也没有浏览器 |
| 替你点"同意服务条款" | 这是要自然人本人确认的法律行为 |
| 替你保管 Key | Key 等同于账号密码，任何第三方（包括 AI）都不该经手 |

所以下面这份教程是"你动手、我在旁边盯着"的形式。**你每走一步卡住了，把报错发我，我帮你判。**

---

## 二、选哪个（结论先行）

| 方案 | 费用 | 推荐度 | 一句话 |
|---|---|---|---|
| **智谱 GLM-4-Flash** | 完全免费 | ⭐⭐⭐⭐⭐ | 先跑通，够用 |
| DeepSeek 官方 | 充值，跑完全程约 1 元内 | ⭐⭐⭐⭐ | 要 SQL 更准就换它 |
| 硅基流动 | 注册送额度 | ⭐⭐⭐ | 备选 |
| 本地 Ollama | 免费，但要下 5GB | ⭐⭐ | 断网环境才考虑 |

**建议路径：先用智谱免费的把流程跑通 → 如果发现生成的 SQL 不准 → 再换 DeepSeek（只改 3 行配置，不用动代码）。**

---

## 三、智谱 GLM-4-Flash 申请步骤

### 步骤 1：打开官网

浏览器访问 **https://open.bigmodel.cn**

### 步骤 2：注册 / 登录

点右上角「登录」，用**手机号 + 短信验证码**注册。不需要绑卡，不需要实名认证就能用免费模型。

### 步骤 3：找到 API Keys

登录后进入**控制台**，左侧菜单里找 **「API Keys」**（有的版本叫「密钥管理」或「API 密钥」）。

点 **「新建 API Key」** 或 **「创建密钥」**。

### 步骤 4：复制 Key

弹出的 Key 长这样（两段用点连接）：

```
a1b2c3d4e5f6g7h8.i9j0k1l2m3n4o5p6
```

⚠️ **有的平台只显示一次**，关掉窗口就看不到了。如果关掉了，直接删掉重新建一个。

### 步骤 5：确认免费模型的准确名称

这一步**很多人会卡住**。免费模型的名称会随平台更新变化，`glm-4-flash` 可能已经改名。

在控制台找 **「模型广场」/「模型列表」/「文档 → 模型」**，找名字里带 **flash** 或标着 **免费** 的那个，记下**完整的模型 ID**。

常见的几种写法（以你控制台实际显示的为准）：

```
glm-4-flash
glm-4-flash-250414
glm-4.5-flash
```

> 如果后面报 **404 / model not found**，99% 就是这里名字写错了。

---

## 四、把 Key 填进项目

### 步骤 1：进入配置目录

```
D:\xiangmushixun-bde\第3周\py\
```

这个目录里有一个 **`.env.example`** 文件。

### 步骤 2：复制成 `.env`

在文件资源管理器里，右键 `.env.example` → 复制 → 粘贴 → 重命名为 **`.env`**（注意最前面有个点，没有后缀名）。

> 如果 Windows 提示"必须输入文件名"，说明你的系统隐藏了扩展名。用记事本"另存为"，文件名填 `".env"`（**带英文双引号**），保存类型选"所有文件"。

或者用命令行：

```powershell
cd D:\xiangmushixun-bde\第3周\py
Copy-Item .env.example .env
```

### 步骤 3：用记事本打开 `.env`，找到「方案 A」

把这三行前面的 `#` 删掉，把 Key 换成你自己的：

```ini
# 改之前（被注释掉，不生效）
# LLM_API_KEY=你的智谱Key
# LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
# LLM_MODEL=glm-4-flash
```

改成：

```ini
# 改之后（生效）
LLM_API_KEY=a1b2c3d4e5f6g7h8.i9j0k1l2m3n4o5p6
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4-flash
```

**三个必须注意的坑**：

| 错误写法 | 后果 |
|---|---|
| `LLM_API_KEY = "xxx"` （等号两边加空格、值加引号） | 读到的 Key 带空格或引号 → 401 |
| `LLM_MODEL=GLM-4-Flash`（大写） | 部分接口区分大小写 → 404 |
| 把 `#` 漏删了一个 | 只有一半配置生效 → 报"未配置 Key"或连到默认地址 |

### 步骤 4：保存

记事本保存时，**编码选 UTF-8**（右下角可以看到）。

---

## 五、验证：三条命令

```powershell
cd D:\xiangmushixun-bde\第3周\py

# 第 1 步：自检连通性（最重要的第一步）
python llm_client.py
```

### 期望看到

```
========================================================
大模型 API 连通性自检
========================================================
.env 路径   : D:\xiangmushixun-bde\第3周\py\.env  (已加载)
API Key     : a1b2c3...o5p6
Base URL    : https://open.bigmodel.cn/api/paas/v4
模型        : glm-4-flash

--- 返回结构 ---
id      : ...
model   : glm-4-flash
choices : 1 个
finish  : stop
内容    : '连通'
usage   : prompt=12 completion=2

[结论] 连通正常，返回格式符合预期
```

看到 **「连通正常」** 就成功了。

### 如果失败

```powershell
# 第 2 步：跑 NL2SQL（真实提问）
python nl2sql.py "广东省2024年12月的销售额是多少？"

# 第 3 步：让模型写经营摘要
python ai_insight.py --llm
```

---

## 六、报错对照表

`llm_client.py` 会按状态码给出定向提示，对照着改就行：

| 报错里出现 | 真正原因 | 怎么改 |
|---|---|---|
| `未配置 Key` | `.env` 没建，或变量名写错，或 `#` 没删 | 确认文件名叫 `.env`、在 `py/` 目录下、三行都没被注释 |
| `401` / `认证失败` / `invalid api key` | Key 错了、多了空格、已过期 | 重新复制，注意首尾不要带空格；必要时删掉重建 Key |
| `404` / `model not found` / `接口不存在` | 模型名不对，或 Base URL 少了 `/v4` | 去控制台核对**完整模型 ID**；Base URL 必须是 `https://open.bigmodel.cn/api/paas/v4` |
| `429` / `限流` / `insufficient balance` | 请求太快，或免费额度用完了 | 等一分钟再试；或换 DeepSeek |
| `Connection error` / `timed out` | 网络问题（校园网/公司网常常挡） | 换手机热点试一次；能通就是网络策略问题 |
| `SSL` / `certificate` | 代理软件或证书问题 | 关掉 VPN/代理软件再试 |

> 我校网络实测：**open.bigmodel.cn、api.deepseek.com、api.siliconflow.cn 的 443 端口都能连通**（2026-11-10 测）。所以如果你报连接错误，大概率是代理软件或防火墙，不是学校网络。

---

## 七、`.env` 到底是什么？为什么放进去就能调用？

这是你最该搞明白的一点，我拆开讲。

### 7.1 `.env` 不是配置文件，是"环境变量便签"

`.env` 本身**没有任何魔力**。它只是一个纯文本文件，格式是 `键=值`。

真正干活的是 **`python-dotenv`** 这个库。程序启动时执行一行：

```python
load_dotenv()      # 读 .env，把里面的键值对塞进 os.environ
```

就这一步。之后 `.env` 的内容就变成了**进程内存里的环境变量**，等价于你在 PowerShell 里敲 `$env:LLM_API_KEY="..."`。

**所以 `.env` 的唯一作用，是让你不用每次开终端都重新 export 一遍变量。**

### 7.2 程序怎么找到 Key

`llm_client.py` 里的查找逻辑（简化版）：

```python
def _pick(*names):                 # 按顺序找，第一个非空的胜出
    for n in names:
        v = os.getenv(n)
        if v: return v

key   = _pick("LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY")
url   = _pick("LLM_BASE_URL", "DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
model = _pick("LLM_MODEL", "DEEPSEEK_MODEL") or "deepseek-chat"
```

注意两点：
- **环境变量优先级高于 `.env`**（`load_dotenv` 默认不覆盖已存在的变量）——这也是我刚才能用 `$env:LLM_BASE_URL` 指向本地模拟端点的原因；
- 变量名有多个候选，所以旧的 `DEEPSEEK_*` 写法也还能用。

### 7.3 真正发请求的那一步

```python
from openai import OpenAI
client = OpenAI(api_key=key, base_url=url)      # 只是构造对象，不发请求
resp = client.chat.completions.create(           # 这里才真正发 HTTP
    model=model,
    messages=[{"role": "user", "content": "只回复两个字：连通"}],
)
print(resp.choices[0].message.content)
```

实际发出的 HTTP 请求是：

```
POST https://open.bigmodel.cn/api/paas/v4/chat/completions
Authorization: Bearer a1b2c3d4e5f6g7h8.i9j0k1l2m3n4o5p6
Content-Type: application/json

{"model": "glm-4-flash", "messages": [...]}
```

**所以"能不能调通"只取决于四件事**：

| 条件 | 谁保证 | 现状 |
|---|---|---|
| ① Key 有效 | 你申请 | ⏳ 待你操作 |
| ② Base URL 对 | 教程已给准确值 | ✅ |
| ③ 模型名对 | 需你核对控制台 | ⏳ 待你核对 |
| ④ 网络通 | 已实测 | ✅ 三个厂商 443 均可达 |

### 7.4 那"代码这条路"通不通？

**已经验证过了。** 我用一个本地模拟端点（`py/tools/mock_llm_server.py`，返回写死的假数据）跑通了全链路：

```powershell
# 本地起一个假的 OpenAI 兼容服务
python tools/mock_llm_server.py 18080

# 用环境变量把它指过去（不需要真 Key）
$env:LLM_API_KEY="test-key-not-real"
$env:LLM_BASE_URL="http://127.0.0.1:18080/v1"
$env:LLM_MODEL="mock-model"
```

三条命令的实际结果：

| 命令 | 结果 | 验证了什么 |
|---|---|---|
| `python llm_client.py` | `[结论] 连通正常，返回格式符合预期` | 请求构造、`openai` SDK 兼容性、响应解析 |
| `python nl2sql.py "广东省2024年12月的销售额是多少？"` | 生成的 SQL 去掉了 ` ``` ` 围栏、自动补 `limit 200`、**真查到 171,556.38 元 / 73 单** | Prompt 组装 → 模型返回 → SQL 清洗 → 安全校验 → Hive 执行，**全链路** |
| `python ai_insight.py --llm` | 报告里出现"（以下由大模型生成…）"段落 | 洞察结果 JSON → Prompt → 模型文本 → 写入 Markdown |

**结论**：除了"远端模型本身"，这条路上的每一颗螺丝都拧紧了。你把真 Key 填进去，**理论上立刻就能用**；万一不通，只可能是上表 ①③ 两项（Key 或模型名），改配置即可，不用改代码。

*(测试完成后我已把被假数据覆盖的 `evidence/ai_insight.md` 从 Git 还原，交付物里不会残留假内容。)*

---

## 八、换成 DeepSeek（可选）

如果智谱生成的 SQL 不够准，换 DeepSeek：

1. https://platform.deepseek.com 注册
2. 充值（10 元起，够用很久）
3. 「API keys」→ 创建 → 复制
4. `.env` 里把方案 A 注释掉，启用方案 B：

```ini
# LLM_API_KEY=你的智谱Key
# LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
# LLM_MODEL=glm-4-flash

LLM_API_KEY=sk-你的DeepSeekKey
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

5. 重新跑 `python llm_client.py` 验证

**成本参考**：本周全部脚本（NL2SQL 5 个用例 + 洞察 1 次）跑一遍约 5~10 万 tokens，按 DeepSeek 官方定价约**几毛到 1 元**。具体价格以官网为准。

---

## 九、安全红线

| 不要做 | 为什么 |
|---|---|
| 把 `.env` 发到群里 / 截图发人 | Key 泄露 = 别人用你的额度 |
| 把 Key 硬编码进 `.py` | 会被提交到 Git，永久留在历史里 |
| 把 Key 写进文档 / PPT | 答辩材料会流传 |
| 提交前不检查 | 跑一次 `git status`，**看不到 `.env` 就对了** |

本项目已做的防护：

- `.gitignore` 里有 `.env`、`*.key`、`*.pem`；
- `llm_client.py` 的 `mask_key()` 只显示前 6 位和后 4 位；
- 交付物里所有出现 Key 的地方都是 `sk-your-key-here` 这类占位符。

**万一泄露了**：立刻去控制台把这个 Key 删掉，重新建一个。旧 Key 作废，损失可控。

---

## 十、配好之后会发生什么

你配好 Key 并验证通过后，告诉我一声，我会：

1. 用真实模型重跑那 5 个 NL2SQL 测试用例，把 `evidence/nl2sql_demo.txt` 从"预置 SQL"换成**模型真实生成**的记录；
2. 跑 `python ai_insight.py --llm`，拿到模型撰写的经营摘要，人工核对数字后写进报告；
3. 更新 3 份文档里所有"未配置 Key / 未验证"的表述；
4. 把提交清单里的自评从 **88** 改回实际应得的分数（NL2SQL 那 6 分能补回来）。

---

## 附：一分钟速查

```
① 注册  https://open.bigmodel.cn        （手机号）
② 建 Key  控制台 → API Keys → 新建
③ 核对模型名  控制台 → 模型列表 → 找 flash
④ 复制  .env.example → .env
⑤ 填三行  LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
⑥ 验证  python llm_client.py   →  看到"连通正常"
⑦ 试用  python nl2sql.py "广东省2024年12月销售额"
```