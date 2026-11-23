"""第 5 周 · 端到端联调自检（逐层核对 + 指标口径 + 服务层副本 + 应用接口）

为什么要有这个脚本：
  第 5 周任务书子任务 1 要求"逐项核对数据一致性（各层行数、指标值是否吻合），
  修复联调中发现的 Bug"。前四周的校验脚本是分散的（第 1~4 周各有一套 evidence），
  没有一个"从上到下一次性跑完"的入口。本脚本就是那个入口，输出可直接当证据提交。

核对顺序（严格按数据流向，任何一步断了都能马上定位）：
  1. 环境     Docker 9 个服务状态
  2. ODS     6 张贴源表行数                      期望 114,809
  3. DWD     6 条主链路 + dim_date 行数           期望 111,037（不含 dim_date）
  4. DWS     9 张汇总表行数 + 汇总值回算
  5. ADS     11 张应用表行数 + 核心指标值
  6. 副本     ClickHouse 11 张、MySQL 3 张
  7. 应用     API 10 个接口 / Superset / Streamlit
  8. 结论     PASS / FAIL 汇总

用法：
  python e2e_verify.py                 # 全量
  python e2e_verify.py --skip-docker   # 不查容器（只查数据与接口）
  python e2e_verify.py --out xxx.txt   # 指定证据输出文件（默认 ../evidence/e2e_verify.txt）

口径提醒（写进证据，防止后人误读）：
  - GMV 走订单口径 pay_amount（36,116,687.06）
  - 品类 / 门店 / 时段 走明细分摊口径 alloc_amount（35,833,305.06）
  - 两者相距 283,382.65 元 = 114 张无明细订单，相加没有意义
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # 第5周
REPO = ROOT.parent                      # 仓库根
sys.path.insert(0, str(REPO / "第4周" / "py"))   # 复用第 4 周自包含客户端

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

LINES: list[str] = []
CHECKS: list[tuple[str, bool, str]] = []      # (检查项, 是否通过, 说明)


def out(text: str = "") -> None:
    print(text)
    LINES.append(text)


def head(title: str) -> None:
    out()
    out("=" * 78)
    out(f"  {title}")
    out("=" * 78)


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    out(f"  [{'PASS' if ok else 'FAIL'}] {name}  {detail}")


# ----------------------------------------------------------------- 1. 环境
SERVICES = {
    "mysql": "元数据库",
    "mysql-init": "一次性建库",
    "hive-metastore": "Hive 元数据",
    "hive-server": "HiveServer2",
    "clickhouse": "CH 服务层缓存",
    "superset": "BI 仪表板",
    "superset-init": "一次性初始化",
    "ydsh-api": "数据服务",
    "ydsh-app": "Streamlit 问答",
}


def step_docker() -> None:
    head("1. 环境：9 个服务（7 常驻 + 2 一次性任务）")
    try:
        r = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            check("Docker 引擎", False, "未启动（请先启动 Docker Desktop）")
            return
        out(f"  Docker 引擎版本：{r.stdout.strip()}")
    except Exception as exc:  # noqa: BLE001
        check("Docker 引擎", False, f"{type(exc).__name__}: 找不到 docker 命令")
        return

    running = 0
    for name, desc in SERVICES.items():
        r = subprocess.run(["docker", "inspect", "--format",
                            "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}",
                            name], capture_output=True, text=True)
        if r.returncode != 0:
            check(f"{name}（{desc}）", False, "容器不存在")
            continue
        status, health = (r.stdout.strip().split("|") + [""])[:2]
        if name.endswith("-init"):
            ok = status == "exited"          # 一次性任务：跑完退出才正常
            detail = f"{status}（一次性任务，退出码 0 才算正常）" if ok else status
        else:
            ok = status == "running" and health in ("healthy", "")
            detail = f"{status} {health}".strip()
            running += 1 if ok else 0
        check(f"{name}（{desc}）", ok, detail)
    out(f"  常驻服务就绪：{running}/7")


# ----------------------------------------------------------------- 2/3/4/5 数据
def q(sql: str, db: str = "ydsh_ods"):
    import hive_client
    return hive_client.query_df(sql, database=db)


def scalar(sql: str, db: str = "ydsh_ods"):
    df = q(sql, db)
    return df.iloc[0, 0]


def union_counts(db: str, tables: list[str]) -> dict[str, int]:
    """一次查询把同一库的多张表行数取回来（Hive 单条 union all 控制在 8 路以内）。"""
    parts = [f"select '{t}' as t, count(*) as n from {db}.{t}" for t in tables]
    df = q("\nunion all ".join(parts), db="default")
    return {str(r.t): int(r.n) for r in df.itertuples()}


ODS_TABLES = ["ods_user", "ods_product", "ods_store", "ods_order",
              "ods_order_item", "ods_user_behavior"]
DWD_STREAMS = ["dim_user", "dim_product", "dim_store", "dwd_order",
               "dwd_order_item", "dwd_user_behavior"]
DWS_TABLES = ["dws_sales_day", "dws_sales_week", "dws_sales_month",
              "dws_category_month", "dws_store_month", "dws_province_month",
              "dws_user_day", "dws_user_month", "dws_behavior_day"]
ADS_TABLES = ["ads_kpi_overview", "ads_kpi_month", "ads_sales_daily",
              "ads_category_rank", "ads_province_sales", "ads_store_rank",
              "ads_channel_month", "ads_behavior_funnel", "ads_user_rfm",
              "ads_pay_type_month", "ads_hour_category"]


def step_ods() -> dict[str, int]:
    head("2. ODS 贴源层：6 张表行数（期望合计 114,809）")
    counts = union_counts("ydsh_ods", ODS_TABLES)
    for t in ODS_TABLES:
        out(f"  {t:<20}{counts.get(t, -1):>8,}")
    total = sum(counts.values())
    out(f"  {'合计':<20}{total:>8,}")
    check("ODS 行数合计 = 114,809", total == 114809, f"实际 {total:,}")
    return counts


def step_dwd(ods: dict[str, int]) -> dict[str, int]:
    head("3. DWD 明细层：清洗后行数（期望 111,037，不含维度表 dim_date）")
    counts = union_counts("ydsh_dwd", DWD_STREAMS)
    for t in DWD_STREAMS:
        out(f"  {t:<20}{counts.get(t, -1):>8,}")
    dim_date = int(scalar("select count(*) from ydsh_dwd.dim_date", "ydsh_dwd"))
    out(f"  {'dim_date（生成维表）':<20}{dim_date:>8,}")
    total = sum(counts.values())
    out(f"  {'6 条主链路合计':<20}{total:>8,}")
    check("DWD 行数合计 = 111,037", total == 111037, f"实际 {total:,}")
    delta = sum(ods.values()) - total
    rate = delta / sum(ods.values()) * 100
    out(f"  清洗剔除 {delta:,} 行，占比 {rate:.2f}%")
    check("清洗剔除率 ≈ 3.28%", abs(rate - 3.28) < 0.05, f"实际 {rate:.2f}%")
    check("dim_date 覆盖 2 个自然年 = 731 天", dim_date == 731, f"实际 {dim_date}")
    return counts


def step_dws() -> None:
    head("4. DWS 汇总层：9 张表行数 + 汇总值回算")
    c1 = union_counts("ydsh_dws", DWS_TABLES[:8])
    c2 = union_counts("ydsh_dws", DWS_TABLES[8:])
    counts = {**c1, **c2}
    for t in DWS_TABLES:
        out(f"  {t:<22}{counts.get(t, -1):>8,}")

    head("4.1 汇总值回算：DWS 三个粒度加总必须等于订单口径 GMV")
    day = float(scalar("select round(sum(gmv), 2) from ydsh_dws.dws_sales_day", "ydsh_dws"))
    week = float(scalar("select round(sum(gmv), 2) from ydsh_dws.dws_sales_week", "ydsh_dws"))
    month = float(scalar("select round(sum(gmv), 2) from ydsh_dws.dws_sales_month", "ydsh_dws"))
    out(f"  DWS 日粒度 GMV 合计        {day:>18,.2f}")
    out(f"  DWS 周粒度 GMV 合计        {week:>18,.2f}")
    out(f"  DWS 月粒度 GMV 合计        {month:>18,.2f}")
    for label, v in (("日", day), ("周", week), ("月", month)):
        check(f"DWS {label}粒度 GMV = 36,116,687.06", abs(v - 36116687.06) < 1.0, f"{v:,.2f}")

    out("  说明：三张表都是「渠道 × 日期」粒度，同一订单只落一个渠道，因此加总不会重复计数。")
    check("dws_behavior_day 仅覆盖 10~12 月（368 行）",
          counts.get("dws_behavior_day") == 368, f"实际 {counts.get('dws_behavior_day')}")


def step_ads() -> tuple[dict[str, int], dict[str, float]]:
    head("5. ADS 应用层：11 张表 + 核心指标值")
    c1 = union_counts("ydsh_ads", ADS_TABLES[:8])
    c2 = union_counts("ydsh_ads", ADS_TABLES[8:])
    counts = {**c1, **c2}
    for t in ADS_TABLES:
        out(f"  {t:<26}{counts.get(t, -1):>8,}")

    head("5.1 核心指标口径核对")
    row = q("""select gmv, valid_gmv, order_cnt, buyer_cnt, aov, arpu,
                      repurchase_rate, valid_revenue_rate
               from ydsh_ads.ads_kpi_overview""", "ydsh_ads").iloc[0]
    out(f"  GMV              {float(row.gmv):>18,.2f}")
    out(f"  有效 GMV         {float(row.valid_gmv):>18,.2f}  ({float(row.valid_revenue_rate) * 100:.2f}%)")
    out(f"  订单量           {int(row.order_cnt):>18,}")
    out(f"  下单用户         {int(row.buyer_cnt):>18,}")
    out(f"  客单价           {float(row.aov):>18,.2f}")
    out(f"  ARPU             {float(row.arpu):>18,.2f}")
    check("GMV = 36,116,687.06", abs(float(row.gmv) - 36116687.06) < 0.01, f"{float(row.gmv):,.2f}")
    check("订单量 = 14,398", int(row.order_cnt) == 14398, f"{int(row.order_cnt):,}")
    check("客单价 = GMV / 订单量", abs(float(row.aov) - float(row.gmv) / int(row.order_cnt)) < 0.01,
          f"{float(row.aov):,.2f}")

    gmv_dwd = float(scalar("select round(sum(pay_amount), 2) from ydsh_dwd.dwd_order", "ydsh_dwd"))
    cnt_dwd = int(scalar("select count(*) from ydsh_dwd.dwd_order", "ydsh_dwd"))
    alloc = float(scalar("select round(sum(alloc_amount), 2) from ydsh_dwd.dwd_order_item", "ydsh_dwd"))
    item_amt = float(scalar("select round(sum(item_amount), 2) from ydsh_dwd.dwd_order_item", "ydsh_dwd"))
    out(f"  DWD 回算 GMV（pay_amount） {gmv_dwd:>15,.2f}")
    out(f"  DWD 回算分摊额（alloc）    {alloc:>15,.2f}")
    out(f"  DWD 回算原价额（item）     {item_amt:>15,.2f}（只作权重，不可当销售额）")
    check("ADS GMV = DWD 回算 GMV", abs(float(row.gmv) - gmv_dwd) < 0.01, f"{gmv_dwd:,.2f}")
    check("ADS 订单量 = DWD 订单数", int(row.order_cnt) == cnt_dwd, f"{cnt_dwd:,}")

    head("5.2 各维度表加总校验（同一指标在不同表里必须对得上）")
    pairs = [
        ("ads_kpi_month.gmv", "select round(sum(gmv),2) from ydsh_ads.ads_kpi_month", 36116687.06),
        ("ads_sales_daily.gmv", "select round(sum(gmv),2) from ydsh_ads.ads_sales_daily", 36116687.06),
        ("ads_province_sales.gmv", "select round(sum(gmv),2) from ydsh_ads.ads_province_sales", 36116687.06),
        ("ads_store_rank.gmv", "select round(sum(gmv),2) from ydsh_ads.ads_store_rank", 36116687.06),
        ("ads_channel_month.gmv", "select round(sum(gmv),2) from ydsh_ads.ads_channel_month", 36116687.06),
        ("ads_pay_type_month.gmv", "select round(sum(gmv),2) from ydsh_ads.ads_pay_type_month", 36116687.06),
        ("ads_category_rank.sales_amt", "select round(sum(sales_amt),2) from ydsh_ads.ads_category_rank", alloc),
        ("ads_hour_category.sales_amt", "select round(sum(sales_amt),2) from ydsh_ads.ads_hour_category", alloc),
    ]
    values: dict[str, float] = {}
    for label, sql, expect in pairs:
        v = float(scalar(sql, "ydsh_ads"))
        values[label] = v
        tol = max(1.0, abs(expect) * 0.0002)     # 逐行 round(2) 累计误差容忍 0.02%
        check(f"{label} 合计", abs(v - expect) <= tol, f"{v:,.2f}（期望 {expect:,.2f}）")

    # 无明细订单造成的口径差
    orphan = int(scalar("""select count(*) from ydsh_dwd.dwd_order o
                           left join (select distinct order_id from ydsh_dwd.dwd_order_item) i
                           on o.order_id = i.order_id
                           where i.order_id is null""", "ydsh_dwd"))
    gap = float(scalar("select round(sum(pay_amount),2) from ydsh_dwd.dwd_order", "ydsh_dwd")) - \
        float(scalar("select round(sum(pay_amount),2) from ydsh_dwd.dwd_order o "
                     "join (select distinct order_id from ydsh_dwd.dwd_order_item) i "
                     "on o.order_id = i.order_id", "ydsh_dwd"))
    out(f"  无明细订单 {orphan} 张，实付合计 {gap:,.2f} 元")
    check("订单口径 − 明细分摊口径 = 无明细订单金额",
          abs((gmv_dwd - alloc) - gap) < 1.0, f"{gmv_dwd - alloc:,.2f} vs {gap:,.2f}")
    return counts, values


def load_env() -> None:
    """把仓库根 .env 加载进环境变量。

    必须在这里做：ch_client / pymysql 都是在 import 时读环境变量的，
    不先加载就会用 default/空密码去连 ClickHouse，报 516 Authentication failed
    （第 5 周联调时真实踩到过，记录在《第5周_AI协同日志》）。
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO / ".env", override=False)
    except Exception:  # noqa: BLE001
        pass
    os.environ.setdefault("CLICKHOUSE_HOST", "127.0.0.1")
    os.environ.setdefault("CLICKHOUSE_PORT", "8123")
    os.environ.setdefault("CLICKHOUSE_DB", "ydsh_ads")


