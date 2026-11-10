"""第 3 周 · 把 KPI 结果导出成 Excel（交付物 2 的表格版）

为什么单独写一个导出脚本，而不是手抄进 Excel：
  手抄的数一定会和 Hive 里的数分叉，等答辩被问"这个数怎么来的"就答不上。
  这里每个单元格都由 SQL 现算，sheet 名即报表名，口径与 ads_kpi_report.sql 一致。

用法：
  python export_kpi_xlsx.py
输出：
  docs/KPI指标结果表.xlsx
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from hive_client import query_df

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "KPI指标结果表.xlsx"

HEADER_FILL = PatternFill("solid", fgColor="2F5597")
HEADER_FONT = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name="微软雅黑", size=10)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# (sheet 名, 说明, SQL)
SHEETS: list[tuple[str, str, str]] = [
    (
        "核心KPI总览",
        "全周期 2024-01-01 ~ 2024-12-31，金额单位：元",
        """select stat_scope `统计范围`, gmv `GMV`, valid_gmv `有效GMV`, order_cnt `订单量`,
                  valid_order_cnt `有效订单量`, buyer_cnt `下单用户数`, aov `客单价`,
                  arpu `ARPU`, valid_revenue_rate `有效营收占比`, cancel_rate `取消率`,
                  refund_rate `退款中占比`, avg_order_items `件数每单`
           from ydsh_ads.ads_kpi_overview""",
    ),
    (
        "月度KPI",
        "含环比；同比全为空（只有 2024 一年数据）",
        """select stat_month `月份`, gmv `GMV`, valid_gmv `有效GMV`, order_cnt `订单量`,
                  buyer_cnt `下单用户`, aov `客单价`, arpu `ARPU`,
                  repurchase_rate `当月复购率`, gmv_mom `GMV环比`
           from ydsh_ads.ads_kpi_month order by stat_month""",
    ),
    (
        "品类销售榜",
        "销售额用明细分摊口径 alloc_amount，合计 35,833,305.06",
        """select category `品类`, sum(sales_amt) `销售额`, sum(item_qty) `销量`,
                  sum(order_cnt) `订单数`,
                  sum(sales_amt)/sum(item_qty) `件均价`
           from ydsh_ads.ads_category_rank group by category order by `销售额` desc""",
    ),
    (
        "省份销售榜",
        "人均消费 = 全年 GMV / 全年下单用户数",
        """select province `省份`, region_area `大区`, sum(gmv) `GMV`,
                  sum(order_cnt) `订单量`, sum(buyer_cnt) `下单人次`,
                  sum(gmv)/sum(buyer_cnt) `人均消费`
           from ydsh_ads.ads_province_sales group by province, region_area
           order by `GMV` desc""",
    ),
    (
        "门店销售榜",
        "坪效 = 门店 GMV / 营业面积，按月取均值",
        """select store_name `门店`, province `省份`, city `城市`,
                  sum(gmv) `GMV`, sum(order_cnt) `订单量`,
                  avg(sales_per_sqm) `月均坪效`
           from ydsh_ads.ads_store_rank group by store_name, province, city
           order by `GMV` desc""",
    ),
    (
        "渠道结构",
        "线上合计 75.07%，门店 24.93%",
        """select channel_name `渠道`, is_online `是否线上`, sum(gmv) `GMV`,
                  sum(order_cnt) `订单量`,
                  sum(gmv)/sum(sum(gmv)) over () `GMV占比`
           from ydsh_ads.ads_channel_month group by channel_name, is_online
           order by `GMV` desc""",
    ),
    (
        "行为漏斗",
        "注意：购买率高于加购率，行为日志非真实漏斗",
        """select stat_month `月份`, browse_pv `浏览`, cart_pv `加购`, fav_pv `收藏`,
                  buy_pv `购买`, browse_pv_avg `日均浏览`, buy_pv_avg `日均购买`,
                  cart_rate `加购率`, fav_rate `收藏率`, buy_rate `购买率`
           from ydsh_ads.ads_behavior_funnel order by stat_month""",
    ),
    (
        "用户RFM",
        "R/F/M 各 ntile(5) 分档；R 越小越近期",
        """select rfm_segment `客户分层`, count(1) `人数`,
                  avg(recency_days) `平均未购天数`, avg(frequency) `平均订单数`,
                  avg(monetary) `人均消费`
           from ydsh_ads.ads_user_rfm group by rfm_segment order by `人数` desc""",
    ),
    (
        "周度极值",
        "W53 只有 12-30、12-31 两天，不能当作业绩最差周",
        """select week_key `周`, week_start `周一`, week_end `周日`,
                  sum(gmv) `GMV`, sum(order_cnt) `订单量`
           from ydsh_dws.dws_sales_week group by week_key, week_start, week_end
           order by `GMV` desc limit 3""",
    ),
    (
        "周度最低",
        "同上，W53 为不足 7 天的残周",
        """select week_key `周`, week_start `周一`, week_end `周日`,
                  sum(gmv) `GMV`, sum(order_cnt) `订单量`
           from ydsh_dws.dws_sales_week group by week_key, week_start, week_end
           order by `GMV` asc limit 3""",
    ),
]


def write_sheet(wb: Workbook, name: str, note: str, sql: str) -> None:
    df = query_df(sql)
    ws = wb.create_sheet(name[:31])

    # 标题行 + 说明行
    ws.append([f"{name}　—　{note}"])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
    c = ws.cell(row=1, column=1)
    c.font = Font(name="微软雅黑", size=11, bold=True, color="1F3864")
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22

    # 表头
    ws.append(list(df.columns))
    for col in range(1, len(df.columns) + 1):
        cell = ws.cell(row=2, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[2].height = 20

    # 数据
    for row in df.itertuples(index=False):
        ws.append([
            float(v) if isinstance(v, (int, float)) or type(v).__name__ == "Decimal" else v
            for v in row
        ])

    # 数值格式：列名里含"率/占比"用百分比，其余数值用千分位
    for idx, colname in enumerate(df.columns, start=1):
        letter = get_column_letter(idx)
        for r in range(3, ws.max_row + 1):
            cell = ws.cell(row=r, column=idx)
            cell.font = BODY_FONT
            cell.border = BORDER
            if isinstance(cell.value, (int, float)):
                if any(k in colname for k in ("率", "占比")):
                    cell.number_format = "0.00%"
                elif isinstance(cell.value, int):
                    cell.number_format = "#,##0"
                else:
                    cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")
        width = max(len(str(colname)) * 2 + 4, 12)
        ws.column_dimensions[letter].width = min(width, 30)

    ws.freeze_panes = "A3"
    print(f"  {name}: {len(df)} 行 × {len(df.columns)} 列")


def main() -> None:
    print("从 Hive 取数并写入 Excel ...")
    wb = Workbook()
    wb.remove(wb.active)  # 删掉默认空白 sheet
    for name, note, sql in SHEETS:
        write_sheet(wb, name, note, sql)

    # 首页：说明
    cover = wb.create_sheet("说明", 0)
    cover.column_dimensions["A"].width = 22
    cover.column_dimensions["B"].width = 88
    rows = [
        ("云购生活 · KPI 指标结果表", ""),
        ("数据范围", "2024-01-01 ~ 2024-12-31（366 天）"),
        ("数据来源", "ydsh_ads 9 张应用表 + ydsh_dws 汇总表"),
        ("生成方式", "第3周/py/export_kpi_xlsx.py 实时查询 Hive 生成，非手工录入"),
        ("对应 SQL", "第3周/sql/ads/kpi_report.sql"),
        ("", ""),
        ("口径提醒 1", "品类/商品级金额用 alloc_amount（明细口径），合计 35,833,305.06"),
        ("口径提醒 2", "订单级 GMV 用 pay_amount，合计 36,116,687.06，差额来自 114 张无明细订单"),
        ("口径提醒 3", "复购率恒为 100%，本数据集无区分度，请用月度复购率（45.82%~50.85%）"),
        ("口径提醒 4", "GMV 同比全为空，因只有 2024 一年数据"),
        ("口径提醒 5", "行为漏斗购买率高于加购率，日志为并列事件而非会话步骤"),
        ("口径提醒 6", "2024-W53 只有 2 天，不可当作业绩最差周"),
        ("", ""),
        ("生成日期", "2026-11-10"),
    ]
    for i, (k, v) in enumerate(rows, start=1):
        cover.cell(row=i, column=1, value=k)
        cover.cell(row=i, column=2, value=v)
        a = cover.cell(row=i, column=1)
        b = cover.cell(row=i, column=2)
        a.font = Font(name="微软雅黑", size=10, bold=True)
        b.font = BODY_FONT
        b.alignment = Alignment(wrap_text=True, vertical="center")
        if i == 1:
            a.font = Font(name="微软雅黑", size=14, bold=True, color="1F3864")
            cover.row_dimensions[1].height = 28

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"\n已保存 -> {OUT}")


if __name__ == "__main__":
    main()