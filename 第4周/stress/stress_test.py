"""第 4 周 · 压力测试与查询优化对照实验

任务书要求："使用简单工具对系统进行压力测试（如并发查询响应时间），记录测试结果"。
这里不止测"能不能扛"，而是回答四个会被追问的问题：

  实验 A  Hive 单查询基线：11 张 ADS 表各查一次，多慢？慢在哪？
  实验 B  并发能力：并发 1/2/4/8 时，Hive 直连与 ClickHouse 分别什么水平、失败率多少
  实验 C  数据服务（/api/all）并发：1/5/10/20 并发下的 p50/p95/失败率，以及缓存的作用
  实验 D  查询优化对照：
          D1 分区裁剪      dwd_order 全表 vs 按月分区 vs 用 substr(order_date) 伪条件
          D2 预聚合收益    ADS 结果集 vs 回 DWD 明细现算
          D3 分桶 join     dwd_order(user_id 分桶) 与 dim_user 的 join

输出：evidence/stress_*.json + 控制台 markdown 表格（可直接贴进报告）

用法：
  python stress_test.py                 # 全跑（约 4~6 分钟）
  python stress_test.py --quick         # 减小并发轮次
  python stress_test.py --only A,B      # 只跑部分实验
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "py"))

import ch_client          # noqa: E402
import hive_client        # noqa: E402

EVID = HERE.parent / "evidence"
EVID.mkdir(parents=True, exist_ok=True)

API = os.getenv("API_BASE", "http://127.0.0.1:8000")

ADS_TABLES = [
    "ads_kpi_overview", "ads_kpi_month", "ads_sales_daily", "ads_category_rank",
    "ads_province_sales", "ads_store_rank", "ads_channel_month",
    "ads_behavior_funnel", "ads_user_rfm", "ads_pay_type_month", "ads_hour_category",
]

# 大屏最常打的一条：按月的销售汇总（Hive 与 CH 用完全相同的 SQL）
BENCH_SQL = """
select substr(order_date, 1, 7) as ym, count(1) as orders,
       round(sum(gmv), 2) as gmv, round(avg(aov), 2) as aov
