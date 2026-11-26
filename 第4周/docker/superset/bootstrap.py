"""Superset 一键初始化（REST API 驱动，容器内跑完即退出）

做什么：
  1) 建两个数据源：Hive 数仓（主）、MySQL 业务库（跨源演示）
  2) 在 Hive 上建 6 个物理数据集 + 1 个虚拟数据集（省份英文名映射）
  3) 建 6 个图表：月度趋势折线 / 品类柱状 / 区域地图 / 支付占比饼图 /
                TopN 排行表 / KPI 大数字
  4) 建 1 个仪表板，按 12 栅格排版，挂 3 个原生筛选器（月份/品类/支付方式），
     并把交叉筛选（cross filter）打开，实现图表之间点击联动
  5) 全部幂等：已存在就复用，删掉重来用 --rebuild

为什么用 API 而不是让人手动点：
  任务书要求"一键部署 + 现场演示"，手动点 20 分钟也点不完，还不可复现。
  用 API 建出来的东西，答辩时 `docker compose up -d` 就能自动出现。

用法（容器内）：
  python /app/bootstrap.py
  python /app/bootstrap.py --rebuild      # 删掉同名图表/仪表板重建
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests

BASE = os.getenv("SUPERSET_URL", "http://superset:8088").rstrip("/")
USER = os.getenv("ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
HIVE_URI = os.getenv("HIVE_URI", "hive://hive@hive-server:10000/ydsh_ads")
MYSQL_URI = os.getenv("MYSQL_URI", "mysql+pymysql://root:root@mysql:3306/ydsh_mysql?charset=utf8mb4")

DB_HIVE = "Hive 数仓（ydsh_ads）"
DB_MYSQL = "MySQL 业务库（ydsh_mysql）"
DASH_TITLE = "云购生活 · 经营分析仪表板"
DASH_SLUG = "ydgmv-overview"

S = requests.Session()
TOKEN = ""
_CSRF = ""


# --------------------------------------------------------------------- 基础
def log(msg: str) -> None:
    print(msg, flush=True)


def login(attempts: int = 60) -> None:
    global TOKEN
    for i in range(1, attempts + 1):
        try:
            r = S.post(f"{BASE}/api/v1/security/login",
                       json={"username": USER, "password": PASSWORD, "provider": "db", "refresh": False},
                       timeout=20)
            if r.status_code == 200 and r.json().get("access_token"):
                TOKEN = r.json()["access_token"]
                S.headers.update({"Authorization": f"Bearer {TOKEN}",
                                  "Content-Type": "application/json",
                                  "Referer": BASE})
                log(f"  登录成功（第 {i} 次尝试）")
                return
        except Exception as exc:  # noqa: BLE001
            if i == attempts:
                raise SystemExit(f"登录 Superset 失败：{exc}")
        time.sleep(3)
    raise SystemExit("登录 Superset 失败：超时")


def _csrf_token() -> str:
    """取 CSRF token。

    Superset 的 GET 接口用 JWT 就能过，但 POST/PUT/DELETE 一律要求 X-CSRFToken，
    否则报 "The CSRF token is missing."（实测第一步建数据源就卡在这）。
    token 本身也是用 JWT 去 /security/csrf_token/ 换的。
    """
    global _CSRF
    if _CSRF:
        return _CSRF
    r = S.get(f"{BASE}/api/v1/security/csrf_token/", timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"取 CSRF token 失败：{r.status_code} {r.text[:200]}")
    _CSRF = r.json().get("result", "")
    return _CSRF


def api(method: str, path: str, **kw):
    url = f"{BASE}/api/v1{path}"
    if method.upper() not in ("GET", "HEAD"):
        hdrs = dict(kw.pop("headers", {}) or {})
        hdrs["X-CSRFToken"] = _csrf_token()
        kw["headers"] = hdrs
    r = S.request(method, url, timeout=180, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {}


def me_id() -> int | None:
    """取管理员 id（用于 owners）。

    注意：Superset 4.1.2 的 /api/v1/me 用 JWT 访问会 401（"Not authorized"），
    但 /api/v1/database/ 等资源接口同样的 JWT 却是 200 —— 这是该接口自身的行为，
    不是鉴权没开。所以这里失败不报错，直接返回 None，后端允许不填 owners。
    """
    for path in ("/me/", "/security/users/?q=(page_size:1)"):
        try:
            res = api("GET", path)
            result = res.get("result")
            if isinstance(result, dict):
                return result.get("id")
            if isinstance(result, list) and result:
                return result[0]["id"]
        except Exception:  # noqa: BLE001
            continue
    return None


# ------------------------------------------------------------------- 数据源
def ensure_database(name: str, uri: str, extra: dict | None = None) -> int:
    hits = api("GET", "/database/", params={"q": json.dumps({"filters": [
        {"col": "database_name", "opr": "eq", "value": name}]})})["result"]
    if hits:
        db_id = hits[0]["id"]
        # 连接串变了就更新（比如从 root 换成权限最小的只读账号），
        # 否则"改了配置但 Superset 还在用旧账号"这种坑很难发现。
        if hits[0].get("sqlalchemy_uri") != uri and "x" not in uri:
            try:
                api("PUT", f"/database/{db_id}", json={
                    "sqlalchemy_uri": uri, "database_name": name,
                    "configuration_method": "sqlalchemy_form"})
                log(f"  数据源连接串已更新：{name} (id={db_id})")
            except Exception as exc:  # noqa: BLE001
                log(f"  ! 更新连接串失败（继续用原连接）：{exc}")
        log(f"  数据源已存在：{name} (id={db_id})")
        return db_id

    payload = {
        "database_name": name,
        "sqlalchemy_uri": uri,
        "expose_in_sqllab": True,
        "allow_ctas": False,
        "allow_cvas": False,
        "allow_dml": False,
        "allow_run_async": False,
        "configuration_method": "sqlalchemy_form",
        "extra": json.dumps(extra or {"metadata_params": {}, "engine_params": {}}),
    }
    res = api("POST", "/database/", json=payload)
    db_id = res["id"]
    log(f"  建立数据源：{name} (id={db_id})")
    return db_id


def test_database(uri: str) -> dict:
    try:
        return api("POST", "/database/test_connection", json={
            "sqlalchemy_uri": uri, "database_name": "probe",
            "configuration_method": "sqlalchemy_form"})
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


# ------------------------------------------------------------------- 数据集
def ensure_dataset(db_id: int, table_name: str, owner: int | None, sql: str | None = None,
                   schema: str | None = "ydsh_ads") -> int:
    hits = api("GET", "/dataset/", params={"q": json.dumps({
        "filters": [{"col": "table_name", "opr": "eq", "value": table_name}]})})["result"]
    if hits:
        ds_id = hits[0]["id"]
        log(f"  数据集已存在：{table_name} (id={ds_id})")
        return ds_id

    payload = {"database": db_id, "table_name": table_name}
    if owner:
        payload["owners"] = [owner]
    if sql:
        # 虚拟数据集：schema 必须为空
        payload["sql"] = sql
    else:
        payload["schema"] = schema
    res = api("POST", "/dataset/", json=payload)
    ds_id = res["id"]
    try:
        api("PUT", f"/dataset/{ds_id}/refresh")
    except Exception as exc:  # noqa: BLE001
        log(f"    ! 刷新字段失败（不影响建图，但图表可能取不到列）：{exc}")
    log(f"  建立数据集：{table_name} (id={ds_id})")
    return ds_id


def dataset_columns(ds_id: int) -> dict[str, dict]:
    res = api("GET", f"/dataset/{ds_id}")
    cols = res["result"].get("columns") or []
    return {c["column_name"]: c for c in cols}


def metric(col: dict, label: str) -> dict:
    """构造 SIMPLE 型 adhoc 指标（不预先在数据集上定义指标，配置更集中）。"""
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": col["column_name"], "type": col.get("type", "DOUBLE"),
                   "id": col.get("id"), "is_dttm": col.get("is_dttm", False)},
        "aggregate": "SUM",
        "sqlExpression": None,
        "label": label,
        "hasCustomLabel": True,
        "optionName": f"metric_{col['column_name']}_sum",
    }


# ---------------------------------------------------------------------- 图表
def list_charts() -> dict[str, int]:
    res = api("GET", "/chart/", params={"q": json.dumps({"page_size": 200})})
    return {c["slice_name"]: c["id"] for c in res.get("result", [])}


def ensure_chart(name: str, ds_id: int, viz_type: str, params: dict,
                 existing: dict[str, int], rebuild: bool) -> int:
    params = {"datasource": f"{ds_id}__table", "viz_type": viz_type,
              "time_range": "No filter", "adhoc_filters": [], **params}
    # query_context 是 Superset 4.x 的"查询快照"字段，页面上点一次"保存"才会生成。
    # 用 API 建图表时必须自己写，否则 /api/v1/chart/{id}/data/ 会报
    # "Chart has no query context saved"（实测），导出 CSV、定时刷新也会一起失效。
    query_context = {
        "datasource": {"id": ds_id, "type": "table"},
        "force": False,
        "queries": [{k: v for k, v in params.items() if k != "datasource"}],
        "form_data": params,
        "result_format": "json",
        "result_type": "full",
    }
    body = {
        "slice_name": name,
        "datasource_id": ds_id,
        "datasource_type": "table",
        "viz_type": viz_type,
        "params": json.dumps(params, ensure_ascii=False),
        "query_context": json.dumps(query_context, ensure_ascii=False),
    }
    if name in existing:
        cid = existing[name]
        if rebuild:
            api("PUT", f"/chart/{cid}", json=body)
            log(f"  更新图表：{name} (id={cid})")
        else:
            log(f"  图表已存在：{name} (id={cid})")
        return cid
    res = api("POST", "/chart/", json=body)
    cid = res["id"]
    log(f"  建立图表：{name} (id={cid})")
    return cid


# -------------------------------------------------------------------- 仪表板
def list_dashboards() -> dict[str, int]:
    res = api("GET", "/dashboard/", params={"q": json.dumps({"page_size": 200})})
    return {d["dashboard_title"]: d["id"] for d in res.get("result", [])}


def build_position(charts: list[tuple[str, int, int, int, str | None]]) -> dict:
    """按 12 栅格排三行：
       行1：KPI 大数字(3) + 月度趋势(9)
       行2：品类柱状(4) + 区域地图(4) + 支付占比(4)
       行3：TopN 排行表(12)
       charts: [(key, chart_id, width, height, uuid)]
    """
    pos: dict = {"DASHBOARD_VERSION_KEY": "v2"}
    pos["ROOT_ID"] = {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"], "parents": []}
    pos["HEADER_ID"] = {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": DASH_TITLE}}
    pos["GRID_ID"] = {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]}

    rows = [[0, 1], [2, 3, 4], [5]]
    flat = [c for c in charts]
    idx = 0
    for r_i, row in enumerate(rows, 1):
        row_id = f"ROW-{r_i}"
        pos[row_id] = {"type": "ROW", "id": row_id, "children": [],
                       "parents": ["ROOT_ID", "GRID_ID"],
                       "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        pos["GRID_ID"]["children"].append(row_id)
        for _ in row:
            if idx >= len(flat):
                break
            key, cid, w, h, uuid = flat[idx]
            idx += 1
            child_id = f"CHART-{cid}"
            meta = {"chartId": cid, "width": w, "height": h, "sliceName": key}
            if uuid:
                # 4.x 前端按 uuid 找图表组件；uuid 不对就显示"没有找到相关图表的组件"
                meta["uuid"] = uuid
            pos[child_id] = {
                "type": "CHART", "id": child_id, "children": [],
                "parents": ["ROOT_ID", "GRID_ID", row_id],
                "meta": meta,
            }
            pos[row_id]["children"].append(child_id)
    return pos


def link_dashboard_charts(dash_id: int, chart_ids: list[int]) -> bool:
    """把图表关联到仪表板（dashboard_slices 多对多）。

    为什么必须单独做：REST API 的 dashboard POST/PUT 不接受 slices 字段
    （返回 "Unknown field."），position_json 里写了 chartId 也没用 ——
    前端拿到的 dashboard.charts 是空数组，于是 6 个位置全显示
    "没有找到相关图表的组件，是否已经删除"（实测）。
    这里直接在模型层写关联表，是唯一干净的入口。
    """
    try:
        from superset.app import create_app

        app = create_app()
        with app.app_context():
            from superset import db
            from superset.models.dashboard import Dashboard
            from superset.models.slice import Slice

            dash = db.session.get(Dashboard, dash_id)
            if dash is None:
                print(f"  ! 找不到仪表板 {dash_id}")
                return False
            dash.slices = db.session.query(Slice).filter(Slice.id.in_(chart_ids)).all()
            db.session.commit()
            print(f"  已关联 {len(dash.slices)} 个图表到仪表板 {dash_id}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 关联图表失败：{type(exc).__name__}: {exc}")
        return False


def native_filter(fid: str, name: str, column: str, targets: list[int],
                  default: str | None = None) -> dict:
    return {
        "id": fid,
        "name": name,
        "filterType": "filter_select",
        "targets": [{"datasetId": ds, "column": {"name": column}} for ds in targets],
        "defaultDataMask": {"extraFormData": {}, "filterState": {},
                            "ownState": ({"value": [default]} if default else {})},
        "controlValues": {
            "enableEmptyFilter": False,
            "defaultToFirstItem": False,
            "inverseSelection": False,
            "searchAllOptions": False,
            "multiSelect": True,
            "sortAscending": True,
        },
        "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
        "type": "NATIVE_FILTER",
        "description": "",
    }


def build_json_metadata(chart_ids: list[int], filters: list[dict]) -> dict:
    """native_filter_configuration + 交叉筛选（联动）配置。"""
    scope = {"rootPath": ["ROOT_ID"], "excluded": []}
    return {
        "native_filter_configuration": filters,
        "cross_filters_enabled": True,
        "global_chart_configuration": {"scope": scope, "chartsInScope": chart_ids},
        "chart_configuration": {
            str(cid): {"id": cid, "crossFilters": {"scope": scope, "chartsInScope": chart_ids}}
            for cid in chart_ids
        },
        "expanded_slices": {},
        "refresh_frequency": 0,
        "color_scheme": "supersetColors",
        "label_colors": {},
        "shared_label_colors": {},
        "timed_refresh_immune_slices": [],
        "default_filters": "{}",
        "filter_scopes": {},
    }


# ---------------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="已存在的图表/仪表板也重写配置")
    args = ap.parse_args()

    log("=" * 74)
    log("Superset 初始化开始")
    log("=" * 74)

    log("\n[1/6] 登录")
    login()
    admin = me_id()
    log(f"  管理员 id={admin}（为空时不写 owners 字段）")

    log("\n[2/6] 数据源")
    db_hive = ensure_database(DB_HIVE, HIVE_URI)
    db_mysql = ensure_database(DB_MYSQL, MYSQL_URI)
    log(f"  连通性自测 Hive：{str(test_database(HIVE_URI))[:160]}")
    log(f"  连通性自测 MySQL：{str(test_database(MYSQL_URI))[:160]}")

    log("\n[3/6] 数据集")
    ds = {}
    for t in ("ads_kpi_overview", "ads_kpi_month", "ads_sales_daily",
              "ads_category_rank", "ads_province_sales", "ads_pay_type_month",
              "ads_store_rank"):
        ds[t] = ensure_dataset(db_hive, t, admin)

    # 虚拟数据集：把中文省名映射成 Superset 内置中国地图的英文名（NAME_1）
    province_sql = """
