"""Superset 部署结果校验（不是"建成功了"，而是"每个图表真的能查出数"）

背景：REST API 建图表成功 ≠ 图表能渲染。
      params 里的 viz_type / x_axis / metric 只要有一处对不上，
      图表在页面上就是一个空白框加 "Unexpected error"。
      所以这里对每个图表都真的跑一次取数，并检查返回行数。

用法（容器内）：
  python /app/check_superset.py
  输出 evidence 风格清单，最后给 PASS/FAIL 汇总（可用于自动化验收）
"""

from __future__ import annotations

import json
import os
import sys

import requests

BASE = os.getenv("SUPERSET_URL", "http://superset:8088").rstrip("/")
USER = os.getenv("ADMIN_USERNAME", "admin")
PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
DASH_SLUG = "ydgmv-overview"

S = requests.Session()


def login() -> None:
    r = S.post(f"{BASE}/api/v1/security/login",
               json={"username": USER, "password": PASSWORD, "provider": "db"}, timeout=30)
    r.raise_for_status()
    S.headers.update({"Authorization": f"Bearer {r.json()['access_token']}",
                      "Referer": BASE})
    tok = S.get(f"{BASE}/api/v1/security/csrf_token/", timeout=30).json()["result"]
    S.headers.update({"X-CSRFToken": tok})


def main() -> int:
    login()
    print("=" * 78)
    print("Superset 图表取数校验")
    print("=" * 78)

    charts = S.get(f"{BASE}/api/v1/chart/?q=" + json.dumps({"page_size": 100}), timeout=60).json()
    rows = charts.get("result", [])
    print(f"图表总数：{len(rows)}\n")

    ok_cnt = 0
    for c in rows:
        cid, name = c["id"], c["slice_name"]
        try:
            r = S.get(f"{BASE}/api/v1/chart/{cid}/data/?format=json", timeout=180)
            if r.status_code != 200:
                print(f"  [FAIL] {name:<28} HTTP {r.status_code} {r.text[:120]}")
                continue
            body = r.json()
            if body.get("result"):
                res = body["result"][0]
                n = res.get("rowcount", len(res.get("data") or []))
                err = res.get("error")
                if err:
                    print(f"  [FAIL] {name:<28} 查询报错：{str(err)[:120]}")
                elif n and n > 0:
                    ok_cnt += 1
                    sample = (res.get("data") or [{}])[0]
                    print(f"  [PASS] {name:<28} {n:>4} 行  首行={str(sample)[:90]}")
                else:
                    print(f"  [FAIL] {name:<28} 返回 0 行（多半是 metric/列名不匹配）")
            else:
                print(f"  [FAIL] {name:<28} 空结果 {r.text[:160]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] {name:<28} {type(exc).__name__}: {exc}")

    print("\n" + "-" * 78)
    d = S.get(f"{BASE}/api/v1/dashboard/?q=" + json.dumps({"page_size": 100}), timeout=60).json()
    dash = next((x for x in d.get("result", []) if x.get("slug") == DASH_SLUG), None)
    if dash is None:
        print("[FAIL] 找不到仪表板")
        return 1
    detail = S.get(f"{BASE}/api/v1/dashboard/{dash['id']}", timeout=60).json()["result"]
    pos = json.loads(detail.get("position_json") or "{}")
    meta = json.loads(detail.get("json_metadata") or "{}")
    n_chart_nodes = sum(1 for k in pos if k.startswith("CHART-"))
    filters = meta.get("native_filter_configuration") or []
    print(f"仪表板：{detail.get('dashboard_title')}  id={dash['id']}")
    print(f"  图表位：{n_chart_nodes}")
    print(f"  原生筛选器：{[f.get('name') for f in filters]}")
    print(f"  交叉筛选（联动）：{meta.get('cross_filters_enabled')}")
    print(f"  访问地址：http://localhost:8088/superset/dashboard/{dash['id']}/")

    print("-" * 78)
    all_ok = ok_cnt == len(rows) and n_chart_nodes == len(rows) and len(filters) >= 1
    print(f"结论：{ok_cnt}/{len(rows)} 个图表可正常取数；"
          f"{'全部通过' if all_ok else '存在需要修复的项'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())