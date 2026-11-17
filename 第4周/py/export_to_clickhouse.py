"""把 ydsh_ads 的 ADS 结果集复制到 ClickHouse（服务层缓存）

为什么要有这一步（避免误解）：
  ClickHouse 在本项目里【不做 ETL、不是主数据源】。指标口径全部在 Hive 数仓里
  定义好（第 3 周 ADS + 第 4 周新增 2 张表），这里只是把算好的结果搬一份到
  一个"毫秒级响应"的引擎里，解决两个现实问题：
    1) 大屏每 30 秒刷新一次，Hive(Tez) 一条聚合查询 1~25 秒，演示时页面转圈；
    2) 多人同时看大屏时，Hive 会话数很快打满（压测第 4 组数据可复现）。
  口径若变化，只改 Hive SQL 重跑本脚本即可，CH 侧没有任何业务逻辑。

一致性校验（脚本最后一步，必须通过）：
  逐表比对 Hive 与 CH 的 行数 + 金额合计，打印 PASS/FAIL。
  只比行数不够 —— double 精度、NULL 处理都可能让合计对不上。

用法：
  python export_to_clickhouse.py                # 全量复制 + 校验
  python export_to_clickhouse.py --verify-only  # 只校验不复制
  python export_to_clickhouse.py --tables ads_kpi_month,ads_pay_type_month
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pandas as pd

import ch_client
import hive_client

DB = os.getenv("CLICKHOUSE_DB", "ydsh_ads")

TABLES = [
    "ads_kpi_overview",
    "ads_kpi_month",
    "ads_sales_daily",
    "ads_category_rank",
    "ads_province_sales",
    "ads_store_rank",
    "ads_channel_month",
    "ads_behavior_funnel",
    "ads_user_rfm",
    "ads_pay_type_month",   # 第 4 周新增
    "ads_hour_category",    # 第 4 周新增
]

# 每张表用于校验的金额列（没有金额列的用行数校验）
CHECK_COL = {
    "ads_kpi_overview": "gmv",
    "ads_kpi_month": "gmv",
    "ads_sales_daily": "gmv",
    "ads_category_rank": "sales_amt",
    "ads_province_sales": "gmv",
    "ads_store_rank": "gmv",
    "ads_channel_month": "gmv",
    "ads_pay_type_month": "gmv",
    "ads_hour_category": "sales_amt",
    "ads_user_rfm": "monetary",
}

TYPE_MAP = {
    "string": "String",
    "varchar": "String",
    "char": "String",
    "int": "Int32",
    "integer": "Int32",
    "bigint": "Int64",
    "smallint": "Int16",
    "tinyint": "Int8",
    "double": "Float64",
    "float": "Float32",
    "boolean": "Bool",
    "date": "Date",
    "timestamp": "DateTime",
}


def ch_type(hive_type: str) -> str:
    t = hive_type.strip().lower()
    if t.startswith("decimal"):
        return "Decimal" + t[len("decimal"):]
    return TYPE_MAP.get(t, "String")


def hive_columns(table: str) -> list[tuple[str, str]]:
    """取字段名与类型（跳过分区信息行）。"""
    with hive_client.get_conn("ydsh_ads") as conn:
        cur = conn.cursor()
        cur.execute(f"describe ydsh_ads.{table}")
        rows = cur.fetchall()
    out = []
    for r in rows:
        name = (r[0] or "").strip()
        if not name or name.startswith("#"):
            break
        out.append((name, (r[1] or "string").strip()))
    return out


def to_native(row: tuple) -> list:
    """numpy / pandas 标量转成 Python 原生类型，clickhouse-connect 才认。"""
    out = []
    for v in row:
        if v is None:
            out.append(None)
        elif isinstance(v, float) and pd.isna(v):
            out.append(None)
        elif hasattr(v, "item"):
            out.append(v.item())
        else:
            out.append(v)
    return out


def copy_table(table: str) -> tuple[int, float]:
    cols = hive_columns(table)
    coldefs = ",\n  ".join(f"`{n}` Nullable({ch_type(t)})" for n, t in cols)

    with ch_client.get_client(None) as client:
        client.command(f"create database if not exists {DB}")
        client.command(f"drop table if exists {DB}.{table}")
        client.command(
            f"create table {DB}.{table} (\n  {coldefs}\n) "
            "engine = MergeTree order by tuple() comment 'ydsh_ads 结果集服务层副本'"
        )

    t0 = time.time()
    df = hive_client.query_df(f"select * from ydsh_ads.{table}")
    names = list(df.columns)
    rows = [to_native(r) for r in df.itertuples(index=False, name=None)]
    with ch_client.get_client(None) as client:
        client.insert(f"{DB}.{table}", rows, column_names=names)
    return len(rows), time.time() - t0


def verify(table: str) -> tuple[bool, str]:
    col = CHECK_COL.get(table)

    hive_n = int(hive_client.query_df(f"select count(1) as n from ydsh_ads.{table}")["n"].iloc[0])
    ch_n = int(ch_client.query_df(f"select count(1) as n from {DB}.{table}")["n"].iloc[0])
    if hive_n != ch_n:
        return False, f"行数不一致 Hive={hive_n} CH={ch_n}"

    if not col:
        return True, f"{hive_n} 行"

    h_sum = float(hive_client.query_df(
        f"select round(sum({col}), 2) as s from ydsh_ads.{table}")["s"].iloc[0])
    c_sum = float(ch_client.query_df(
        f"select round(sum({col}), 2) as s from {DB}.{table}")["s"].iloc[0])
    diff = abs(h_sum - c_sum)
    ok = diff < 0.01
    return ok, f"{hive_n} 行 / {col} 合计 Hive={h_sum:,.2f} CH={c_sum:,.2f} 差={diff:.4f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--tables", default=None, help="逗号分隔，只处理指定表")
    args = ap.parse_args()

    tables = TABLES if not args.tables else [t.strip() for t in args.tables.split(",")]
    print("=" * 78)
    print(f"ADS → ClickHouse 服务层缓存  目标库：{DB}  表数：{len(tables)}")
    print("=" * 78)
    print(f"CH 版本：{ch_client.ping()}")

    if not args.verify_only:
        for t in tables:
            n, dt = copy_table(t)
            print(f"  [复制] {t:<24} {n:>6} 行   用时 {dt:5.1f}s")

    print("-" * 78)
    print("一致性校验（Hive 侧 vs CH 侧）")
    ok_all = True
    for t in tables:
        try:
            ok, msg = verify(t)
        except Exception as exc:  # noqa: BLE001
            ok, msg = False, f"校验失败：{type(exc).__name__}: {exc}"
        ok_all &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {t:<24} {msg}")
    print("-" * 78)
    print("结论：" + ("全部一致，CH 可直接作为大屏数据源" if ok_all else "存在不一致，请检查"))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())