from ydsh_ads.ads_sales_daily
group by substr(order_date, 1, 7)
order by ym
"""


def pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round((p / 100) * (len(s) - 1)))))
    return s[k]


def summarize(name: str, lat: list[float], fails: int) -> dict:
    return {
        "case": name,
        "n": len(lat),
        "fail": fails,
        "fail_rate": round(fails / max(1, len(lat) + fails) * 100, 2),
        "mean_ms": round(statistics.fmean(lat) * 1000, 1) if lat else None,
        "p50_ms": round(pct(lat, 50) * 1000, 1) if lat else None,
        "p95_ms": round(pct(lat, 95) * 1000, 1) if lat else None,
        "max_ms": round(max(lat) * 1000, 1) if lat else None,
        "min_ms": round(min(lat) * 1000, 1) if lat else None,
    }


def table(rows: list[dict], cols: list[str]) -> str:
    head = "| " + " | ".join(cols) + " |\n|" + "|".join(["---"] * len(cols)) + "|"
    body = "\n".join("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows)
    return head + "\n" + body


# ---------------------------------------------------------------------- 实验 A
def exp_a() -> list[dict]:
    print("\n[实验 A] Hive 单查询基线（11 张 ADS 表，串行）")
    rows = []
    for t in ADS_TABLES:
        sql = f"select count(1) as n from ydsh_ads.{t}"
        try:
            t0 = time.perf_counter()
            df = hive_client.query_df(sql)
            dt = time.perf_counter() - t0
            rows.append({"table": t, "rows": int(df["n"].iloc[0]), "elapsed_s": round(dt, 2)})
            print(f"  {t:<24} {rows[-1]['rows']:>6} 行   {dt:6.2f}s")
        except Exception as exc:  # noqa: BLE001
            rows.append({"table": t, "rows": -1, "elapsed_s": -1, "error": str(exc)[:80]})
            print(f"  {t:<24} 失败：{exc}")
    print(table(rows, ["table", "rows", "elapsed_s"]))
    return rows


# ---------------------------------------------------------------------- 实验 B
def _bench_once(engine: str) -> float:
    t0 = time.perf_counter()
    if engine == "hive":
        hive_client.query_df(BENCH_SQL)
    else:
        ch_client.query_df(BENCH_SQL.replace("ydsh_ads.ads_sales_daily", "ydsh_ads.ads_sales_daily"))
    return time.perf_counter() - t0


def exp_b(levels: list[int], repeat: int) -> list[dict]:
    print(f"\n[实验 B] 并发能力对比（每档 {repeat} 次请求/线程）")
    rows = []
    for engine in ("hive", "clickhouse"):
        for conc in levels:
            lat: list[float] = []
            fails = 0
            lock = threading.Lock()

            def worker() -> None:
                nonlocal fails
                for _ in range(repeat):
                    try:
                        dt = _bench_once(engine)
                        with lock:
                            lat.append(dt)
                    except Exception:  # noqa: BLE001
                        with lock:
                            fails += 1

            t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=conc) as pool:
                for _ in range(conc):
                    pool.submit(worker)
            wall = time.perf_counter() - t0
            r = summarize(f"{engine} 并发{conc}", lat, fails)
            r["wall_s"] = round(wall, 2)
            r["qps"] = round((len(lat) + fails) / wall, 2) if wall else None
            rows.append(r)
            print(f"  {engine:<11} 并发 {conc:>2}  p50={r['p50_ms']:>9} ms  p95={r['p95_ms']:>9} ms  "
                  f"失败 {fails}  QPS={r['qps']}")
    return rows


# ---------------------------------------------------------------------- 实验 C
def exp_c(levels: list[int], repeat: int) -> list[dict]:
    print(f"\n[实验 C] 数据服务 /api/all 并发（每档 {repeat} 次请求）")
    rows = []
    for nocache in (1, 0):
        for conc in levels:
            lat: list[float] = []
            fails = 0
            lock = threading.Lock()
            url = f"{API}/api/all?nocache={nocache}"

            def worker() -> None:
                nonlocal fails
                s = requests.Session()
                for _ in range(repeat):
                    t0 = time.perf_counter()
                    try:
                        r = s.get(url, timeout=600)
                        dt = time.perf_counter() - t0
                        if r.status_code != 200:
                            raise RuntimeError(str(r.status_code))
                        with lock:
                            lat.append(dt)
                    except Exception:  # noqa: BLE001
                        with lock:
                            fails += 1

            t0 = time.perf_counter()
            with ThreadPoolExecutor(max_workers=conc) as pool:
                for _ in range(conc):
                    pool.submit(worker)
            wall = time.perf_counter() - t0
            label = f"/api/all{'（不走缓存）' if nocache else '（默认缓存）'} 并发{conc}"
            r = summarize(label, lat, fails)
            r["wall_s"] = round(wall, 2)
            r["qps"] = round((len(lat) + fails) / wall, 2) if wall else None
            rows.append(r)
            print(f"  nocache={nocache} 并发 {conc:>2}  p50={r['p50_ms']:>8} ms  "
                  f"p95={r['p95_ms']:>8} ms  失败 {fails}")
    return rows


# ---------------------------------------------------------------------- 实验 D
D_CASES = [
    ("D1 全表扫描（无分区条件）",
     "select count(1) as n, round(sum(pay_amount), 2) as gmv from ydsh_dwd.dwd_order",
     "hive"),
    ("D1 分区裁剪（order_month = 2024-11）",
     "select count(1) as n, round(sum(pay_amount), 2) as gmv "
     "from ydsh_dwd.dwd_order where order_month = '2024-11'",
     "hive"),
    ("D1 伪条件（substr(order_date) 无法裁剪分区）",
     "select count(1) as n, round(sum(pay_amount), 2) as gmv "
     "from ydsh_dwd.dwd_order where substr(order_date, 1, 7) = '2024-11'",
     "hive"),
    # D2 三组必须是"同一口径"才能比：都是 2024-12 微信支付的 GMV
    ("D2 预聚合（ADS 结果集已算好，单表过滤）",
     "select round(sum(gmv), 2) as gmv from ydsh_ads.ads_pay_type_month "
     "where stat_month = '2024-12' and pay_code = 'P2'",
     "hive"),
    ("D2 现算（回 DWD 明细，同口径重算）",
     "select round(sum(pay_amount), 2) as gmv from ydsh_dwd.dwd_order "
     "where order_month = '2024-12' and pay_code = 'P2'",
     "hive"),
    ("D2 最差写法（ADS 场景回明细三表 join）",
     "select round(sum(i.alloc_amount), 2) as gmv "
     "from ydsh_dwd.dwd_order_item i "
     "join ydsh_dwd.dwd_order o on i.order_id = o.order_id "
     "join ydsh_dwd.dim_product p on i.product_id = p.product_id "
     "where o.order_month = '2024-12'",
     "hive"),
    ("D3 分桶表 join（dwd_order bucketed by user_id）",
     "select count(1) as n from ydsh_dwd.dwd_order o "
     "join ydsh_dwd.dim_user u on o.user_id = u.user_id",
     "hive"),
    ("基准：ClickHouse 同一 SQL（与 D2 预聚合完全一致）",
     "select round(sum(gmv), 2) as gmv from ydsh_ads.ads_pay_type_month "
     "where stat_month = '2024-12' and pay_code = 'P2'",
     "clickhouse"),
]


def exp_d() -> list[dict]:
    print("\n[实验 D] 查询优化对照")
    rows = []
    for name, sql, engine in D_CASES:
        try:
            t0 = time.perf_counter()
            if engine == "hive":
                df = hive_client.query_df(sql)
            else:
                df = ch_client.query_df(sql)
            dt = time.perf_counter() - t0
            val = df.iloc[0, 0] if len(df.columns) else None
            rows.append({"case": name, "engine": engine, "elapsed_s": round(dt, 2),
                         "result": str(val)})
            print(f"  {name:<42} {dt:7.2f}s   结果={val}")
        except Exception as exc:  # noqa: BLE001
            rows.append({"case": name, "engine": engine, "elapsed_s": -1,
                         "result": f"失败：{type(exc).__name__}"})
            print(f"  {name:<42} 失败：{exc}")
    print(table(rows, ["case", "engine", "elapsed_s", "result"]))
    return rows


# ---------------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="逗号分隔，如 A,B,D")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    only = set((args.only or "A,B,C,D").upper().split(","))
    levels_b = [1, 2, 4] if args.quick else [1, 2, 4, 8]
    levels_c = [1, 5] if args.quick else [1, 5, 10, 20]
    repeat = 2 if args.quick else 3

    print("=" * 78)
    print("云购生活数仓 · 第 4 周压力测试")
    print(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}   模式：{'快速' if args.quick else '完整'}")
    print(f"Hive：{hive_client.HIVE_HOST}:{hive_client.HIVE_PORT}    "
          f"ClickHouse：{ch_client.CH_HOST}:{ch_client.CH_PORT}    服务：{API}")
    print("=" * 78)

    result: dict = {"meta": {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hive": f"{hive_client.HIVE_HOST}:{hive_client.HIVE_PORT}",
        "clickhouse": f"{ch_client.CH_HOST}:{ch_client.CH_PORT}",
        "api": API, "quick": args.quick,
    }}

    if "A" in only:
        result["A_baseline"] = exp_a()
    if "B" in only:
        result["B_concurrency_engine"] = exp_b(levels_b, repeat)
    if "C" in only:
        result["C_concurrency_api"] = exp_c(levels_c, repeat)
    if "D" in only:
        result["D_optimization"] = exp_d()

    out = EVID / "stress_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())