def step_copies(ads_counts: dict[str, int]) -> None:
    head("6. 服务层副本：ClickHouse 11 张 / MySQL 3 张")
    try:
        import ch_client
        ver = ch_client.ping()
        out(f"  ClickHouse 版本：{ver}")
        cnt = ch_client.table_counts()
        miss = [t for t in ADS_TABLES if t not in cnt]
        bad = [f"{t}: Hive {ads_counts.get(t)} / CH {cnt.get(t)}"
               for t in ADS_TABLES if t in cnt and cnt[t] != ads_counts.get(t)]
        out(f"  CH 副本表数 {len(cnt)}，行数合计 {sum(cnt.values()):,}")
        check("CH 副本 11 张表齐全", not miss, f"缺 {miss}" if miss else "")
        check("CH 副本行数与 Hive ADS 一致", not bad, "; ".join(bad))
    except Exception as exc:  # noqa: BLE001
        check("ClickHouse 副本", False, f"{type(exc).__name__}: {exc}")

    try:
        import pymysql
        from dotenv import dotenv_values
        env = dotenv_values(REPO / ".env")
        pwd = env.get("MYSQL_ROOT_PASSWORD") or env.get("MYSQL_PASSWORD") or "root"
        conn = pymysql.connect(host="127.0.0.1", port=3307, user="root",
                              password=pwd, database="ydsh_mysql", charset="utf8mb4")
        cur = conn.cursor()
        cur.execute("show tables")
        tables = [r[0] for r in cur.fetchall()]
        total = 0
        for t in tables:
            cur.execute(f"select count(*) from `{t}`")
            n = int(cur.fetchone()[0])
            total += n
            out(f"  MySQL ydsh_mysql.{t:<22}{n:>6,}")
        conn.close()
        check("MySQL 业务快照 3 张表 / 61 行", len(tables) == 3 and total == 61,
              f"{len(tables)} 张 / {total} 行")
    except Exception as exc:  # noqa: BLE001
        check("MySQL 业务快照", False, f"{type(exc).__name__}: {exc}")


