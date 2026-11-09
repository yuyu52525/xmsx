"""第 3 周 · 从 Hive 自动抽取 Schema，生成大模型可读的元信息

为什么必须"自动抽取"而不是手写：
  表结构会随迭代变化（本周就新增了 9 张 DWS + 9 张 ADS），
  手写的 Schema 描述一旦和真实表结构脱节，NL2SQL 生成的 SQL 必然报错，
  而且报错信息会误导排查方向。所以元信息必须从 metastore 现取。

抽取内容：库名 / 表名 / 字段名 / 数据类型 / 中文注释 / 行数
输出：evidence/nl2sql_schema.json（给程序用）、evidence/nl2sql_schema.md（给人看）

用法：
  python schema_extract.py
"""

from __future__ import annotations

import json
from pathlib import Path

from hive_client import get_conn

ROOT = Path(__file__).resolve().parent.parent
EVID_DIR = ROOT / "evidence"
EVID_DIR.mkdir(parents=True, exist_ok=True)

# NL2SQL 只暴露"业务可直接问"的表：
#   ADS 9 张（已经按业务场景聚合好，不需要 JOIN）
#   DWD 4 张维度表（需要按地区/品类/门店下钻时用）
# 不暴露 ODS / stg_ 中间表：字段无业务语义，模型容易拼错。
SCHEMA_TABLES: list[tuple[str, str]] = [
    ("ydsh_ads", "ads_kpi_overview"),
    ("ydsh_ads", "ads_kpi_month"),
    ("ydsh_ads", "ads_sales_daily"),
    ("ydsh_ads", "ads_category_rank"),
    ("ydsh_ads", "ads_province_sales"),
    ("ydsh_ads", "ads_store_rank"),
    ("ydsh_ads", "ads_channel_month"),
    ("ydsh_ads", "ads_behavior_funnel"),
    ("ydsh_ads", "ads_user_rfm"),
    ("ydsh_dwd", "dim_user"),
    ("ydsh_dwd", "dim_product"),
    ("ydsh_dwd", "dim_store"),
    ("ydsh_dwd", "dim_date"),
]

TABLE_DESC = {
    ("ydsh_ads", "ads_kpi_overview"): "全周期核心 KPI 总览（单行）",
    ("ydsh_ads", "ads_kpi_month"): "月度 KPI，含环比与同比",
    ("ydsh_ads", "ads_sales_daily"): "销售日报（每日 GMV/订单/客单价/7日移动平均）",
    ("ydsh_ads", "ads_category_rank"): "品类月度榜单与销售占比",
    ("ydsh_ads", "ads_province_sales"): "省份月度销售与 ARPU",
    ("ydsh_ads", "ads_store_rank"): "门店月度榜单与坪效",
    ("ydsh_ads", "ads_channel_month"): "渠道月度 GMV 与占比",
    ("ydsh_ads", "ads_behavior_funnel"): "月度行为漏斗（浏览/加购/收藏/购买）",
    ("ydsh_ads", "ads_user_rfm"): "用户 RFM 价值分层",
    ("ydsh_dwd", "dim_user"): "用户维度（性别/年龄/省市/会员等级）",
    ("ydsh_dwd", "dim_product"): "商品维度（类目/品牌/价格）",
    ("ydsh_dwd", "dim_store"): "门店维度（省市/大区/面积）",
    ("ydsh_dwd", "dim_date"): "日期维度（年/季/月/周/是否周末）",
}


def describe_table(db: str, table: str) -> list[dict]:
    """取字段名 / 类型 / 注释。遇到 '# Partition Information' 即停止。"""
    with get_conn(db) as conn:
        cur = conn.cursor()
        cur.execute(f"describe `{db}`.`{table}`")
        rows = cur.fetchall()

    cols: list[dict] = []
    for row in rows:
        name = (row[0] or "").strip()
        if not name or name.startswith("#"):
            break  # 分区信息之后不再属于普通字段
        cols.append(
            {
                "name": name,
                "type": (row[1] or "").strip(),
                "comment": (row[2] or "").strip(),
            }
        )
    return cols


def row_count(db: str, table: str) -> int | None:
    try:
        with get_conn(db) as conn:
            cur = conn.cursor()
            cur.execute(f"select count(1) from `{db}`.`{table}`")
            return int(cur.fetchone()[0])
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {db}.{table} 行数获取失败：{exc}")
        return None


def extract() -> dict:
    schema: dict[str, dict] = {}
    for db, table in SCHEMA_TABLES:
        key = f"{db}.{table}"
        print(f"  抽取 {key} ...")
        cols = describe_table(db, table)
        schema[key] = {
            "database": db,
            "table": table,
            "description": TABLE_DESC.get((db, table), ""),
            "rows": row_count(db, table),
            "columns": cols,
        }
    return schema


def to_text(schema: dict) -> str:
    """转成紧凑的文本 Schema，直接拼进 Prompt。"""
    lines: list[str] = []
    for key, meta in schema.items():
        rows = meta["rows"]
        rows_txt = f"，约 {rows:,} 行" if rows is not None else ""
        lines.append(f"### {key}  —— {meta['description']}{rows_txt}")
        for col in meta["columns"]:
            comment = f"  -- {col['comment']}" if col["comment"] else ""
            lines.append(f"  {col['name']} {col['type']}{comment}")
        lines.append("")
    return "\n".join(lines).strip()


def to_markdown(schema: dict) -> str:
    lines = ["# NL2SQL 可查询表结构（自动抽取）", "",
             "> 由 `第3周/py/schema_extract.py` 从 Hive metastore 实时抽取，",
             "> 字段注释直接取 `describe` 的 comment，不做人工转写。", ""]
    for key, meta in schema.items():
        lines.append(f"## {key}")
        lines.append("")
        lines.append(f"- 说明：{meta['description']}")
        lines.append(f"- 行数：{meta['rows']:,}" if meta["rows"] is not None else "- 行数：未知")
        lines.append("")
        lines.append("| 字段 | 类型 | 注释 |")
        lines.append("|---|---|---|")
        for col in meta["columns"]:
            lines.append(f"| `{col['name']}` | {col['type']} | {col['comment']} |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print("开始从 Hive 抽取 Schema ...")
    schema = extract()
    (EVID_DIR / "nl2sql_schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (EVID_DIR / "nl2sql_schema.md").write_text(to_markdown(schema), encoding="utf-8")
    total_cols = sum(len(m["columns"]) for m in schema.values())
    print(f"\n完成：{len(schema)} 张表、{total_cols} 个字段")
    print(f"  JSON -> {EVID_DIR / 'nl2sql_schema.json'}")
    print(f"  MD   -> {EVID_DIR / 'nl2sql_schema.md'}")