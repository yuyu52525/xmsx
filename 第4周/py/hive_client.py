"""第 4 周 · Hive 连接工具（自包含版，供 API / Streamlit / 压测脚本共用）

与第 3 周 py/hive_client.py 的关系：
  接口保持一致（get_conn / query_df / ping），但第 4 周要跑在容器里，
  所以连接参数全部走环境变量、并加了重试与超时，文件独立不依赖第 3 周目录。

关键经验（第 3 周实测）：
  - auth 必须是 NONE（pyhive 会走 SASL PLAIN）；填 NOSASL 会报 TSocket read 0 bytes
  - 依赖链：pyhive + thrift + thrift_sasl + pure-sasl，少任何一个都连不上
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager

import pandas as pd
from pyhive import hive

HIVE_HOST = os.getenv("HIVE_HOST", "localhost")
HIVE_PORT = int(os.getenv("HIVE_PORT", "10000"))
HIVE_USER = os.getenv("HIVE_USER", "hive")
HIVE_AUTH = os.getenv("HIVE_AUTH", "NONE")
HIVE_DB = os.getenv("HIVE_DB", "ydsh_ads")
HIVE_TIMEOUT = int(os.getenv("HIVE_TIMEOUT", "120"))  # 秒


def _connect(database: str) -> hive.Connection:
    return hive.Connection(
        host=HIVE_HOST,
        port=HIVE_PORT,
        username=HIVE_USER,
        database=database,
        auth=HIVE_AUTH,
        configuration={"hive.server2.client.protocol": "1"},
    )


@contextmanager
def get_conn(database: str = HIVE_DB, retries: int = 3, backoff: float = 2.0):
    """建立一个 HiveServer2 连接，用完自动关闭。带指数退避重试。"""
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            conn = _connect(database)
            break
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt == retries:
                raise
            time.sleep(backoff * attempt)
    else:  # pragma: no cover
        raise RuntimeError(f"连接 Hive 失败：{last}")
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def query_df(sql: str, database: str = HIVE_DB, timeout: int | None = None) -> pd.DataFrame:
    """执行查询并返回 DataFrame（cursor + fetchall，避开 pandas 对 DBAPI 的告警）。"""
    with get_conn(database) as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0].split(".")[-1] for d in cur.description] if cur.description else []
    df = pd.DataFrame(rows, columns=cols)
    return df


def query_timed(sql: str, database: str = HIVE_DB) -> tuple[pd.DataFrame, float]:
    """返回 (结果, 耗时秒)。压测脚本用。"""
    t0 = time.perf_counter()
    df = query_df(sql, database)
    return df, time.perf_counter() - t0


def ping() -> str:
    """连通性自检：返回 Hive 版本号。"""
    with get_conn("default", retries=1) as conn:
        cur = conn.cursor()
        cur.execute("select version()")
        return cur.fetchone()[0]


def describe(sql: str, database: str = HIVE_DB) -> None:
    """调试辅助：执行并打印。"""
    df = query_df(sql, database)
    print(df.to_string(index=False))


if __name__ == "__main__":
    print("Hive 版本：", ping())
    print(query_df("select count(1) as n from ydsh_ads.ads_kpi_overview").to_string(index=False))