def step_app() -> None:
    head("7. 应用层：数据服务接口 / Superset / Streamlit")
    try:
        import requests
    except Exception:  # noqa: BLE001
        check("requests", False, "未安装，跳过接口探测")
        return

    try:
        r = requests.get("http://127.0.0.1:8000/api/health", timeout=20).json()
        out(f"  /api/health  {json.dumps(r, ensure_ascii=False)[:400]}")
        check("数据服务健康检查", r.get("status") in ("ok", "healthy", True) or "hive" in r,
              str(r.get("backend", ""))[:40])
    except Exception as exc:  # noqa: BLE001
        check("数据服务 /api/health", False, f"{type(exc).__name__}")

    endpoints = ["/api/kpi", "/api/month", "/api/daily", "/api/category", "/api/province",
                 "/api/paytype", "/api/hour_category", "/api/store", "/api/rfm", "/api/channel"]
    ok_cnt = 0
    for ep in endpoints:
        try:
            r = requests.get(f"http://127.0.0.1:8000{ep}", timeout=60)
            n = len(r.json().get("data", r.json() if isinstance(r.json(), list) else []))
            out(f"  {ep:<22}{r.status_code}  返回 {n} 条")
            ok_cnt += 1 if r.status_code == 200 else 0
        except Exception as exc:  # noqa: BLE001
            out(f"  {ep:<22}ERR {type(exc).__name__}")
    check("10 个数据接口全部 200", ok_cnt == 10, f"{ok_cnt}/10")

    for label, url, key in (("Superset", "http://127.0.0.1:8088/health", "healthy"),
                            ("Streamlit", "http://127.0.0.1:8501/_stcore/health", "ok")):
        try:
            r = requests.get(url, timeout=20)
            out(f"  {label:<22}{r.status_code}  {r.text[:40]}")
            check(f"{label} 健康检查", r.status_code == 200, "")
        except Exception as exc:  # noqa: BLE001
            check(f"{label} 健康检查", False, f"{type(exc).__name__}")


