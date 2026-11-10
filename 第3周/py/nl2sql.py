"""第 3 周 · NL2SQL 接口（自然语言 → SQL → 执行 → 结果）

链路（LCEL）：
  ChatPromptTemplate（系统约束 + 真实 Schema + Few-shot）
        │
        ▼
  RunnableLambda（调 DeepSeek，替换点：可换成任意 OpenAI 兼容模型）
        │
        ▼
  StrOutputParser → cleanse_sql（去代码块 / 安全校验 / 补 limit）
        │
        ▼
  Hive 执行（只读）→ DataFrame → 打印

安全设计（本周要求"约束生成 SQL 的规范性"）：
  1. 只允许 SELECT / WITH 开头；
  2. 命中 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE 等词直接拒绝；
  3. 表名必须带库名（防止在 default 库里瞎查）；
  4. 无 LIMIT 时自动补 LIMIT 200（防止一问就扫全表）；
  5. 执行前再走一遍正则，不信任模型输出。

用法：
  python nl2sql.py "广东省上月销售额是多少？"
  python nl2sql.py --demo        # 用预置参考 SQL 跑通全链路（无 Key 时演示用）
  python nl2sql.py --schema      # 打印自动抽取的 Schema
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

import schema_extract
from hive_client import query_df
from llm_client import chat, has_key

ROOT = Path(__file__).resolve().parent.parent
EVID_DIR = ROOT / "evidence"
SCHEMA_JSON = EVID_DIR / "nl2sql_schema.json"

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|merge|grant|revoke|load|overwrite)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """你是 Hive SQL 专家。请把用户的中文问题翻译成一条可直接执行的 Hive SQL。

