"""把 KPI 结果集落一份到 MySQL（"业务库"角色，供 Superset 做跨源连接演示）

为什么要有 MySQL 数据源：
  任务书子任务 1 要求"通过 JDBC 连接 Hive，同时连接 MySQL"。
  本项目 MySQL 原本只当 Hive Metastore + Superset 元数据库，里面没有业务数据。
  为了能真实演示"跨源查询"，把 3 张小表（KPI 总览 / 月度 KPI / 支付方式）
  以快照形式落到 ydsh_mysql 库：
    - 分析主数据源仍然是 Hive（口径在数仓里）；
    - MySQL 这份只用于 Superset 侧对比与跨源能力演示，不参与任何指标定义；
    - 数据量：1 + 12 + 48 行，快照过期风险低，重跑本脚本即可刷新。

用法：
  python export_to_mysql.py
  python export_to_mysql.py --host 127.0.0.1 --port 3307 --password root
"""

from __future__ import annotations

import argparse
import os

import pymysql

import hive_client

DB = "ydsh_mysql"

TABLES = [
    ("ads_kpi_overview", ["gmv", "valid_gmv", "order_cnt", "buyer_cnt", "aov", "arpu"]),
    ("ads_kpi_month", ["stat_month", "gmv", "valid_gmv", "order_cnt", "buyer_cnt", "aov"]),
    ("ads_pay_type_month", ["stat_month", "pay_name", "gmv", "order_cnt", "gmv_share"]),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3307")))
    ap.add_argument("--user", default=os.getenv("MYSQL_USER", "root"))
    ap.add_argument("--password", default=os.getenv("MYSQL_ROOT_PASSWORD", "root"))
    args = ap.parse_args()

    print("=" * 74)
    print(f"KPI 快照 → MySQL  {args.host}:{args.port}  库：{DB}")
    print("=" * 74)

    conn = pymysql.connect(host=args.host, port=args.port, user=args.user,
                           password=args.password, charset="utf8mb4", autocommit=True)
    cur = conn.cursor()
    cur.execute(f"create database if not exists {DB} default character set utf8mb4")
    cur.execute(f"use {DB}")

    for table, wanted in TABLES:
        df = hive_client.query_df(f"select * from ydsh_ads.{table}")
        cols = [c for c in wanted if c in df.columns]
        df = df[cols]

        # 全表重建：字段类型按 DataFrame 推断，够用（都是小数/整数/字符串）
        cur.execute(f"drop table if exists {table}")
        defs = []
        for c in cols:
            if str(df[c].dtype).startswith(("int", "int32", "int64")):
                defs.append(f"`{c}` double")
            elif str(df[c].dtype).startswith("float"):
                defs.append(f"`{c}` double")
            else:
                defs.append(f"`{c}` varchar(64)")
        cur.execute(f"create table {table} ({', '.join(defs)}) engine=InnoDB default charset=utf8mb4")

        placeholders = ",".join(["%s"] * len(cols))
        sql = f"insert into {table} ({','.join('`'+c+'`' for c in cols)}) values ({placeholders})"
        rows = []
        for r in df.itertuples(index=False, name=None):
            rows.append(tuple(None if (isinstance(v, float) and v != v) else
                              (v.item() if hasattr(v, "item") else v) for v in r))
        cur.executemany(sql, rows)
        print(f"  [写入] {table:<22} {len(rows):>4} 行  字段 {', '.join(cols)}")

    cur.execute("show tables")
    names = [r[0] for r in cur.fetchall()]
    print("-" * 74)
    print(f"库 {DB} 现有表：{', '.join(names)}")
    cur.close()
    conn.close()
    print("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())