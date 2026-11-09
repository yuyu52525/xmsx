"""Hive 连接与取数工具（第 3 周共用模块）

本模块只负责"连 Hive + 把 SQL 结果变成 DataFrame"，不含业务逻辑，
供 forecast_gmv.py / ai_insight.py / nl2sql.py 复用。

连接参数全部来自环境变量，默认值对应本项目 docker-compose 的映射
（hive-server 暴露 10000 端口，账号 hive，无密码）。
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import pandas as pd
from pyhive import hive

HIVE_HOST = os.getenv("HIVE_HOST", "localhost")
HIVE_PORT = int(os.getenv("HIVE_PORT", "10000"))
HIVE_USER = os.getenv("HIVE_USER", "hive")
HIVE_AUTH = os.getenv("HIVE_AUTH", "NONE")  # 实测该镜像需 SASL PLAIN；NOSASL 会报 "TSocket read 0 bytes"


@contextmanager
def get_conn(database: str = "ydsh_ads"):
    """建立一个 HiveServer2 连接，用完自动关闭。"""
    conn = hive.Connection(
        host=HIVE_HOST,
        port=HIVE_PORT,
        username=HIVE_USER,
        database=database,
        auth=HIVE_AUTH,
    )
    try:
        yield conn
    finally:
        conn.close()


def query_df(sql: str, database: str = "ydsh_ads") -> pd.DataFrame:
    """执行查询并返回 DataFrame。

    这里不用 pd.read_sql：pandas 3 只对 SQLAlchemy 连接免警告，
    直接拿 pyhive 的 DBAPI 连接会打一堆 UserWarning。
    改成 cursor + fetchall，列名取 cursor.description（去掉表名前缀）。
    """
    with get_conn(database) as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0].split(".")[-1] for d in cur.description] if cur.description else []
    return pd.DataFrame(rows, columns=cols)


def ping() -> str:
    """连通性自检：返回 Hive 版本号。"""
    with get_conn("default") as conn:
        cur = conn.cursor()
        cur.execute("select version()")
        return cur.fetchone()[0]


if __name__ == "__main__":
    print("Hive 版本：", ping())
    df = query_df("select * from ydsh_ads.ads_kpi_overview")
    print(df.T)