# ----------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "evidence" / "e2e_verify.txt"))
    ap.add_argument("--skip-docker", action="store_true")
    args = ap.parse_args()

    t0 = time.perf_counter()
    head("云购生活数仓 · 第 5 周端到端联调自检")
    out(f"  执行时间：{datetime.now():%Y-%m-%d %H:%M:%S}")
    out(f"  解释器：{sys.executable}")
    out(f"  仓库根：{REPO}")

    load_env()
    if not args.skip_docker:
        step_docker()

    try:
        import hive_client
        out(f"\n  Hive 版本：{hive_client.ping()}")
        check("Hive 连接", True)
    except Exception as exc:  # noqa: BLE001
        check("Hive 连接", False, f"{type(exc).__name__}: {exc}")
        _finish(t0, args.out)
        return 1

    ods = step_ods()
    step_dwd(ods)
    step_dws()
    ads_counts, _ = step_ads()
    step_copies(ads_counts)
    step_app()
    _finish(t0, args.out)
    return 0 if all(ok for _, ok, _ in CHECKS) else 2


def _finish(t0: float, out_path: str) -> None:
    head("8. 结论")
    pass_n = sum(1 for _, ok, _ in CHECKS if ok)
    fail = [(n, d) for n, ok, d in CHECKS if not ok]
    out(f"  核对项 {len(CHECKS)} 个：通过 {pass_n}，未通过 {len(fail)}")
    for n, d in fail:
        out(f"    ✗ {n}  {d}")
    out(f"  总耗时 {time.perf_counter() - t0:.1f} 秒")
    out()
    out("  结论：" + ("全链路一致，端到端可复现" if not fail else "存在不一致项，见上方 FAIL 清单"))

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(LINES), encoding="utf-8")
    print(f"\n证据已写入：{path}")


if __name__ == "__main__":
    raise SystemExit(main())