select province, region_area, stat_month,
       case province
         when '陕西省' then 'Shaanxi'   when '重庆市' then 'Chongqing'
         when '辽宁省' then 'Liaoning'  when '河南省' then 'Henan'
         when '福建省' then 'Fujian'    when '安徽省' then 'Anhui'
         when '北京市' then 'Beijing'   when '浙江省' then 'Zhejiang'
         when '上海市' then 'Shanghai'  when '山东省' then 'Shandong'
         when '广东省' then 'Guangdong' when '四川省' then 'Sichuan'
         when '江苏省' then 'Jiangsu'   when '湖南省' then 'Hunan'
         when '湖北省' then 'Hubei'
         else province end as province_map,
       gmv, order_cnt, buyer_cnt, aov, arpu
from ydsh_ads.ads_province_sales
""".strip()
    ds["v_province_map"] = ensure_dataset(db_hive, "v_province_map", admin,
                                          sql=province_sql, schema=None)

    log("\n[4/6] 图表")
    existing = list_charts()
    cols = {t: dataset_columns(i) for t, i in ds.items()}
    charts: list[tuple[str, int]] = []

    # ① KPI 大数字
    # 注意：老式 big_number 面板只认单数 metric，但新版后端按 metrics 组查询，
    # 只给 metric 会报 "Empty query?"（实测），所以两个字段都给。
    kpi_metric = metric(cols["ads_kpi_overview"]["gmv"], "GMV")
    cid = ensure_chart(
        "① 全年 GMV（指标卡）", ds["ads_kpi_overview"], "big_number_total",
        {"metric": kpi_metric, "metrics": [kpi_metric],
         "subheader": "订单口径 · 2024 全年", "header_font_size": 34},
        existing, args.rebuild)
    charts.append(("GMV", cid))

    # ② 月度趋势折线
    cid = ensure_chart(
        "② 月度销售趋势（折线）", ds["ads_kpi_month"], "echarts_timeseries_line",
        {"x_axis": "stat_month",
         "metrics": [metric(cols["ads_kpi_month"]["gmv"], "GMV"),
                     metric(cols["ads_kpi_month"]["valid_gmv"], "有效 GMV")],
         "groupby": [], "row_limit": 100, "x_axis_sort_asc": True,
         "show_legend": True, "rich_tooltip": True, "marker_size": 6,
         "opacity": 0.85, "seriesType": "line"},
        existing, args.rebuild)
    charts.append(("月度趋势", cid))

    # ③ 品类销售柱状
    cid = ensure_chart(
        "③ 品类销售额（柱状）", ds["ads_category_rank"], "echarts_timeseries_bar",
        {"x_axis": "category",
         "metrics": [metric(cols["ads_category_rank"]["sales_amt"], "销售额")],
         "groupby": [], "row_limit": 20, "x_axis_sort": "销售额",
         "x_axis_sort_asc": False, "show_legend": False},
        existing, args.rebuild)
    charts.append(("品类柱状", cid))

    # ④ 省份销售 TopN（横向条形）
    # 为什么不是地图（2026-11-26 决定）：country_map 在本镜像里始终渲染空白——
    #   数据侧已确认按省聚合返回 15 行、geo 的 NAME_1 与映射后的英文省名完全一致，
    #   补了 groupby 前端仍不出图，判断为插件侧问题，继续排查性价比低。
    #   改为条形看区域排名；“中国地图”能力保留在 ECharts 大屏（第4周/web，
    #   已核对 15 个省名与 china.json 100% 匹配）。
    prov_metric = metric(cols["ads_province_sales"]["gmv"], "GMV")
    cid = ensure_chart(
        "④ 省份销售 TopN（条形）", ds["ads_province_sales"], "echarts_timeseries_bar",
        {"x_axis": "province", "metrics": [prov_metric], "groupby": [],
         "row_limit": 20, "orientation": "horizontal",
         "x_axis_sort": "GMV", "x_axis_sort_asc": False,
         "order_desc": True, "show_legend": False},
        existing, args.rebuild)
    charts.append(("省份条形", cid))

    # ⑤ 支付方式占比饼图（依赖第 4 周新建的 ads_pay_type_month）
    cid = ensure_chart(
        "⑤ 支付方式占比（饼图）", ds["ads_pay_type_month"], "pie",
        {"groupby": ["pay_name"],
         "metric": metric(cols["ads_pay_type_month"]["gmv"], "GMV"),
         "row_limit": 10, "donut": True, "show_labels": True,
         "show_legend": True, "labels_outside": True},
        existing, args.rebuild)
    charts.append(("支付占比", cid))

    # ⑥ 门店 TopN 排行表
    # 关键：必须 group by store_id + store_name。
    # 数据里 60 个门店编号只有 52 个名称（8 组同名不同店），
    # 只按 store_name 分组会把两家门店合成一条，数字看着大但其实错了。
    cid = ensure_chart(
        "⑥ 门店 GMV TopN（排行表）", ds["ads_store_rank"], "table",
        {"query_mode": "aggregate", "groupby": ["store_id", "store_name"],
         "metrics": [metric(cols["ads_store_rank"]["gmv"], "GMV"),
                     metric(cols["ads_store_rank"]["order_cnt"], "订单量"),
                     metric(cols["ads_store_rank"]["sales_per_sqm"], "月均坪效")],
         "row_limit": 10, "order_desc": True, "order_by_cols": [],
         "show_cell_bars": True, "include_search": False},
        existing, args.rebuild)
    charts.append(("门店TopN", cid))

    log("\n[5/6] 仪表板")
    dashboards = list_dashboards()
    chart_ids = [c for _, c in charts]
    filters = [
        native_filter("NATIVE_FILTER-month", "月份", "stat_month",
                      [ds["ads_kpi_month"], ds["ads_category_rank"], ds["v_province_map"],
                       ds["ads_pay_type_month"], ds["ads_store_rank"]]),
        native_filter("NATIVE_FILTER-category", "品类", "category",
                      [ds["ads_category_rank"]]),
        native_filter("NATIVE_FILTER-pay", "支付方式", "pay_name",
                      [ds["ads_pay_type_month"]]),
    ]
    # 版面：宽度合计 12，高度单位 50
    uuids = {c["id"]: c.get("uuid")
             for c in api("GET", "/chart/", params={"q": json.dumps({"page_size": 200})})["result"]}
    layout = [(name, cid, w, h, uuids.get(cid)) for (name, cid), (w, h) in zip(
        charts, [(3, 50), (9, 50), (4, 50), (4, 50), (4, 50), (12, 50)])]
    position = build_position(layout)
    meta = build_json_metadata(chart_ids, filters)

    body = {
        "dashboard_title": DASH_TITLE,
        "slug": DASH_SLUG,
        "published": True,
        "position_json": json.dumps(position, ensure_ascii=False),
        "json_metadata": json.dumps(meta, ensure_ascii=False),
    }
    if DASH_TITLE in dashboards:
        did = dashboards[DASH_TITLE]
        api("PUT", f"/dashboard/{did}", json=body)
        log(f"  更新仪表板：{DASH_TITLE} (id={did})")
    else:
        res = api("POST", "/dashboard/", json=body)
        did = res["id"]
        log(f"  建立仪表板：{DASH_TITLE} (id={did})")

    link_dashboard_charts(did, chart_ids)

    log("\n[6/6] 校验")
    got = api("GET", f"/dashboard/{did}")
    pos = got["result"].get("position_json") or "{}"
    n_chart_nodes = pos.count('"type": "CHART"')
    linked = got["result"].get("charts") or []
    log(f"  仪表板图表位：{n_chart_nodes} / 期望 {len(charts)}")
    log(f"  已关联图表数：{len(linked)} / 期望 {len(charts)}")
    log(f"  访问地址：{BASE}/superset/dashboard/{did}/")
    log("")
    log("=" * 74)
    log("完成。仪表板链接：http://localhost:8088/superset/dashboard/%d/" % did)
    log("=" * 74)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"\n[失败] {exc}", file=sys.stderr)
        raise SystemExit(1)