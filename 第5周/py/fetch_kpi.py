"""第 5 周 · 文档取数（从 ClickHouse 副本快速取指标，用于写文档时核对数字）

为什么用 ClickHouse 而不是 Hive：写文档要反复核对几十个数，Hive 每条 1~15 秒，
CH 每条 30~50 毫秒；两者数据完全一致（第 5 周端到端自检第 6 步已验证 11 张表逐表行数相等）。

用法：python fetch_kpi.py
输出：屏幕 + ../evidence/kpi_for_docs.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "第4周" / "py"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env", override=False)

import ch_client  # noqa: E402

LINES: list[str] = []


def show(title: str, sql: str) -> None:
    df = ch_client.query_df(sql)
    LINES.append("")
    LINES.append(f"--- {title}")
    LINES.append(df.to_string(index=False))


show("月度 GMV / 订单量 / 客单价", """
select stat_month, round(gmv, 2) gmv, order_cnt, round(aov, 2) aov,
       round(valid_gmv, 2) valid_gmv, round(gmv_mom * 100, 2) mom_pct
from ydsh_ads.ads_kpi_month order by stat_month
""")

show("品类销售额（12 个月合计）", """
select category, round(amt, 2) sales_amt,
       round(amt / 35833305.06 * 100, 2) share_pct,
       qty item_qty
from (select category, sum(sales_amt) amt, sum(item_qty) qty
      from ydsh_ads.ads_category_rank group by category)
order by amt desc
""")

show("省份 GMV（12 个月合计）", """
select province, region_area, round(amt, 2) gmv,
       round(amt / 36116687.06 * 100, 2) share_pct, oc order_cnt, bc buyer_cnt
from (select province, any(region_area) region_area, sum(gmv) amt,
             sum(order_cnt) oc, sum(buyer_cnt) bc
      from ydsh_ads.ads_province_sales group by province)
order by amt desc
""")

show("门店 Top10（按 store_id 聚合，避免同名门店被合并）", """
select store_id, store_name, city, round(amt, 2) gmv, oc order_cnt
from (select store_id, any(store_name) store_name, any(city) city,
             sum(gmv) amt, sum(order_cnt) oc
      from ydsh_ads.ads_store_rank group by store_id)
order by amt desc limit 10
""")

show("渠道（12 个月合计）", """
select channel_name, round(amt, 2) gmv, round(amt / 36116687.06 * 100, 2) share_pct, oc order_cnt
from (select channel_name, sum(gmv) amt, sum(order_cnt) oc
      from ydsh_ads.ads_channel_month group by channel_name)
order by amt desc
""")

show("支付方式（12 个月合计）", """
select pay_type, round(amt, 2) gmv, round(amt / 36116687.06 * 100, 2) share_pct, oc order_cnt
from (select pay_name pay_type, sum(gmv) amt, sum(order_cnt) oc
      from ydsh_ads.ads_pay_type_month group by pay_name)
order by amt desc
""")

show("RFM 分层人数", """
select rfm_segment, count(*) users, round(sum(monetary), 2) monetary
from ydsh_ads.ads_user_rfm group by rfm_segment order by users desc
""")

show("行为漏斗", """
select * from ydsh_ads.ads_behavior_funnel order by stat_month
""")

show("时段分布（核对随机性）", """
select hour, round(amt, 2) sales, oc orders
from (select hour_of_day hour, sum(sales_amt) amt, sum(order_cnt) oc
      from ydsh_ads.ads_hour_category group by hour_of_day)
order by hour
""")

show("ADS 各表行数（与 Hive 一致性基准）", """
select 'ads_kpi_overview' t, count(*) n from ydsh_ads.ads_kpi_overview
union all select 'ads_kpi_month', count(*) from ydsh_ads.ads_kpi_month
union all select 'ads_sales_daily', count(*) from ydsh_ads.ads_sales_daily
union all select 'ads_category_rank', count(*) from ydsh_ads.ads_category_rank
union all select 'ads_province_sales', count(*) from ydsh_ads.ads_province_sales
union all select 'ads_store_rank', count(*) from ydsh_ads.ads_store_rank
union all select 'ads_channel_month', count(*) from ydsh_ads.ads_channel_month
union all select 'ads_behavior_funnel', count(*) from ydsh_ads.ads_behavior_funnel
union all select 'ads_user_rfm', count(*) from ydsh_ads.ads_user_rfm
union all select 'ads_pay_type_month', count(*) from ydsh_ads.ads_pay_type_month
union all select 'ads_hour_category', count(*) from ydsh_ads.ads_hour_category
order by 1
""")

text = "\n".join(LINES)
print(text)
out = ROOT / "evidence" / "kpi_for_docs.txt"
out.write_text(text, encoding="utf-8")
print(f"\n已写入 {out}")