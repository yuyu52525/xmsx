"""第 4 周 · 界面上机自检（CDP 驱动真实浏览器点一遍）

为什么要做这个：答辩要求"现场演示"，
`curl` 通了不等于页面能点。本脚本会真的：
  1) 打开 Streamlit，在输入框里输入问题、点"提问"，等模型+Hive 返回，
     读出页面文字确认"SQL、结果表、图表"都出现了；
  2) 打开 ECharts 大屏，读布局自检报告，确认 7 个面板无重叠、图表都出图。
结果打印成清单 + 截图存 docs/images，可直接作为 evidence。

用法：
  python ui_check.py                    # 两个界面都查
  python ui_check.py --only streamlit
  python ui_check.py --only screen
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from screenshot import DevTools, find_browser  # noqa: E402

HERE = Path(__file__).resolve().parent
DOCS_IMG = HERE.parent / "docs" / "images"

QUESTION = "各支付方式的销售额占比是多少？"


def check_screen(dev: DevTools) -> dict:
    dev.goto("http://127.0.0.1:8000/?debug=1", settle=22)
    raw = dev.js("document.getElementById('geomReport') ? document.getElementById('geomReport').textContent : ''")
    if not raw:
        return {"ok": False, "reason": "大屏没有产出布局自检报告（可能数据没加载出来）"}
    rep = json.loads(raw)
    dev.shot(DOCS_IMG / "screen_01_dashboard.png")
    # area-rank 是自绘 HTML 排行条（不是 ECharts），允许它没有 canvas
    no_canvas = [c for c in rep["chartsWithoutCanvas"] if c != "area-rank"]
    rep["ok"] = (len(rep["panels"]) == 7 and not rep["overlaps"]
                 and len(no_canvas) == 0 and rep["kpiCount"] == 6
                 and rep.get("rankItems", 0) >= 5)
    return rep


def check_streamlit(dev: DevTools) -> dict:
    dev.goto("http://127.0.0.1:8501", settle=9)

    # 1) 输入问题（用 Input.insertText，才能触发 React 的 onChange）
    focused = dev.js("""(() => {
        const el = document.querySelector('input[type="text"], textarea');
        if (!el) return false;
        el.focus(); return true;
    })()""")
    if not focused:
        return {"ok": False, "reason": "找不到输入框"}
    dev.call("Input.insertText", {"text": QUESTION})
    time.sleep(0.8)

    # 2) 点"提问"
    clicked = dev.js("""(() => {
        const btns = [...document.querySelectorAll('button')];
        const b = btns.find(b => (b.innerText || '').includes('提问'));
        if (!b) return false;
        b.click(); return true;
    })()""")
    if not clicked:
        return {"ok": False, "reason": "找不到提问按钮"}

    # 3) 等模型 + Hive 跑完（GLM-4-Flash 约 3~8s，Hive 首次查询 5~15s）
    text = ""
    deadline = time.time() + 120
    while time.time() < deadline:
        time.sleep(4)
        text = dev.js("""(document.querySelector('[data-testid="stMain"]')
                         || document.body).innerText || ''""") or ""
        if "生成的 SQL" in text and ("图表" in text or "数据表" in text):
            break
    time.sleep(4)
    text = dev.js("""(document.querySelector('[data-testid="stMain"]')
                     || document.body).innerText || ''""") or ""
    dev.shot(DOCS_IMG / "screen_02_streamlit.png")

    res = {
        "question": QUESTION,
        "has_question": QUESTION[:6] in text,
        "has_sql": "select" in text.lower() or "SELECT" in text,
        "has_chart_tab": "图表" in text,
        "has_table_tab": "数据表" in text,
        "has_error": ("Traceback" in text) or ("失败" in text),
        "chars": len(text),
    }
    res["ok"] = all([res["has_question"], res["has_sql"], res["has_chart_tab"]]) and not res["has_error"]
    res["excerpt"] = text[:1200]
    return res


def check_superset(dev: DevTools) -> dict:
    """登录 Superset → 打开仪表板 → 数图表并抓错误文案。"""
    dev.goto("http://localhost:8088/login/", settle=6)
    dev.js("""(() => {
        const u = document.querySelector('#username, input[name="username"]');
        const p = document.querySelector('#password, input[name="password"]');
        if (u) u.focus();
        return !!u && !!p;
    })()""")
    dev.call("Input.insertText", {"text": "admin"})
    dev.js("""(() => { const p = document.querySelector('#password, input[name="password"]');
                       if (p) p.focus(); return true; })()""")
    dev.call("Input.insertText", {"text": "admin"})
    time.sleep(0.5)
    dev.js("""(() => { const b = document.querySelector('button[type="submit"], input[type="submit"]');
                       if (b) { b.click(); return true; } return false; })()""")
    time.sleep(6)

    # 不要在等待期间反复 evaluate：Superset 仪表板要连打 6 条 Hive 查询，
    # 期间长时间轮询会让无头浏览器把标签页判定为空闲回收，CDP 连接直接断掉（实测）。
    # 改成"一次等够 + 一次读取"。
    dev.goto("http://localhost:8088/superset/dashboard/ydgmv-overview/", settle=38)
    try:
        text = dev.js("document.body.innerText || ''") or ""
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"读取页面失败（浏览器连接中断）：{type(exc).__name__}"}
    time.sleep(3)
    try:
        text = dev.js("document.body.innerText || ''") or text
        holders = dev.js("""(() => document.querySelectorAll(
            '.dashboard-component-chart-holder, [data-test="chart-container"]').length)()""") or 0
        canvases = dev.js("(() => document.querySelectorAll('canvas').length)()") or 0
        svgs = dev.js("(() => document.querySelectorAll('svg').length)()") or 0
        dev.shot(DOCS_IMG / "screen_03_superset_dashboard.png")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"采样失败：{type(exc).__name__}", "chars": len(text)}

    errors = [ln.strip() for ln in text.splitlines()
              if ("Unexpected error" in ln or "无法" in ln or "Error" in ln or "错误" in ln)]
    res = {
        "logged_in": "登录" not in (text[:200] or "") or "仪表板" in text,
        "chart_holders": holders,
        "canvas": canvases,
        "svg": svgs,
        "error_lines": errors[:6],
        "has_dashboard_title": "经营分析仪表板" in text,
        "chars": len(text),
    }
    res["ok"] = res["has_dashboard_title"] and holders >= 5 and not errors
    res["excerpt"] = text[:1500]
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["screen", "streamlit", "superset"], default=None)
    args = ap.parse_args()

    DOCS_IMG.mkdir(parents=True, exist_ok=True)
    out: dict = {}
    dev = DevTools(find_browser(), 1920, 1080, 1.0)
    try:
        if args.only in (None, "screen"):
            out["screen"] = check_screen(dev)
        if args.only in (None, "streamlit"):
            out["streamlit"] = check_streamlit(dev)
        if args.only in (None, "superset"):
            out["superset"] = check_superset(dev)
    finally:
        dev.close()

    (HERE.parent / "evidence" / "ui_check.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 70)
    for name, res in out.items():
        print(f"[{name}] {'通过' if res.get('ok') else '未通过'}")
        for k, v in res.items():
            if k in ("excerpt", "panels", "kpis"):
                continue
            print(f"    {k}: {v}")
    print("=" * 70)
    return 0 if all(r.get("ok") for r in out.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())