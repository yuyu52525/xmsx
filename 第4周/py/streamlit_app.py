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
TIME_HINTS = ("date", "month", "day", "week", "hour", "时间", "月份", "日期", "时段")


def _is_timey(col: str, s: pd.Series) -> bool:
    name = str(col).lower()
    if any(h in name for h in TIME_HINTS):
        return True
    if s.dtype.kind in "biufc":
        return False
    return s.astype(str).str.match(r"^\d{4}(-\d{2}){0,2}").fillna(False).all()


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def guess_chart(df: pd.DataFrame) -> str:
    """给一句 SQL 的结果猜一个合适的图：默认返回 line/bar/pie/scatter/table。"""
    if df is None or df.empty:
        return "table"
    num = _numeric_cols(df)
    if len(df) == 1 or not num:
        return "table"
    time_cols = [c for c in df.columns if _is_timey(c, df[c])]
    if time_cols and len(df) >= 3:
        return "line"
    if len(num) >= 2 and len(df) >= 20:
        return "scatter"
    if len(df) <= 12 and len(num) == 1:
        return "pie"
    return "bar"


def chart_option(df: pd.DataFrame, kind: str, title: str = "") -> dict:
    """把 DataFrame 转成 ECharts option（够用的通用版本，不做过度设计）。"""
    cols = list(df.columns)
    num = _numeric_cols(df)
    cats = [c for c in cols if c not in num]

    def label_of(row) -> str:
        if cats:
            return " / ".join(str(row[c]) for c in cats[:2])
        return str(row[cols[0]])

    x = [label_of(r) for _, r in df.iterrows()]
    y1 = num[0] if num else cols[-1]

    base = {
        "backgroundColor": "transparent",
        "title": {"text": title, "left": "center", "textStyle": {"color": "#e9f4ff", "fontSize": 13}},
        "tooltip": {"trigger": "axis" if kind in ("line", "bar") else "item"},
        "textStyle": {"fontFamily": "Microsoft YaHei, PingFang SC, sans-serif", "color": "#dbe9f8"},
        "color": ["#35d6ff", "#7c5cff", "#ffc857", "#27e2a4", "#ff7ab6", "#4f8bff"],
        "animationDuration": 600,
    }

    if kind == "line":
        time_cols = [c for c in df.columns if _is_timey(c, df[c])]
        xdata = [str(v) for v in df[time_cols[0]]] if time_cols else x
        return {
            **base,
            "legend": {"top": 6, "right": 10, "textStyle": {"color": "#8aa9cc", "fontSize": 11}},
            "grid": {"left": 60, "right": 40, "top": 46, "bottom": 40},
            "xAxis": {"type": "category", "data": xdata,
                      "axisLabel": {"color": "#8aa9cc", "rotate": 30 if len(xdata) > 12 else 0},
                      "axisLine": {"lineStyle": {"color": "rgba(120,170,220,.3)"}}},
            "yAxis": {"type": "value", "axisLabel": {"color": "#8aa9cc"},
                      "splitLine": {"lineStyle": {"color": "rgba(120,170,220,.12)"}}},
            "series": [{
                "name": c, "type": "line", "smooth": True, "symbolSize": 5,
                "data": [None if pd.isna(v) else float(v) for v in df[c]],
                "areaStyle": {"opacity": 0.12} if i == 0 else None,
            } for i, c in enumerate(num)],
        }

    if kind == "bar":
        series = [{
            "name": c, "type": "bar", "barMaxWidth": 34,
            "data": [None if pd.isna(v) else float(v) for v in df[c]],
            "itemStyle": {"borderRadius": [3, 3, 0, 0]},
        } for c in num]
        return {
            **base,
            "legend": {"top": 6, "right": 10, "textStyle": {"color": "#8aa9cc", "fontSize": 11}},
            "grid": {"left": 60, "right": 40, "top": 46, "bottom": 48},
            "xAxis": {"type": "category", "data": x,
                      "axisLabel": {"color": "#8aa9cc", "interval": 0, "rotate": 30},
                      "axisLine": {"lineStyle": {"color": "rgba(120,170,220,.3)"}}},
            "yAxis": {"type": "value", "axisLabel": {"color": "#8aa9cc"},
                      "splitLine": {"lineStyle": {"color": "rgba(120,170,220,.12)"}}},
            "series": series,
        }

    if kind == "pie":
        return {
            **base,
            "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c}（{d}%）"},
            "legend": {"bottom": 0, "textStyle": {"color": "#8aa9cc", "fontSize": 11}},
            "series": [{
                "type": "pie", "radius": ["42%", "68%"], "center": ["50%", "46%"],
                "label": {"color": "#dbe9f8", "formatter": "{b}\n{d}%"},
                "data": [{"name": x[i], "value": float(df[y1].iloc[i])} for i in range(len(df))],
            }],
        }

    if kind == "scatter":
        xs = num[0]
        ys = num[1] if len(num) > 1 else num[0]
        return {
            **base,
            "tooltip": {"trigger": "item", "formatter": "{c}"},
            "grid": {"left": 70, "right": 30, "top": 30, "bottom": 46},
            "xAxis": {"type": "value", "name": xs, "nameTextStyle": {"color": "#8aa9cc"},
                      "axisLabel": {"color": "#8aa9cc"},
                      "splitLine": {"lineStyle": {"color": "rgba(120,170,220,.12)"}}},
            "yAxis": {"type": "value", "name": ys, "nameTextStyle": {"color": "#8aa9cc"},
                      "axisLabel": {"color": "#8aa9cc"},
                      "splitLine": {"lineStyle": {"color": "rgba(120,170,220,.12)"}}},
            "series": [{
                "type": "scatter", "symbolSize": 8, "itemStyle": {"opacity": .72},
                "data": [[float(r[xs]), float(r[ys])] for _, r in df.iterrows()
                         if not (pd.isna(r[xs]) or pd.isna(r[ys]))],
            }],
        }

    return base


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
            auto = guess_chart(df)
            kind = st.radio(
                "图表类型", ["自动", "折线", "柱状", "饼图", "散点", "仅表格"],
                index=0, horizontal=True, key=f"kind{idx}",
                help=f"自动推断结果：{auto}",
            )
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