【硬性约束】
1. 只能生成 SELECT 或 WITH 开头的查询；禁止任何写操作。
2. 只能使用下面 Schema 里出现的库名、表名、字段名，绝对不要臆造字段。
3. 表名必须写全库名，例如 ydsh_ads.ads_kpi_month。
4. 金额是 double，输出时请写成 cast(round(字段, 2) as decimal(18, 2))，避免科学计数法。
5. 若问题涉及"上个月/某月"，本数据集只有 2024 年 1—12 月，请结合问题里的月份或取最大月份。
6. 结果必须带 limit（最多 200 行）。
7. 只输出 SQL 本身，不要解释，不要 ```sql 代码块。

【表结构】
{schema}

【示例】
问题：广东省 2024 年 12 月的销售额是多少？
SQL：select cast(round(sum(gmv), 2) as decimal(18, 2)) as gmv
     from ydsh_ads.ads_province_sales
     where province = '广东省' and stat_month = '2024-12';

问题：销量最高的前 5 个品类是哪些？
SQL：select category, sum(item_qty) as total_qty
     from ydsh_ads.ads_category_rank
     group by category
     order by total_qty desc
     limit 5;"""

USER_TEMPLATE = "用户问题：{question}\n\n请只输出一条 Hive SQL。"


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------
def load_schema_text() -> str:
    if SCHEMA_JSON.exists():
        schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    else:
        print("[提示] 未找到缓存的 Schema，现场从 Hive 抽取 ...")
        schema = schema_extract.extract()
    return schema_extract.to_text(schema)


# ------------------------------------------------------------------
# SQL 清洗与安全校验
# ------------------------------------------------------------------
def cleanse_sql(text: str) -> str:
    """去掉代码块围栏与多余说明，只保留一条 SQL。"""
    s = text.strip()
    # 去掉 ```sql ... ``` 围栏
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    # 模型偶尔会在前面写"SQL："之类
    s = re.sub(r"^(SQL|sql)\s*[:：]\s*", "", s)
    # 只取第一条语句
    s = s.split(";")[0].strip()
    return s


def guard_sql(sql: str) -> str:
    """安全校验：只读、带库名、带 limit。校验不过直接抛异常。"""
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        raise ValueError(f"拒绝执行：不是 SELECT 查询 -> {sql[:80]}")
    if FORBIDDEN.search(sql):
        raise ValueError(f"拒绝执行：包含写操作关键字 -> {FORBIDDEN.search(sql).group(0)}")
    # 表名必须带库名：from/join 后面不能直接跟裸表名
    bare = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)\b(?!\s*\.)", sql, re.IGNORECASE)
    if bare:
        raise ValueError(f"拒绝执行：表名缺少库名前缀 -> {bare}")
    if not re.search(r"\blimit\b", sql, re.IGNORECASE):
        sql = sql.rstrip() + "\nlimit 200"
    return sql


# ------------------------------------------------------------------
# LangChain 链路
# ------------------------------------------------------------------
def _invoke_llm(prompt_value) -> str:
    """把 LangChain 的 PromptValue 转成 OpenAI messages 再调模型。"""
    role_map = {"system": "system", "human": "user", "ai": "assistant"}
    messages = [
        {"role": role_map.get(m.type, "user"), "content": m.content}
        for m in prompt_value.to_messages()
    ]
    return chat(messages, temperature=0.0, max_tokens=512)


def build_chain():
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", USER_TEMPLATE)]
    )
    return prompt | RunnableLambda(_invoke_llm) | StrOutputParser()


def ask(question: str, verbose: bool = True) -> tuple[str, pd.DataFrame]:
    """完整链路：生成 SQL → 清洗 → 校验 → 执行。"""
    schema_text = load_schema_text()
    chain = build_chain()
    raw = chain.invoke({"schema": schema_text, "question": question})
    sql = guard_sql(cleanse_sql(raw))
    if verbose:
        print("\n生成 SQL：")
        print("  " + sql.replace("\n", "\n  "))
    df = query_df(sql)
    return sql, df


# ------------------------------------------------------------------
# 无 Key 时的链路演示（明确标注不是模型输出）
# ------------------------------------------------------------------
DEMO_CASES: list[tuple[str, str]] = [
    (
        "广东省上月销售额是多少？",
        "select stat_month, province, cast(round(gmv, 2) as decimal(18, 2)) as gmv, order_cnt\n"
        "from ydsh_ads.ads_province_sales\n"
        "where province = '广东省' and stat_month = '2024-12'",
    ),
    (
        "销量最高的前 5 个品类是哪些？",
        "select category, sum(item_qty) as total_qty, "
        "cast(round(sum(sales_amt), 2) as decimal(18, 2)) as total_sales\n"
        "from ydsh_ads.ads_category_rank\n"
        "group by category\n"
        "order by total_qty desc\n"
        "limit 5",
    ),
    (
        "2024 年 12 月的 GMV、订单量和客单价是多少？",
        "select stat_month, cast(round(gmv, 2) as decimal(18, 2)) as gmv, order_cnt,\n"
        "       cast(round(aov, 2) as decimal(18, 2)) as aov\n"
        "from ydsh_ads.ads_kpi_month\n"
        "where stat_month = '2024-12'",
    ),
    (
        "哪个省的人均消费（ARPU）最高？",
        "select province, cast(round(avg_arpu, 2) as decimal(18, 2)) as arpu\n"
        "from (select province, avg(arpu) as avg_arpu\n"
        "      from ydsh_ads.ads_province_sales group by province) t\n"
        "order by arpu desc\n"
        "limit 5",
    ),
    (
        "各渠道在 12 月的销售额占比是多少？",
        "select channel_name, cast(round(gmv, 2) as decimal(18, 2)) as gmv, gmv_share\n"
        "from ydsh_ads.ads_channel_month\n"
        "where stat_month = '2024-12'\n"
        "order by gmv desc",
    ),
]


def run_demo() -> None:
    print("=" * 60)
    print("NL2SQL 链路演示（未配置 API Key，使用预置参考 SQL）")
    print("说明：本模式只演示『提问 → SQL → 校验 → 执行 → 结果』链路，")
    print("      生成的 SQL 是人工预置的参考答案，不是大模型输出。")
    print("=" * 60)
    for i, (q, sql) in enumerate(DEMO_CASES, 1):
        print(f"\n[{i}] 问题：{q}")
        try:
            safe = guard_sql(cleanse_sql(sql))
            print("    SQL：" + safe.replace("\n", "\n         "))
            df = query_df(safe)
            print(f"    命中 {len(df)} 行")
            if len(df) <= 12:
                print(df.to_string(index=False))
            else:
                print(df.head(10).to_string(index=False) + "\n    ...")
        except Exception as exc:  # noqa: BLE001
            print(f"    执行失败：{exc}")


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args[0] == "--schema":
        print(load_schema_text())
        return 0
    if args[0] == "--demo":
        run_demo()
        return 0

    question = " ".join(args)
    if not has_key():
        print("[错误] 未配置大模型 API Key（LLM_API_KEY / DEEPSEEK_API_KEY），无法调用模型。")
        print("       1) 复制 py/.env.example 为 py/.env 并填入 Key（模板里有 4 种方案）；")
        print("       2) 先跑 `python llm_client.py` 验证连通性；")
        print("       3) 或不配 Key、直接跑 `python nl2sql.py --demo` 看链路是否通。")
        return 2

    sql, df = ask(question)
    print(f"\n命中 {len(df)} 行：")
    print(df.to_string(index=False) if len(df) <= 50 else df.head(50).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())