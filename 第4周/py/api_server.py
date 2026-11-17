"""第 4 周 · 数据服务（JSON 接口 + 大屏静态托管）

一套接口，两个引擎：
  同一个 SQL（都写 ydsh_ads.xxx，因为 CH 副本与 Hive 同名同库）
  打到 Hive 或 ClickHouse，由 DATA_BACKEND 决定，默认 auto：
    先试 ClickHouse，连不上就自动回落到 Hive —— 演示时 CH 没起来也不会白屏。

接口清单（都是只读）：
  GET  /api/health          服务与两个引擎的连通性
  GET  /api/kpi             顶部指标卡（ads_kpi_overview）
  GET  /api/month           月度趋势（ads_kpi_month）
  GET  /api/daily           日趋势 + 7 日均线（ads_sales_daily）
  GET  /api/category        品类对比（ads_category_rank 聚合）
  GET  /api/province        省份分布（ads_province_sales 聚合，供地图）
  GET  /api/paytype         支付方式占比（ads_pay_type_month 聚合）
  GET  /api/hour_category   时段 × 品类热力图（ads_hour_category）
  GET  /api/store           门店 TopN（ads_store_rank 聚合）
  GET  /api/rfm             RFM 散点（ads_user_rfm）
  GET  /api/channel         渠道结构（ads_channel_month 聚合）
  GET  /api/all             大屏一次性取全量数据（减少 10 次往返）
  POST /api/ask             NL2SQL：{"question": "..."} → {sql, rows}
  GET  /                    静态托管 web/ 目录（ECharts 大屏）

缓存：进程内 TTL 缓存（默认 10s，CACHE_TTL=0 关闭）。
  大屏 30s 自动刷新 + 多人同时看，缓存能把后端压力从 O(观众数) 降到 O(1/10s)；
  压测时用 CACHE_TTL=0 跑一遍、再开缓存跑一遍，两个数都记录，不混淆。

启动：
  python api_server.py                    # 本地：uvicorn 起在 8000
  uvicorn api_server:app --host 0.0.0.0 --port 8000   # 容器内
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import ch_client
import hive_client

HERE = Path(__file__).resolve().parent
WEB_DIR = HERE.parent / "web"
CACHE_TTL = float(os.getenv("CACHE_TTL", "10"))
BACKEND_WANT = os.getenv("DATA_BACKEND", "auto").strip().lower()
MAX_PARALLEL = int(os.getenv("MAX_PARALLEL", "4"))  # /api/all 并发度

app = FastAPI(title="云购生活 · 数据服务", version="4.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# 极简 TTL 缓存（够用就好，不引第三方）
# ----------------------------------------------------------------------
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _cache_get(key: str):
    if CACHE_TTL <= 0:
        return None
    with _cache_lock:
        hit = _cache.get(key)
        if not hit:
            return None
        ts, payload = hit
        if time.time() - ts > CACHE_TTL:
            _cache.pop(key, None)
            return None
        return payload


def _cache_put(key: str, payload: dict) -> dict:
    if CACHE_TTL > 0:
        with _cache_lock:
            _cache[key] = (time.time(), payload)
    return payload


# ----------------------------------------------------------------------
# 引擎选择与执行
# ----------------------------------------------------------------------
_backend_state = {"name": None, "checked_at": 0.0}


def _resolve_backend() -> str:
    """auto 模式下每 30 秒探一次 CH，探不通就用 hive。"""
    if BACKEND_WANT in ("hive", "clickhouse"):
        return BACKEND_WANT
    now = time.time()
    if _backend_state["name"] and now - _backend_state["checked_at"] < 30:
        return _backend_state["name"]
    name = "hive"
    if ch_client.available():
        try:
            ch_client.ping()
            name = "clickhouse"
        except Exception:  # noqa: BLE001
            name = "hive"
    _backend_state.update(name=name, checked_at=now)
    return name


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame → JSON 安全的 list[dict]（numpy 类型统一转原生，NaN → null）。"""
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", force_ascii=False))


def run(engine: str, sql: str) -> pd.DataFrame:
    if engine == "clickhouse":
        return ch_client.query_df(sql)
    return hive_client.query_df(sql)


