"""第 4 周 · Streamlit 对话式问答应用（NL2SQL 完整闭环 + ECharts 渲染）

闭环链路（对应任务书子任务 3）：
   提问 → LLM 生成 SQL → 安全校验（只读/带库名/补 limit）→ Hive 执行
        → 表格展示 → ECharts 图表渲染 → 写入会话历史

设计要点：
  1) 复用第 3 周已验证的 NL2SQL 链路（nl2sql.ask），不重写提示词工程；
  2) 图表类型自动推断 + 允许手动覆盖，避免"一问就只会画柱状图"；
  3) 没配 Key 时进入"演示模式"，用预置 SQL 跑通链路，并明确标注不是模型输出；
  4) 所有异常都落到页面上（含生成的 SQL），不做静默吞异常 —— 排查比好看重要。

启动：
    streamlit run streamlit_app.py --server.port 8501
本地演示：http://localhost:8501     容器内：http://localhost:8501
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import hive_client
import llm_client
import nl2sql

# ECharts 从数据服务取（同一镜像的 api 服务已托管该文件）；
# 容器内换成宿主机映射地址，因为最终是"浏览器"去加载这个 js。
ECHARTS_SRC = os.getenv("ECHARTS_SRC", "http://localhost:8000/assets/echarts.min.js")
ECHARTS_CDN = "https://unpkg.com/echarts@5.5.1/dist/echarts.min.js"

st.set_page_config(
    page_title="云购生活 · 智能经营问答",
    page_icon="🐳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------- 样式
st.markdown("""
<style>
  .block-container { padding-top: 2.2rem; max-width: 1500px; }
  .q-card {
    background: linear-gradient(135deg, rgba(53,214,255,.10), rgba(124,92,255,.08));
    border-left: 3px solid #35d6ff; border-radius: 6px;
    padding: 10px 14px; margin-bottom: 8px; font-size: 1.02rem;
  }
  .meta-line { color: #7f9bc0; font-size: .82rem; }
  .badge {
    display:inline-block; padding:1px 8px; border-radius:999px; font-size:.74rem;
    border:1px solid rgba(53,214,255,.35); color:#35d6ff; margin-right:6px;
  }
  .badge.warn { border-color:rgba(255,200,87,.45); color:#ffc857; }
  .badge.err  { border-color:rgba(255,120,120,.45); color:#ff8a8a; }
  div[data-testid="stMetricValue"] { font-size: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- 侧边栏
def sidebar() -> None:
    with st.sidebar:
        st.header("运行状态")

        # Hive
        try:
            ver = hive_client.ping()
            st.success(f"Hive 已连接：{ver.split()[0]}")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Hive 连不上：{type(exc).__name__}")

        # 大模型
        if llm_client.has_key():
            st.success(f"大模型已配置：{llm_client.model_name()}")
            st.caption(f"Key {llm_client.mask_key()} ｜ {llm_client.base_url()}")
        else:
            st.warning("未配置大模型 Key —— 进入演示模式（用预置 SQL 跑链路）")

        st.divider()
        st.header("试试这些问题")
        examples = [
            "2024 年 12 月的 GMV、订单量和客单价是多少？",
            "各支付方式的销售额占比是多少？",
            "广东省 2024 年 12 月的销售额是多少？",
            "销量最高的前 5 个品类是哪些？",
            "一天中哪个时段销售额最高？",
            "哪个省的客单价最高？",
            "2024 年各渠道的 GMV 占比",
        ]
        for i, q in enumerate(examples):
            if st.button(q, key=f"ex{i}", use_container_width=True):
                st.session_state["pending_q"] = q
                st.rerun()

        st.divider()
        st.header("会话管理")
        if st.button("清空历史对话", use_container_width=True):
            st.session_state["history"] = []
            st.rerun()
        st.caption("每次提问约消耗 3.0k~3.6k tokens（含 Schema）")

        with st.expander("查看 token 用量"):
            if llm_client.USAGE_LOG.exists():
                rows = [ln.split("\t") for ln in
                        llm_client.USAGE_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
                tot_in = sum(int(r[2]) for r in rows if len(r) >= 5)
                tot_out = sum(int(r[3]) for r in rows if len(r) >= 5)
                st.write(f"调用 {len(rows)} 次 ｜ 输入 {tot_in:,} ｜ 输出 {tot_out:,} ｜ 合计 {tot_in + tot_out:,}")
                st.dataframe(
                    pd.DataFrame(rows[-10:], columns=["时间", "模型", "输入", "输出", "合计"]),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.write("暂无记录")


# ---------------------------------------------------------------- 图表推断
# 图表“看着怪”，多数不是渲染问题，而是选错图：
# 把 15 个省份塞进饼图、把明细表画成散点、把占比画成折线。
# 所以分两步：先按“结果形状 + 问题意图”选图（pick_chart），
# 再按图类型做排序、截断、量纲换算（chart_option）。
# 注意：ECharts 的 formatter 只支持字符串模板（{b}/{c}/{d}），
# 不支持传 JS 函数，所以数值的单位换算在 Python 侧做完再喂给前端。
TIME_HINTS = ("date", "month", "day", "week", "hour", "时间", "月份", "日期",
              "时段", "年份", "周")
SHARE_HINTS = ("占比", "比例", "构成", "结构", "份额", "分布", "百分比", "percent")
REL_HINTS = ("关系", "相关", "散点")
RATE_HINTS = ("率", "占比", "比例", "百分比", "share", "rate")


def _is_timey(col: str, s: pd.Series) -> bool:
    """判断是不是时间轴。按词边界匹配名称，避免 recency_days 这类被误判。"""
    name = str(col).lower()
    if re.search(r"(^|_)(date|month|day|week|hour|year)($|_)", name):
        return True
    if any(h in name for h in ("时间", "月份", "日期", "时段", "年份")):
        return True
    if s.dtype.kind in "biufc":
        return False
    try:
        return bool(s.astype(str).str.match(r"^\d{4}(-\d{2}){0,2}").fillna(False).all())
    except Exception:  # noqa: BLE001
        return False


def _to_num(s: pd.Series) -> pd.Series:
    """把可能带 Decimal / 字符串的列尽量转成 float。"""
    return pd.to_numeric(s, errors="coerce")


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    """数值列：真正的数值列，外加“能转成数值”的 object 列（Decimal、数字字符串）。"""
    out = []
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s):
            out.append(c)
            continue
        if s.dtype == object:
            v = _to_num(s)
            if v.notna().mean() >= 0.9 and v.notna().any():
                out.append(c)
    return out


def _dim_numeric(df: pd.DataFrame, num: list[str]) -> set[str]:
    """看起来像“编码维度”的数值列（hour_of_day / level_rank 等），不该当度量。"""
    dims: set[str] = set()
    for c in num:
        name = str(c).lower()
        if re.search(r"(^|_)(hour|day|month|year|week|rank|level|code|id|no)($|_)", name):
            v = _to_num(df[c]).dropna()
            if len(v) and v.nunique() <= 60 and (v % 1 == 0).all():
                dims.add(c)
    return dims


def _label_cols(df: pd.DataFrame, num: list[str]) -> list[str]:
    """非度量列 = 全部列 - 度量列（编码维度会被剔出度量）。"""
    dims = _dim_numeric(df, num)
    return [c for c in df.columns if c not in num or c in dims]


def _measure_cols(df: pd.DataFrame, num: list[str]) -> list[str]:
    dims = _dim_numeric(df, num)
    return [c for c in num if c not in dims]


def _share_like(df: pd.DataFrame, question: str, num: list[str]) -> bool:
    """是不是“看结构”的问题：问题里带占比词，或结果本身就是比例列。"""
    q = (question or "").lower()
    if any(h in q for h in SHARE_HINTS):
        return True
    for c in num:
        if any(h in str(c) for h in RATE_HINTS):
            return True
        v = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(v) and v.max() <= 1.000001 and 0.98 <= v.sum() <= 1.02:
            return True
    return False


def pick_chart(df: pd.DataFrame, question: str = "") -> tuple[str, str]:
    """返回 (图表类型, 选择理由)。理由显示在页面上，方便判断该不该手动改。"""
    if df is None or df.empty:
        return "table", "没有数据"
    num = _measure_cols(df, _numeric_cols(df))
    labs = _label_cols(df, _numeric_cols(df))
    if not num:
        return "table", "没有数值列，画图没有意义"
    if len(df) == 1:
        return "table", "只有一行，已用指标卡展示"

    time_cols = [c for c in labs if _is_timey(c, df[c])]
    if time_cols and len(df) >= 3:
        return "line", "含时间列，按时间看趋势"

    if labs and len(df) > 15:
        ratio = df[labs[0]].nunique() / max(1, len(df))
        if ratio > 0.95:
            return "table", "首列几乎每行都不同，是明细不是分类"

    if _share_like(df, question, num):
        if len(df) <= 8:
            return "pie", "占比类问题且项目不多，用饼图看结构"
        return "bar", "占比类问题但项目较多，用条形更清楚"

    q = (question or "").lower()
    if len(num) >= 2 and len(df) >= 20 and any(h in q for h in REL_HINTS):
        return "scatter", "两个数值看关系"

    if len(num) == 1 and len(labs) >= 2 and 2 <= df[labs[1]].nunique() <= 8:
        return "bar", f"按「{labs[0]}」分组、用「{labs[1]}」分系列对比"

    if len(df) > 12:
        return "bar", "分类较多，用条形并按数值排序"
    return "bar", "分类对比"


def _cut(s, n: int = 12) -> str:
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def _scale_of(values: list[float]) -> tuple[float, str]:
    """数值量纲换算：>=1 亿用“亿”，>=1 万用“万”，避免坐标轴出现 36116687.06。"""
    v = [abs(x) for x in values if x is not None and not pd.isna(x)]
    if not v:
        return 1.0, ""
    m = max(v)
    if m >= 1e8:
        return 1e8, "（亿元）"
    if m >= 1e4:
        return 1e4, "（万元）"
    return 1.0, ""


def _pivot_series(df: pd.DataFrame, x_col: str, s_col: str,
                  v_col: str) -> tuple[list[str], list[dict]]:
    """一维表转多系列：x 取一组，series 取另一组。"""
    piv = df.pivot_table(index=x_col, columns=s_col, values=v_col,
                         aggfunc="sum").fillna(0)
    xs = [str(i) for i in piv.index]
    series = [{"name": str(c), "data": [float(v) for v in piv[c].tolist()]}
              for c in piv.columns]
    return xs, series


def chart_option(df: pd.DataFrame, kind: str, title: str = "") -> dict:
    """DataFrame → ECharts option：排序、截断、量纲换算都在这里做。"""
    cols = list(df.columns)
    _all = _numeric_cols(df)
    num = _measure_cols(df, _all)
    labs = _label_cols(df, _all)
    _v0 = _to_num(df[num[0]]).fillna(0) if len(num) == 1 and len(df) > 0 else None
    is_pct = any(any(h in str(c) for h in RATE_HINTS) for c in num) or \
        (_v0 is not None and _v0.max() <= 1.000001 and 0.98 <= _v0.sum() <= 1.02)

    base = {
        "backgroundColor": "transparent",
        "title": {"text": title, "left": "center",
                  "textStyle": {"color": "#e9f4ff", "fontSize": 13}},
        "textStyle": {"fontFamily": "Microsoft YaHei, PingFang SC, sans-serif",
                      "color": "#dbe9f8"},
        "color": ["#35d6ff", "#7c5cff", "#ffc857", "#27e2a4", "#ff7ab6", "#4f8bff"],
        "animationDuration": 600,
    }

    # ---------------- 散点
    if kind == "scatter":
        xs = num[0]
        ys = num[1] if len(num) > 1 else num[0]
        return {
            **base,
            "tooltip": {"trigger": "item"},
            "grid": {"left": 76, "right": 30, "top": 30, "bottom": 46},
            "xAxis": {"type": "value", "name": str(xs),
                      "nameTextStyle": {"color": "#8aa9cc"},
                      "axisLabel": {"color": "#8aa9cc"},
                      "splitLine": {"lineStyle": {"color": "rgba(120,170,220,.12)"}}},
            "yAxis": {"type": "value", "name": str(ys),
                      "nameTextStyle": {"color": "#8aa9cc"},
                      "axisLabel": {"color": "#8aa9cc"},
                      "splitLine": {"lineStyle": {"color": "rgba(120,170,220,.12)"}}},
            "series": [{
                "type": "scatter", "symbolSize": 8, "itemStyle": {"opacity": .72},
                "data": [[float(r[xs]), float(r[ys])] for _, r in df.iterrows()
                         if not (pd.isna(r[xs]) or pd.isna(r[ys]))],
            }],
        }

    # ---------------- 组织 x 与系列
    if len(labs) >= 2 and len(num) == 1 and 2 <= df[labs[1]].nunique() <= 8:
        xs, series = _pivot_series(df, labs[0], labs[1], num[0])
    else:
        def label_of(row) -> str:
            return " / ".join(str(row[c]) for c in labs[:2]) if labs else str(row[cols[0]])
        xs = [label_of(r) for _, r in df.iterrows()]
        series = [{"name": str(c),
                   "data": [None if pd.isna(v) else float(v)
                            for v in _to_num(df[c])]}
                  for c in num[:4]]

    # ---------------- 排序：时间升序，其余按数值降序
    if kind == "line" and labs and _is_timey(labs[0], df[labs[0]]):
        order = sorted(range(len(xs)), key=lambda i: str(xs[i]))
    elif kind == "line":
        order = list(range(len(xs)))
    else:
        totals = [sum((s["data"][i] or 0) for s in series) for i in range(len(xs))]
        order = sorted(range(len(xs)), key=lambda i: -totals[i])
    xs = [_cut(xs[i]) for i in order]
    for s in series:
        s["data"] = [s["data"][i] for i in order]

    # ---------------- 饼图：前 8 项 + 其他
    if kind == "pie":
        vals = [v or 0 for v in series[0]["data"]]
        if len(xs) > 9:
            xs = xs[:8] + ["其他"]
            vals = vals[:8] + [sum(vals[8:])]
        return {
            **base,
            "tooltip": {"trigger": "item"},
            "legend": {"type": "scroll", "bottom": 0,
                       "textStyle": {"color": "#8aa9cc", "fontSize": 11}},
            "series": [{
                "type": "pie", "radius": ["40%", "66%"], "center": ["50%", "44%"],
                "minAngle": 3, "avoidLabelOverlap": True,
                "label": {"color": "#dbe9f8", "formatter": "{b}\n{d}%", "fontSize": 11},
                "labelLine": {"length": 8, "length2": 6},
                "data": [{"name": xs[i], "value": vals[i]} for i in range(len(xs))],
            }],
        }

    # ---------------- 折线 / 柱状：量纲换算
    flat = [v for s in series for v in s["data"] if v is not None]
    div, unit = _scale_of(flat)
    if is_pct:
        div, unit = 1.0, "（比例）"
    for s in series:
        s["data"] = [None if v is None else round(v / div, 4) for v in s["data"]]

    horizontal = kind == "bar" and (len(xs) > 8 or any(len(s) > 8 for s in xs))
    cat_axis = {
        "type": "category", "data": xs,
        "axisLabel": {"color": "#8aa9cc",
                      "interval": 0 if len(xs) <= 12 else "auto",
                      "rotate": 0 if horizontal else (30 if len(xs) > 6 else 0)},
        "axisLine": {"lineStyle": {"color": "rgba(120,170,220,.3)"}},
    }
    val_axis = {"type": "value", "name": unit.strip("（）"),
                "nameTextStyle": {"color": "#8aa9cc", "fontSize": 10},
                "axisLabel": {"color": "#8aa9cc"},
                "splitLine": {"lineStyle": {"color": "rgba(120,170,220,.12)"}}}

    if kind == "line":
        return {
            **base,
            "tooltip": {"trigger": "axis"},
            "legend": {"type": "scroll", "top": 6, "right": 10,
                       "textStyle": {"color": "#8aa9cc", "fontSize": 11}},
            "grid": {"left": 66, "right": 40, "top": 48, "bottom": 46},
            "xAxis": {**cat_axis, "rotate": 30 if len(xs) > 12 else 0},
            "yAxis": val_axis,
            "dataZoom": [{"type": "inside"}] if len(xs) > 30 else [],
            "series": [{"name": s["name"], "type": "line",
                        "smooth": len(xs) <= 60,
                        "symbolSize": 4 if len(xs) > 40 else 6,
                        "showSymbol": len(xs) <= 40, "data": s["data"]}
                       for s in series],
        }

    return {
        **base,
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"type": "scroll", "top": 6, "right": 10,
                   "textStyle": {"color": "#8aa9cc", "fontSize": 11}},
        "grid": {"left": 72 if horizontal else 66, "right": 28,
                 "top": 46, "bottom": 46 if horizontal else 58},
        "xAxis": val_axis if horizontal else cat_axis,
        "yAxis": cat_axis if horizontal else val_axis,
        "series": [{
            "name": s["name"], "type": "bar", "barMaxWidth": 30,
            "data": s["data"],
            "itemStyle": {"borderRadius": [3, 3, 0, 0] if not horizontal else [0, 3, 3, 0]},
            "label": {"show": len(series) == 1 and len(xs) <= 12,
                      "position": "right" if horizontal else "top",
                      "color": "#9fb8d4", "fontSize": 9},
        } for s in series],
    }


def render_chart(df: pd.DataFrame, kind: str, height: int = 380, title: str = "") -> None:
    option = chart_option(df, kind, title)
    html = f"""
    <div id="c" style="width:100%;height:{height - 10}px;"></div>
    <script src="{ECHARTS_SRC}" onerror="this.onerror=null;this.src='{ECHARTS_CDN}'"></script>
    <script>
      (function() {{
        function draw() {{
          if (typeof echarts === 'undefined') {{ setTimeout(draw, 120); return; }}
          var el = document.getElementById('c');
          var chart = echarts.init(el, null, {{renderer: 'canvas'}});
          chart.setOption({json.dumps(option, ensure_ascii=False)});
          window.addEventListener('resize', function() {{ chart.resize(); }});
        }}
        draw();
      }})();
    </script>
    """
    components.html(html, height=height, scrolling=False)


# ---------------------------------------------------------------- 单条问答渲染
def render_turn(turn: dict, idx: int) -> None:
    q = turn["question"]
    st.markdown(f'<div class="q-card">🙋 {q}</div>', unsafe_allow_html=True)

    if turn.get("error"):
        st.markdown(
            f'<span class="badge err">失败</span>'
            f'<span class="meta-line">{turn["error"]}</span>', unsafe_allow_html=True)
        if turn.get("sql"):
            st.code(turn["sql"], language="sql")
        return

    badges = [f'<span class="badge">{turn.get("mode", "LLM")}</span>']
    if turn.get("elapsed"):
        badges.append(f'<span class="badge">执行 {turn["elapsed"]:.2f}s</span>')
    if turn.get("tokens"):
        badges.append(f'<span class="badge warn">{turn["tokens"]} tokens</span>')
    badges.append(f'<span class="badge">{len(turn["df"])} 行</span>')
    st.markdown("".join(badges), unsafe_allow_html=True)

    with st.expander("生成的 SQL（已通过只读校验）", expanded=False):
        st.code(turn["sql"], language="sql")

    df: pd.DataFrame = turn["df"]
    if df is None or df.empty:
        st.info("查询成功，但没有命中数据。")
        return

    # 单行结果 → 指标卡
    if len(df) == 1 and len(_numeric_cols(df)) >= 1:
        num = _numeric_cols(df)
        cols = st.columns(min(4, len(num)))
        for i, c in enumerate(num[:4]):
            with cols[i % len(cols)]:
                v = df[c].iloc[0]
                st.metric(label=str(c), value=f"{v:,.2f}" if isinstance(v, float) else f"{v:,}")
        with st.expander("查看原始结果"):
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        tab1, tab2 = st.tabs(["📊 图表", "📋 数据表"])
        with tab1:
            auto, why = pick_chart(df, q)
            kind = st.radio(
                "图表类型", ["自动", "折线", "柱状", "饼图", "散点", "仅表格"],
                index=0, horizontal=True, key=f"kind{idx}",
                help=f"自动推断：{auto}（{why}）",
            )
            st.caption(f"自动选图：{auto} ｜ 理由：{why}")
            mapping = {"自动": auto, "折线": "line", "柱状": "bar",
                       "饼图": "pie", "散点": "scatter", "仅表格": "table"}
            chosen = mapping[kind]
            if chosen == "table":
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                render_chart(df, chosen, title=q[:38])
        with tab2:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                "下载 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"nl2sql_{datetime.now():%H%M%S}.csv", mime="text/csv",
                key=f"dl{idx}",
            )
    st.divider()


# ---------------------------------------------------------------- 执行一次问答
def run_question(question: str) -> dict:
    turn = {"question": question, "sql": "", "df": None,
            "elapsed": 0.0, "error": None, "mode": "LLM", "tokens": None,
            "ts": datetime.now().strftime("%H:%M:%S")}
    t0 = time.perf_counter()
    try:
        if llm_client.has_key():
            with st.spinner("① 正在调用大模型生成 SQL …"):
                schema_text = nl2sql.load_schema_text()
                chain = nl2sql.build_chain()
                raw = chain.invoke({"schema": schema_text, "question": question})
                sql = nl2sql.guard_sql(nl2sql.cleanse_sql(raw))
            turn["sql"] = sql
            with st.spinner("② 正在 Hive 上执行（首次查询可能 5~15 秒）…"):
                turn["df"] = hive_client.query_df(sql)
        else:
            match = next((s for q, s in nl2sql.DEMO_CASES if q == question), None)
            if match is None:
                match = nl2sql.DEMO_CASES[0][1]
            turn["mode"] = "演示（预置 SQL）"
            turn["sql"] = nl2sql.guard_sql(nl2sql.cleanse_sql(match))
            with st.spinner("正在 Hive 上执行（演示模式）…"):
                turn["df"] = hive_client.query_df(turn["sql"])
    except Exception as exc:  # noqa: BLE001
        turn["error"] = f"{type(exc).__name__}: {exc}"
    turn["elapsed"] = time.perf_counter() - t0
    return turn


def main() -> None:
    sidebar()

    st.title("🐳 云购生活 · 智能经营问答")
    st.markdown(
        '<span class="meta-line">自然语言 → SQL → Hive 执行 → 表格与图表 ｜ '
        '数据源：ydsh_ads（11 张 ADS 应用层表）｜ 只读校验：仅允许 SELECT / WITH，自动补 LIMIT 200</span>',
        unsafe_allow_html=True)
    st.write("")

    if "history" not in st.session_state:
        st.session_state["history"] = []

    # 侧边栏点击示例 → 走同一条提交流程
    pending = st.session_state.pop("pending_q", None)

    with st.form("ask", clear_on_submit=False):
        c1, c2 = st.columns([5, 1])
        with c1:
            question = st.text_input(
                "请输入你的问题",
                value=pending or "",
                placeholder="例如：广东省 2024 年 12 月的销售额是多少？",
                label_visibility="collapsed",
            )
        with c2:
            submitted = st.form_submit_button("提问 ⏎", use_container_width=True, type="primary")

    if (submitted or pending) and question.strip():
        turn = run_question(question.strip())
        st.session_state["history"].insert(0, turn)
        st.rerun()

    if not st.session_state["history"]:
        st.info("在上方输入问题，或点左侧示例问题开始。第一次查询 Hive 需要 5~15 秒。")
        return

    st.markdown(f'<span class="meta-line">共 {len(st.session_state["history"])} 轮对话（最新在上）</span>',
                unsafe_allow_html=True)
    st.write("")
    for i, turn in enumerate(st.session_state["history"]):
        render_turn(turn, i)


if __name__ == "__main__":
    main()