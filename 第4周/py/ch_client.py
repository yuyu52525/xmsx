"""第 4 周 · ClickHouse 客户端封装

定位（重要，别理解错）：
  ClickHouse 在本项目里【不是主数据源】，也不承担 ETL。
  它只是"服务层缓存"：把 ydsh_ads 里那批已经算好的 ADS 结果集复制一份，
  用于大屏的高频刷新与压测对比。真正的口径定义全部留在 Hive 数仓里，
  一旦指标口径变了，只改 Hive SQL → 重跑 EXPORT 即可，CH 侧不需要改逻辑。

  这样做的理由：ADS 表最大 1440 行，Hive(Tez) 每次查询启动开销 1~25 秒，
  大屏 6 个面板刷新一次要几十秒，演示时无法接受；CH 同样数据 10~50 毫秒。
  详见 docs/查询优化与压测报告。

设计约束：
  - 表名 / 库名 / SQL 与 Hive 侧完全一致（都在 ydsh_ads 库），
    这样 api_server 里同一句 SQL 可以原样打到两个引擎，切换只换连接。
  - clickhouse_connect 没装时本模块仍可 import（只报不可用），
    保证没有 CH 的环境也能跑 Hive 兜底。
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import pandas as pd

CH_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CH_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CH_USER = os.getenv("CLICKHOUSE_USER", "default")
CH_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CH_DB = os.getenv("CLICKHOUSE_DB", "ydsh_ads")
CH_TIMEOUT = int(os.getenv("CLICKHOUSE_TIMEOUT", "30"))

_AVAILABLE: bool | None = None


def available() -> bool:
    """clickhouse_connect 是否可 import（不等于服务能连上）。"""
    global _AVAILABLE
    if _AVAILABLE is None:
        try:
            import clickhouse_connect  # noqa: F401

            _AVAILABLE = True
        except Exception:  # noqa: BLE001
            _AVAILABLE = False
    return _AVAILABLE


@contextmanager
def get_client(database: str | None = CH_DB):
    import clickhouse_connect

    client = clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD,
        database=database or "default",
        connect_timeout=CH_TIMEOUT,
        send_receive_timeout=CH_TIMEOUT,
    )
    try:
        yield client
    finally:
        client.close()


def query_df(sql: str, database: str | None = CH_DB) -> pd.DataFrame:
    with get_client(database) as client:
        res = client.query(sql)
        return pd.DataFrame([list(r) for r in res.result_rows], columns=list(res.column_names))


def query_timed(sql: str, database: str | None = CH_DB) -> tuple[pd.DataFrame, float]:
    import time

    t0 = time.perf_counter()
    df = query_df(sql, database)
    return df, time.perf_counter() - t0


def ping() -> str:
    with get_client(None) as client:
        return str(client.query("select version()").result_rows[0][0])


def table_counts() -> dict[str, int]:
    """探查 CH 里各 ADS 副本的行数（用于 /api/health 报告缓存是否就绪）。"""
    try:
        df = query_df(
            "select table, sum(rows) as n from system.parts "
            f"where database = '{CH_DB}' and active group by table order by table",
            database=None,
        )
        return {str(r.table): int(r.n) for r in df.itertuples()}
    except Exception:  # noqa: BLE001
        return {}


if __name__ == "__main__":
    print("clickhouse_connect 可用：", available())
    print("CH 版本：", ping())
    print("副本行数：", table_counts())