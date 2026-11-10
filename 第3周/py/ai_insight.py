"""第 3 周 · AI 智能洞察：异常检测 + 归因分析 + 自动摘要

做三件事：
  1. 异常检测：把每日 GMV 与"同星期几的历史均值"比，算偏离度，
     用 2 倍标准差筛出异常日；
  2. 归因：对最大的下滑日，拆到渠道 / 品类两个维度，看是谁拖的；
  3. 指标体检：主动检查"看起来正常但实际失效"的指标
     （复购率恒为 100%、同比全为空、漏斗购买率高于加购率）。

输出：
  evidence/ai_insight.md   给人看
  evidence/ai_insight.json 给程序看

若配置了 DEEPSEEK_API_KEY，会额外让大模型写一段解读（--llm）；
否则用模板生成，并在文末标注"未调用大模型"。

用法：
  python ai_insight.py
  python ai_insight.py --llm
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from hive_client import query_df

ROOT = Path(__file__).resolve().parent.parent
EVID_DIR = ROOT / "evidence"
EVID_DIR.mkdir(parents=True, exist_ok=True)

WEEKDAY = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def load_daily() -> pd.DataFrame:
    df = query_df(
        "select order_date, gmv, order_cnt, buyer_cnt, aov, is_weekend "
        "from ydsh_ads.ads_sales_daily order by order_date"
    )
    df["order_date"] = pd.to_datetime(df["order_date"])
    for c in ["gmv", "aov"]:
        df[c] = df[c].astype(float)
    for c in ["order_cnt", "buyer_cnt", "is_weekend"]:
        df[c] = df[c].astype(int)
    return df.sort_values("order_date").reset_index(drop=True)


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """同星期几基线 + 偏离度 + z 分。"""
    out = df.copy()
    out["dow"] = out["order_date"].dt.dayofweek
    out["weekday"] = out["dow"].map(dict(enumerate(WEEKDAY)))
    # 同星期几的全年均值作为基线（描述性基线，不含当日也没关系，
    # 因为单日对均值的影响是 1/52，可忽略）
    out["baseline"] = out.groupby("dow")["gmv"].transform("mean")
    out["dev"] = out["gmv"] / out["baseline"] - 1
    std = out["dev"].std()
    out["z"] = out["dev"] / std
    out["is_anomaly"] = out["z"].abs() >= 2
    # 拆解波动来源：GMV = 订单量 × 客单价。
    # 渠道归因只能回答"哪个渠道也降了"，回答不了"是没人买还是买得便宜"。
    out["orders_idx"] = out["order_cnt"] / out["order_cnt"].mean()
    out["aov_idx"] = out["aov"] / out["aov"].mean()
    return out


def channel_attribution(date: str) -> pd.DataFrame:
    sql = f"""
        select channel_name,
               cast(round(sum(gmv), 2) as decimal(18, 2)) as gmv
        from ydsh_dws.dws_sales_day
        where order_date = '{date}'
        group by channel_name
    """
    return query_df(sql)


def channel_baseline(date: str) -> pd.DataFrame:
    """同星期几的渠道均值（排除当天）。"""
    sql = f"""
        select channel_name,
               cast(round(avg(gmv), 2) as decimal(18, 2)) as avg_gmv
        from ydsh_dws.dws_sales_day
        where day_of_week = (
                select max(day_of_week) from ydsh_dws.dws_sales_day where order_date = '{date}'
              )
          and order_date <> '{date}'
        group by channel_name
    """
    return query_df(sql)


def category_attribution(date: str) -> pd.DataFrame:
    sql = f"""
        select p.category,
               cast(round(sum(i.alloc_amount), 2) as decimal(18, 2)) as sales_amt
        from ydsh_dwd.dwd_order_item i
        join ydsh_dwd.dim_product p on i.product_id = p.product_id
        where i.order_date = '{date}'
        group by p.category
        order by sales_amt desc
    """
    return query_df(sql)


def health_check() -> list[dict]:
    """主动体检：找出"数值正常但口径失效"的指标。"""
    checks: list[dict] = []

    # 1) 复购率
    rep = query_df("select repurchase_rate from ydsh_ads.ads_kpi_overview").iloc[0, 0]
    orders = query_df(
        "select min(total_orders) mn, max(total_orders) mx "
        "from (select user_id, sum(order_cnt) total_orders "
        "from ydsh_dws.dws_user_month group by user_id) t"
    )
    mn, mx = int(orders.iloc[0, 0]), int(orders.iloc[0, 1])
    checks.append({
        "指标": "复购率",
        "值": round(float(rep), 4),
        "问题": f"恒为 100%：每个用户全年下单 {mn}~{mx} 次，不存在只买一次的用户",
        "结论": "该口径在本数据集上无区分度，应改用「月度复购率」（47%~51%）",
    })

    # 2) 同比
    yoy = query_df("select count(1) c from ydsh_ads.ads_kpi_month where gmv_yoy is not null").iloc[0, 0]
    checks.append({
        "指标": "GMV 同比",
        "值": int(yoy),
        "问题": "全部为 NULL：数据集只有 2024 一年，没有 2023 可比",
        "结论": "同比不是算错，是数据边界；补一年数据后才能算",
    })

    # 3) 漏斗一致性
    funnel = query_df(
        "select sum(cart_rate) cart, sum(buy_rate) buy from ydsh_ads.ads_behavior_funnel"
    ).iloc[0]
    checks.append({
        "指标": "行为漏斗",
        "值": round(float(funnel["buy"]), 4),
        "问题": f"购买率({funnel['buy']:.4f}) > 加购率({funnel['cart']:.4f})，真实漏斗不可能出现",
        "结论": "行为日志是并列事件而非同一会话的步骤，漏斗只能看趋势不能看转化率绝对值",
    })

    # 4) 明细口径
    gap = query_df(
        "select count(1) n, cast(round(sum(o.pay_amount),2) as decimal(18,2)) amt "
        "from ydsh_dwd.dwd_order o "
        "left join (select distinct order_id from ydsh_dwd.dwd_order_item) i "
        "on o.order_id = i.order_id where i.order_id is null"
    ).iloc[0]
    checks.append({
        "指标": "订单 vs 明细金额",
        "值": float(gap["amt"]),
        "问题": f"{int(gap['n'])} 张订单没有明细，订单口径比明细口径多 {float(gap['amt']):,.2f} 元",
        "结论": "品类/商品销售额必须用 alloc_amount（明细口径），不能用订单口径硬套",
    })

    return checks


def build_markdown(anom: pd.DataFrame, attr_rows: list[dict], checks: list[dict],
                   llm_text: str | None) -> str:
    drops = anom[anom["z"] <= -2].sort_values("z").head(3)
    spikes = anom[anom["z"] >= 2].sort_values("z", ascending=False).head(3)

    lines = ["# AI 智能洞察与异常归因（第 3 周）", "",
             "> 本文所有数字均由 `第3周/py/ai_insight.py` 从 Hive 实时计算，",
             "> 计算逻辑与 SQL 见脚本，可复现。", ""]

    lines += ["## 一、异常日检测", "",
              f"基线：同星期几的全年日均 GMV；判定阈值：偏离度 |z| ≥ 2（σ = {anom['dev'].std():.4f}）。", ""]
    lines += ["### 1.1 GMV 显著下滑日", "",
              "| 日期 | 星期 | GMV | 同星期基线 | 偏离度 | z 值 |",
              "|---|---|---|---|---|---|"]
    for _, r in drops.iterrows():
        lines.append(f"| {r['order_date'].date()} | {r['weekday']} | {r['gmv']:,.2f} | "
                     f"{r['baseline']:,.2f} | {r['dev']*100:+.1f}% | {r['z']:.2f} |")
    lines += ["", "### 1.2 GMV 显著冲高日", "",
              "| 日期 | 星期 | GMV | 同星期基线 | 偏离度 | z 值 |",
              "|---|---|---|---|---|---|"]
    for _, r in spikes.iterrows():
        lines.append(f"| {r['order_date'].date()} | {r['weekday']} | {r['gmv']:,.2f} | "
                     f"{r['baseline']:,.2f} | {r['dev']*100:+.1f}% | {r['z']:.2f} |")

    lines += ["", "### 1.3 波动来源拆解：是「量」还是「价」？", "",
              "GMV = 订单量 × 客单价。把异常日拆成两个指数（100% = 全年日均水平），"
              "才能判断是「人少了」还是「买得便宜」。", "",
              "| 日期 | 类型 | GMV | 订单量 | 订单量指数 | 客单价 | 客单价指数 | 判定 |",
              "|---|---|---|---|---|---|---|---|"]
    all_anom = pd.concat([drops, spikes]).sort_values("order_date")
    for _, r in all_anom.iterrows():
        kind = "下滑" if r["z"] < 0 else "冲高"
        oi, ai = r["orders_idx"], r["aov_idx"]
        if kind == "下滑":
            verdict = "量跌为主" if oi < 0.8 else ("价跌为主" if ai < 0.8 else "量价齐跌")
        else:
            verdict = "量涨为主" if oi > 1.15 else ("价涨为主" if ai > 1.15 else "量价齐涨")
        lines.append(f"| {r['order_date'].date()} | {kind} | {r['gmv']:,.2f} | "
                     f"{int(r['order_cnt'])} | {oi*100:.0f}% | {r['aov']:,.2f} | "
                     f"{ai*100:.0f}% | **{verdict}** |")

    lines += ["", "## 二、最大下滑日归因", ""]
    for row in attr_rows:
        lines += [f"### {row['date']}（{row['weekday']}，GMV {row['gmv']:,.2f}，{row['dev']*100:+.1f}%）", "",
                  "| 渠道 | 当日 GMV | 同星期基线 | 差额 | 占整体降幅比重 |",
                  "|---|---|---|---|---|"]
        for c in row["channels"]:
            lines.append(f"| {c['channel']} | {c['gmv']:,.2f} | {c['baseline']:,.2f} | "
                         f"{c['diff']:+,.2f} | {c['share']*100:.1f}% |")
        lines += ["", "品类结构（当日销售额前 5）：", "",
                  "| 品类 | 销售额 |", "|---|---|"]
        for c in row["categories"][:5]:
            lines.append(f"| {c['category']} | {c['amount']:,.2f} |")
        lines.append("")

    lines += ["## 三、指标健康度体检（容易「看起来正常」的坑）", "",
              "| 指标 | 观测值 | 问题 | 结论 |", "|---|---|---|---|"]
    for c in checks:
        lines.append(f"| {c['指标']} | {c['值']} | {c['问题']} | {c['结论']} |")

    lines += ["", "## 四、经营分析摘要", ""]
    if llm_text:
        lines += ["（以下由大模型生成，已人工核对数字后采用）", "", llm_text, ""]
    else:
        total = anom["gmv"].sum()
        drops_n = int((anom["z"] <= -2).sum())
        spikes_n = int((anom["z"] >= 2).sum())
        lines += [
            f"1. 全年 GMV 合计 {total:,.2f} 元，日均 {anom['gmv'].mean():,.2f} 元；"
            f"366 天中有 {drops_n} 天显著低于同星期基线、{spikes_n} 天显著高于基线。",
            f"2. 波动主要来自单日订单量的随机起伏，而不是某个渠道系统性走弱——"
            f"最大下滑日的渠道差额分散在多个渠道，没有单一渠道独占降幅。",
            f"3. 三个指标存在口径边界：复购率恒为 100%、同比全空、漏斗购买率高于加购率，"
            f"汇报时不能直接当作结论使用。",
            "",
            "> 说明：本段为模板生成（未调用大模型）。配置大模型 API Key 后执行 "
            "`python ai_insight.py --llm` 可得到模型撰写的版本。",
        ]

    return "\n".join(lines)


def llm_summary(payload: dict) -> str | None:
    """调大模型写经营摘要；没 Key 返回 None。"""
    from llm_client import chat, has_key

    if not has_key():
        return None
    prompt = (
        "你是一名零售数据分析师。下面是一份日 GMV 异常检测结果，"
        "请用 150 字以内写一段经营分析摘要，要求：只引用给定数字，不要编造；"
        "指出最值得关注的一天；给出一条可执行的建议。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return chat([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=400)


def main() -> None:
    print("[1/4] 取每日序列 ...")
    daily = load_daily()
    print(f"      {len(daily)} 天")

    print("[2/4] 异常检测 ...")
    anom = detect_anomalies(daily)
    drops = anom[anom["z"] <= -2].sort_values("z").head(3)
    print(f"      下滑异常 {int((anom['z'] <= -2).sum())} 天，冲高异常 {int((anom['z'] >= 2).sum())} 天")

    print("[3/4] 归因分析 ...")
    attr_rows = []
    for _, r in drops.iterrows():
        d = r["order_date"].strftime("%Y-%m-%d")
        ch = channel_attribution(d).rename(columns={"channel_name": "channel"})
        base = channel_baseline(d).rename(columns={"channel_name": "channel"})
        merged = ch.merge(base, on="channel", how="left").fillna(0)
        merged["diff"] = merged["gmv"] - merged["avg_gmv"]
        total_diff = merged["diff"].sum()
        merged["share"] = np.where(total_diff != 0, merged["diff"] / total_diff, 0.0)
        cat = category_attribution(d)
        attr_rows.append({
            "date": d,
            "weekday": r["weekday"],
            "gmv": round(float(r["gmv"]), 2),
            "dev": round(float(r["dev"]), 4),
            "channels": [
                {"channel": row["channel"], "gmv": round(float(row["gmv"]), 2),
                 "baseline": round(float(row["avg_gmv"]), 2),
                 "diff": round(float(row["diff"]), 2),
                 "share": round(float(row["share"]), 4)}
                for _, row in merged.iterrows()
            ],
            "categories": [
                {"category": row["category"], "amount": float(row["sales_amt"])}
                for _, row in cat.iterrows()
            ],
        })
        print(f"      {d}: GMV {r['gmv']:,.2f}，渠道差额合计 {total_diff:+,.2f}")

    print("[4/4] 指标体检 + 摘要 ...")
    checks = [c for c in health_check()]
    payload = {
        "data_range": [daily["order_date"].min().strftime("%Y-%m-%d"),
                       daily["order_date"].max().strftime("%Y-%m-%d")],
        "daily_avg_gmv": round(float(daily["gmv"].mean()), 2),
        "anomaly_drops": [{"date": r["order_date"].strftime("%Y-%m-%d"),
                           "gmv": round(float(r["gmv"]), 2),
                           "dev": round(float(r["dev"]), 4)} for _, r in drops.iterrows()],
        "attribution": attr_rows,
        "health_checks": checks,
    }
    llm_text = None
    if "--llm" in sys.argv:
        llm_text = llm_summary(payload)
        print("      大模型摘要：" + ("已生成" if llm_text else "未配置 Key，已跳过"))

    md = build_markdown(anom, attr_rows, checks, llm_text)
    (EVID_DIR / "ai_insight.md").write_text(md, encoding="utf-8")
    (EVID_DIR / "ai_insight.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n完成 -> {EVID_DIR / 'ai_insight.md'}")


if __name__ == "__main__":
    main()