# ----------------------------------------------------------------------
# 所有图表 SQL 集中在这里：口径只在这个文件里出现一次
# 注意：中文别名必须加反引号（Hive 4 限制），所以别名统一用英文
# ----------------------------------------------------------------------
SQL = {
    "kpi": """
        select gmv, valid_gmv, order_cnt, valid_order_cnt, buyer_cnt, aov, arpu,
               repurchase_rate, valid_revenue_rate, cancel_rate, refund_rate,
               avg_order_items, stat_scope
        from ydsh_ads.ads_kpi_overview
    """,
    "month": """
        select stat_month, gmv, valid_gmv, order_cnt, buyer_cnt, aov, gmv_mom
        from ydsh_ads.ads_kpi_month order by stat_month
    """,
    "daily": """
        select order_date, gmv, gmv_ma7, order_cnt, aov
        from ydsh_ads.ads_sales_daily order by order_date
    """,
    "category": """
        select category,
               round(sum(sales_amt), 2) as sales_amt,
               sum(item_qty)           as item_qty,
               sum(order_cnt)          as order_cnt
        from ydsh_ads.ads_category_rank
        group by category
        order by sales_amt desc
    """,
    "province": """
        select province, region_area,
               round(sum(gmv), 2) as gmv,
               sum(order_cnt)     as order_cnt,
               sum(buyer_cnt)     as buyer_cnt
        from ydsh_ads.ads_province_sales
        group by province, region_area
        order by gmv desc
    """,
    "paytype": """
        select pay_code, pay_name,
               round(sum(gmv), 2) as gmv,
               sum(order_cnt)     as order_cnt,
               round(sum(valid_gmv), 2) as valid_gmv
        from ydsh_ads.ads_pay_type_month
        group by pay_code, pay_name
        order by gmv desc
    """,
    "hour_category": """
        select hour_of_day, category, category_order,
               round(sum(sales_amt), 2) as sales_amt,
               sum(order_cnt)           as order_cnt
        from ydsh_ads.ads_hour_category
        group by hour_of_day, category, category_order
        order by hour_of_day, category_order
    """,
    "store": """
        -- 必须按 store_id 分组：门店名不唯一（60 个编号 / 52 个名称，
        -- 有 8 家门店重名），只按名称聚合会把两家不同门店并成一条。
        select store_id, store_name, province,
               round(sum(gmv), 2) as gmv,
               sum(order_cnt)     as order_cnt,
               round(avg(sales_per_sqm), 2) as avg_sales_per_sqm
        from ydsh_ads.ads_store_rank
        group by store_id, store_name, province
        order by gmv desc
        limit 20
    """,
    "rfm": """
        select user_id, recency_days, frequency, round(monetary, 2) as monetary, rfm_segment
        from ydsh_ads.ads_user_rfm
    """,
    "channel": """
        select channel_name,
               round(sum(gmv), 2) as gmv,
               sum(order_cnt)     as order_cnt
        from ydsh_ads.ads_channel_month
        group by channel_name
        order by gmv desc
    """,
}


def respond(key: str, sql: str | None = None, nocache: bool = False) -> dict:
    if not nocache:
        cached = _cache_get(key)
        if cached:
            return {**cached, "cached": True}
    engine = _resolve_backend()
    t0 = time.perf_counter()
    try:
        df = run(engine, sql or SQL[key])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"{engine} 查询失败：{type(exc).__name__}: {exc}")
    payload = {
        "ok": True,
        "backend": engine,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "data": _records(df),
    }
    return _cache_put(key, payload)


# ----------------------------------------------------------------------
# 接口
# ----------------------------------------------------------------------
@app.get("/api/health")
def health():
    out = {"ok": True, "backend": _resolve_backend(), "cache_ttl": CACHE_TTL}
    try:
        out["hive"] = hive_client.ping()
    except Exception as exc:  # noqa: BLE001
        out["hive"] = f"不可用：{type(exc).__name__}"
    try:
        out["clickhouse"] = ch_client.ping() if ch_client.available() else "未安装 clickhouse_connect"
        out["clickhouse_rows"] = ch_client.table_counts()
    except Exception as exc:  # noqa: BLE001
        out["clickhouse"] = f"不可用：{type(exc).__name__}"
    return out


@app.get("/api/kpi")
def api_kpi():
    return respond("kpi")


@app.get("/api/month")
def api_month():
    return respond("month")


@app.get("/api/daily")
def api_daily():
    return respond("daily")


@app.get("/api/category")
def api_category():
    return respond("category")


@app.get("/api/province")
def api_province():
    return respond("province")


@app.get("/api/paytype")
def api_paytype():
    return respond("paytype")


@app.get("/api/hour_category")
def api_hour_category():
    return respond("hour_category")


@app.get("/api/store")
def api_store(top: int = Query(10, ge=1, le=20)):
    res = respond("store")
    return {**res, "data": res["data"][:top]}


@app.get("/api/rfm")
def api_rfm():
    return respond("rfm")


@app.get("/api/channel")
def api_channel():
    return respond("channel")


@app.get("/api/all")
def api_all(nocache: int = Query(0, ge=0, le=1)):
    """大屏一次取全：10 个请求合成 1 个，并发执行（Hive 下从串行 40s 降到 10s 级）。

    nocache=1 绕过进程内缓存 —— 压测时用它测"真实后端耗时"，
    否则测出来的是缓存耗时，会虚高成绩。
    """
    t0 = time.perf_counter()
    keys = ("kpi", "month", "daily", "category", "province",
            "paytype", "hour_category", "store", "rfm", "channel")
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        futures = {k: pool.submit(respond, k, None, bool(nocache)) for k in keys}
        data = {k: f.result() for k, f in futures.items()}
    return {
        "ok": True,
        "backend": data["kpi"]["backend"],
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        "cached": (not nocache) and data["kpi"].get("cached", False),
        **{k: data[k]["data"] for k in keys},
    }


@app.post("/api/ask")
def api_ask(payload: dict):
    """NL2SQL 的 REST 入口。表单：{"question": "广东省 12 月销售额是多少？"}"""
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")
    try:
        import nl2sql

        sql, df = nl2sql.ask(question, verbose=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")
    return {"ok": True, "sql": sql, "row_count": int(len(df)), "data": _records(df)}


# ----------------------------------------------------------------------
# 静态大屏：/ → web/index.html
# ----------------------------------------------------------------------
if WEB_DIR.exists():
    # /assets 供 index.html 用相对路径引用（同时兼容 file:// 直接双击打开）
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")
    app.mount("/web", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


@app.get("/")
def index():
    page = WEB_DIR / "index.html"
    if page.exists():
        return FileResponse(str(page))
    return JSONResponse({"ok": True, "hint": "接口服务已启动，web/index.html 不存在"}, status_code=200)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")