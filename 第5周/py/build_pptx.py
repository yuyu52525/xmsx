"""第 5 周 · 答辩 PPT 生成脚本（约 6 分钟 / 12 页）

为什么用脚本生成而不是手工排版：
  答辩材料会反复改（数字要跟着 evidence 变），手工排版每次都容易漏改、
  字号与对齐也难保持一致。这里把版式固化成函数，改数据重跑即可。

设计约束（避免"AI 味"的堆字）：
  - 一页只讲一件事，标题写结论而不是写主题
  - 数字用大字号卡片，正文不超过 4 行
  - 全篇统一：16:9 / 微软雅黑 / 深蓝主色 / 每页页码与栏目名
  - 每页写演讲备注，带时间预算，合计约 6 分钟

用法：python build_pptx.py
输出：../docs/答辩PPT_第5周.pptx
"""

from __future__ import annotations

import math
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_MARKER_STYLE, XL_TICK_MARK
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt
from pptx.oxml.ns import qn
from lxml import etree

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"
IMG = DOCS / "images"
OUT = DOCS / "答辩PPT_第5周.pptx"

# ------------------------------------------------------------------ 设计常量
W, H = 13.333, 7.5                    # 16:9
M = 0.72                              # 左右页边距
CW = W - 2 * M                        # 内容宽度

NAVY = RGBColor(0x0F, 0x2B, 0x46)
INK = RGBColor(0x22, 0x2B, 0x33)
BLUE = RGBColor(0x1F, 0x6F, 0xB2)
SKY = RGBColor(0x4A, 0x9E, 0xDB)
ORANGE = RGBColor(0xD9, 0x6B, 0x2B)
GRAY = RGBColor(0x6B, 0x77, 0x85)
LINE = RGBColor(0xD8, 0xDF, 0xE6)
SOFT = RGBColor(0xF3, 0xF7, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

CN = "微软雅黑"


# ------------------------------------------------------------------ 基础工具
def _set_ea(run, name: str) -> None:
    """中文必须同时设 latin 与 ea，否则 PowerPoint 回退到宋体。"""
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", name)


def style(run, size: float, bold: bool = False, color: RGBColor = INK,
          name: str = CN) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = name
    _set_ea(run, name)


def text(slide, x, y, w, h, content: str, size: float = 15, bold: bool = False,
         color: RGBColor = INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         line: float = 1.3, space_after: float = 0):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, ln in enumerate(content.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line
        p.space_after = Pt(space_after)
        r = p.add_run()
        r.text = ln
        style(r, size, bold, color)
    return box


def rect(slide, x, y, w, h, fill: RGBColor | None = None,
         line_color: RGBColor | None = None, shape=MSO_SHAPE.RECTANGLE,
         radius: float | None = None, alpha: int | None = None):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.shadow.inherit = False
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
        if alpha is not None:                      # 半透明（装饰用）
            solid = sp.fill.fore_color._xFill
            clr = solid.find(qn("a:srgbClr"))
            a = etree.SubElement(clr, qn("a:alpha"))
            a.set("val", str(int(alpha * 1000)))
    if line_color is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line_color
        sp.line.width = Pt(0.9)
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sp.adjustments[0] = radius
    return sp


def fit_lines(txt: str, width_in: float, size: float) -> int:
    """粗估中文行数：一个汉字约占 1 个字号宽。"""
    per_line = max(6, int((width_in * 72 - 8) / size))
    return max(1, math.ceil(len(txt) / per_line))


def bullets(slide, x, y, w, items: list[dict], size: float = 14.5,
            gap: float = 0.16, accent: RGBColor = BLUE) -> float:
    """带小方块的项目符号块；返回占用高度。items: {lead, body}"""
    cy = y
    for it in items:
        lead = it.get("lead", "")
        body = it.get("body", "")
        full = (lead + body) if lead else body
        lines = fit_lines(full, w - 0.34, size)
        line_h = size * 1.34 / 72
        block_h = lines * line_h
        rect(slide, x, cy + size * 0.22 / 72, 0.09, 0.09, fill=accent)
        box = slide.shapes.add_textbox(Inches(x + 0.3), Inches(cy), Inches(w - 0.3),
                                       Inches(block_h + 0.1))
        tf = box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.line_spacing = 1.34
        if lead:
            r = p.add_run()
            r.text = lead
            style(r, size, True, NAVY)
        r2 = p.add_run()
        r2.text = body
        style(r2, size, False, INK)
        cy += block_h + gap
    return cy - y


def kpi(slide, x, y, w, value: str, label: str, unit: str = "",
        accent: RGBColor = BLUE, v_size: float = 30) -> None:
    text(slide, x, y, w, 0.46, value, v_size, True, accent, line=1.0)
    if unit:
        # 单位紧贴数字右侧
        text(slide, x + w - 0.62, y + 0.2, 0.62, 0.24, unit, 10, False, GRAY)
    text(slide, x, y + 0.5, w, 0.26, label, 10.5, False, GRAY)


def header(slide, kicker: str, title: str, page: int, total: int = 12) -> None:
    rect(slide, M, 0.52, 0.055, 0.2, fill=BLUE)
    text(slide, M + 0.16, 0.49, 6.0, 0.24, kicker, 10.5, True, BLUE)
    text(slide, M, 0.8, CW - 1.0, 0.62, title, 25, True, NAVY, line=1.15)
    text(slide, W - M - 1.0, 0.52, 1.0, 0.24, f"{page:02d} / {total:02d}", 10, False, GRAY,
         align=PP_ALIGN.RIGHT)


def footer(slide, page: int) -> None:
    rect(slide, M, 7.02, CW, 0.008, fill=LINE)
    text(slide, M, 7.1, 6.4, 0.22, "云购生活数仓 · 第 5 周综合答辩", 9, False, GRAY)
    text(slide, W - M - 2.2, 7.1, 2.2, 0.22, "余天乐 · 20230308098", 9, False, GRAY,
         align=PP_ALIGN.RIGHT)


def note(slide, content: str) -> None:
    slide.notes_slide.notes_text_frame.text = content


def table(slide, x, y, w, rows: list[list[str]], col_ratio: list[float],
          size: float = 11.5, header_fill: RGBColor = NAVY,
          row_h: float = 0.34, head_h: float = 0.36,
          align_right: list[int] | None = None) -> None:
    n_r, n_c = len(rows), len(rows[0])
    shape = slide.shapes.add_table(n_r, n_c, Inches(x), Inches(y), Inches(w),
                                   Inches(head_h + row_h * (n_r - 1)))
    tbl = shape.table
    # 去掉默认样式（边框 + 斑马纹），只保留我们自己设的底色
    tblPr = tbl._tbl.tblPr
    for child in list(tblPr):
        if child.tag == qn("a:tableStyleId"):
            tblPr.remove(child)
    sid = etree.SubElement(tblPr, qn("a:tableStyleId"))
    sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"     # No Style, No Grid
    tbl.first_row = False
    tbl.horz_banding = False

    for i, ratio in enumerate(col_ratio):
        tbl.columns[i].width = Emu(int(Inches(w) * ratio))
    tbl.rows[0].height = Inches(head_h)
    for r in range(1, n_r):
        tbl.rows[r].height = Inches(row_h)

    for r in range(n_r):
        for c in range(n_c):
            cell = tbl.cell(r, c)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = header_fill
            else:
                cell.fill.fore_color.rgb = WHITE if r % 2 else SOFT
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.line_spacing = 1.05
            p.alignment = (PP_ALIGN.RIGHT if (align_right and c in align_right) else PP_ALIGN.LEFT)
            run = p.add_run()
            run.text = rows[r][c]
            style(run, size, r == 0,
                  WHITE if r == 0 else INK)


def page_base(prs, kicker, title, page, total=12):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    header(s, kicker, title, page, total)
    footer(s, page)
    return s


# ------------------------------------------------------------------ 数据（全部来自第 5 周证据）
MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月",
          "7月", "8月", "9月", "10月", "11月", "12月"]
GMV_WAN = [315.87, 291.51, 308.77, 302.58, 308.05, 283.00,
           297.92, 303.99, 292.95, 296.32, 299.52, 311.17]
CATS = [("运动户外", 14.91), ("数码家电", 13.73), ("服饰鞋包", 12.56), ("图书文娱", 12.46),
        ("食品生鲜", 12.25), ("家居生活", 11.58), ("美妆个护", 11.39), ("母婴玩具", 11.12)]


# ------------------------------------------------------------------ 各页
def s01_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, W, H, fill=NAVY)
    # 右侧装饰圆（低透明度，不抢文字）
    rect(s, 9.5, -1.6, 6.2, 6.2, fill=BLUE, shape=MSO_SHAPE.OVAL, alpha=22)
    rect(s, 11.1, 4.3, 3.4, 3.4, fill=SKY, shape=MSO_SHAPE.OVAL, alpha=14)

    text(s, M, 1.55, 8.6, 0.3, "企业项目实战实训 · 第 5 周综合答辩", 13, True, SKY)
    text(s, M, 2.0, 9.4, 1.5, "云购生活", 54, True, WHITE, line=1.05)
    text(s, M, 2.95, 9.4, 0.9, "企业级数据仓库与经营分析可视化系统", 27, True, WHITE, line=1.2)
    rect(s, M, 4.12, 1.5, 0.045, fill=ORANGE)
    text(s, M, 4.34, 9.0, 0.66,
         "6 张 CSV → 四层数仓 → 指标体系 → AI 问答 → 三端可视化 → 一条命令部署", 14, False,
         RGBColor(0xBF, 0xCF, 0xDD), line=1.4)

    # 四个规模数字
    items = [("51", "张数仓表"), ("11.5", "万行源数据"), ("9", "个容器服务"), ("3", "个可视化终端")]
    x = M
    for i, (v, l) in enumerate(items):
        text(s, x, 5.62, 1.9, 0.42, v, 26, True, SKY, line=1.0)
        text(s, x, 6.05, 1.9, 0.24, l, 10.5, False, RGBColor(0x9F, 0xB3, 0xC6))
        if i < 3:
            rect(s, x + 1.62, 5.66, 0.008, 0.52, fill=RGBColor(0x2E, 0x4A, 0x66))
        x += 2.16

    text(s, M, 6.72, 8.0, 0.26, "团队 乐天　·　余天乐　20230308098　·　数据科学与大数据技术",
         11, False, RGBColor(0x9F, 0xB3, 0xC6))
    note(s, "【0:00–0:15】各位老师好。我是余天乐，项目是云购生活企业级数据仓库与经营分析可视化系统。"
            "用一句话概括：把一家新零售企业 6 张业务表的 11.5 万行原始数据，做成一套 51 张表、"
            "可以逐层回算的数仓，再用三端界面和 AI 问答把指标交付给业务方。今天六分钟，讲四件事："
            "为什么做、怎么做的、做出了什么、哪里还不够。")


def s02_problem(prs):
    s = page_base(prs, "01 业务问题", "数据“能看，不能算”", 2)
    text(s, M, 1.62, 5.5, 0.9,
         "6 张 CSV 拆开看都正常，\n只要一聚合就出错。", 17, True, NAVY, line=1.45)
    bullets(s, M, 2.62, 5.55, [
        {"lead": "负金额混进 GMV：", "body": "最小 −4,994.73 元，最大 995.78 万元，"
                                          "照算会让客单价失真"},
        {"lead": "同一个值有三种写法：", "body": "pv / PV / 浏览 被 GROUP BY 成三组，"
                                              "漏斗与趋势全错"},
        {"lead": "明细和订单对不上：", "body": "明细原价合计是订单实付的 11.2 倍，"
                                             "品类占比怎么算都不等于 100%"},
    ], size=13.5, gap=0.2)

    rect(s, 6.62, 1.62, 5.99, 4.86, fill=SOFT)
    text(s, 6.95, 1.82, 5.3, 0.26, "业务方原话背后的五个痛点", 10.5, True, BLUE)
    pains = [("P1", "口径不统一", "同一笔 GMV，三个部门报出三个数"),
             ("P2", "脏数据不可信", "重复订单算两次，负金额拉低客单价"),
             ("P3", "取数要排队", "报表出来，促销窗口已经过了"),
             ("P4", "自助取数门槛高", "临时取数几乎都压在数据岗"),
             ("P5", "换机器跑不起来", "环境靠“我这台能跑”")]
    y = 2.22
    for code, name, desc in pains:
        text(s, 7.0, y, 0.5, 0.26, code, 11, True, ORANGE)
        text(s, 7.45, y - 0.02, 2.1, 0.28, name, 12.5, True, NAVY)
        text(s, 9.55, y - 0.01, 2.95, 0.26, desc, 10.5, False, GRAY)
        y += 0.62
    note(s, "【0:15–0:55】先说为什么做。这家企业有 60 家门店和三个线上渠道，"
            "每天要回答四个问题：卖了多少、变化在哪、钱在哪、谁值得留。"
            "但这些答案散在 6 张 CSV 里，而且这份数据是“能看不能算”："
            "负金额和百万级脏金额混在里面，pv 和“浏览”会被 group by 成两组，"
            "订单明细加起来是订单实付的 11 倍。所以第一个结论是——"
            "不做统一的数据层，任何图表都只是把错误画得更好看。"
            "右边五个痛点，本质是同一件事：没有单一事实来源。")


def s03_arch(prs):
    s = page_base(prs, "02 总体架构", "一条链路，五个平面，每层只读上一层", 3)
    layers = [
        ("数据源", "6 个 CSV\n11.48 万行", SKY),
        ("ODS 贴源", "6 张表\n原样落地，脏数据保留", BLUE),
        ("DWD 明细", "25 张表\n清洗 + 星型模型", BLUE),
        ("DWS 汇总", "9 张表\n日 / 周 / 月 + 维度", NAVY),
        ("ADS 应用", "11 张表\n一张表服务一张图", NAVY),
    ]
    x, y, bw, bh, gap = M, 1.78, 2.24, 1.36, 0.22
    for i, (name, desc, col) in enumerate(layers):
        rect(s, x, y, bw, bh, fill=col)
        text(s, x + 0.16, y + 0.14, bw - 0.3, 0.28, name, 13, True, WHITE)
        text(s, x + 0.16, y + 0.52, bw - 0.3, 0.72, desc, 10, False,
             RGBColor(0xDD, 0xE8, 0xF2), line=1.35)
        if i < 4:
            ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + bw + 0.03),
                                    Inches(y + bh / 2 - 0.075), Inches(0.16), Inches(0.15))
            ar.shadow.inherit = False
            ar.fill.solid()
            ar.fill.fore_color.rgb = RGBColor(0xB6, 0xC5, 0xD3)
            ar.line.fill.background()
        x += bw + gap

    # 服务层 + 应用层
    rect(s, M, 3.36, 6.28, 1.3, fill=SOFT, line_color=LINE)
    text(s, M + 0.18, 3.46, 5.9, 0.26, "服务层　结果集副本，不做 ETL", 10.5, True, BLUE)
    text(s, M + 0.18, 3.76, 5.9, 0.78,
         "ClickHouse 11 表（2,666 行，30–50 ms）　·　MySQL 3 表（Superset 跨源演示）",
         11.5, False, INK, line=1.4)

    rect(s, 7.2, 3.36, 5.42, 1.3, fill=SOFT, line_color=LINE)
    text(s, 7.38, 3.46, 5.0, 0.26, "应用层　三种角色，三个入口", 10.5, True, BLUE)
    text(s, 7.38, 3.76, 5.1, 0.78,
         "Superset 仪表板（管理）　·　ECharts 大屏（展厅）　·　Streamlit 问答（自助）",
         11.5, False, INK, line=1.4)

    # 三个设计取舍
    text(s, M, 4.94, 3.0, 0.24, "三个关键取舍", 10.5, True, GRAY)
    takes = [("分层解耦", "跨层取数一律禁止：任何指标都能沿链路回溯"),
             ("口径固化", "GMV 只在 DWD 定义一次，ADS 不再二次计算"),
             ("按需物化", "小数据量下用副本换响应，口径仍以 Hive 为准")]
    x = M
    for i, (t, d) in enumerate(takes):
        text(s, x, 5.26, 3.86, 0.28, t, 12.5, True, NAVY)
        text(s, x, 5.58, 3.72, 0.7, d, 10.5, False, GRAY, line=1.4)
        if i < 2:
            rect(s, x + 3.9, 5.3, 0.008, 0.86, fill=LINE)
        x += 4.06

    rect(s, M, 6.4, CW, 0.012, fill=LINE)
    text(s, M, 6.5, CW, 0.26,
         "ORC + SNAPPY · 按月分区（12 个）· user_id 分 8 桶 · 每字段带中文注释，describe 即可查口径",
         10.5, False, GRAY)
    note(s, "【0:55–1:35】架构是五个平面。数据从 6 个 CSV 进 ODS，原样落地不做加工；"
            "DWD 做清洗和星型建模；DWS 做日周月汇总；ADS 一张表服务一张图；"
            "再上面是服务层和应用层。服务层要特别说明一句：ClickHouse 不是第二套数仓，"
            "它只是把 2,666 行结果集复制一份，把 1 到 15 秒压到 30 到 50 毫秒，"
            "口径改了重跑导出就行。三个取舍里最重要的是分层解耦和口径固化——"
            "GMV 只在 DWD 定义一次，后面所有表都由它派生，所以图上显示的数"
            "和文档里写的数必然是同一个数。")


def s04_clean(prs):
    s = page_base(prs, "03 数据治理", "72,156 条问题，可修复项修复率 100%", 4)
    rows = [["脏数据类型", "问题数", "典型表现", "修复率"],
            ["完整性（缺失）", "255", "年龄 51、邮箱 193、上架日期 11", "100%*"],
            ["唯一性（重复）", "600", "整行重复 400 + 同号异构 200", "100%"],
            ["一致性（格式）", "8,217", "日期斜杠/8 位、手机号带横线", "100%"],
            ["准确性（异常值）", "2,564", "负金额、百万级金额、数量 99", "100%"],
            ["有效性（枚举）", "60,520", "pv / PV / 浏览 等 7 个字段", "100%"]]
    table(s, M, 1.72, 7.15, rows, [0.30, 0.16, 0.40, 0.14], size=11, row_h=0.42, head_h=0.36,
          align_right=[1, 3])
    text(s, M, 4.2, 7.1, 0.24, "* 邮箱 193 条属“业务上允许为空”，标记不填充，单独说明。",
         9.5, False, GRAY)

    # 右：行数漏斗
    rect(s, 8.3, 1.72, 4.31, 2.05, fill=SOFT)
    text(s, 8.5, 1.84, 3.9, 0.24, "行数：清洗前后", 10, True, BLUE)
    text(s, 8.5, 2.14, 2.0, 0.32, "114,809", 22, True, NAVY, line=1.0)
    text(s, 10.55, 2.24, 1.0, 0.22, "→", 14, True, GRAY)
    text(s, 10.9, 2.14, 1.6, 0.32, "111,037", 22, True, BLUE, line=1.0)
    rect(s, 8.5, 2.66, 3.4, 0.1, fill=RGBColor(0xC9, 0xD6, 0xE2))
    rect(s, 8.5, 2.66, 3.4 * 0.9671, 0.1, fill=BLUE)
    text(s, 8.5, 2.84, 3.9, 0.24, "保留 96.71%　剔除 3,772 行（3.29%）", 10, False, GRAY)

    # 右：三种策略
    text(s, 8.3, 3.96, 4.3, 0.24, "三种修复策略（不搞一刀切）", 10, True, BLUE)
    strat = [("删除", "3,772", "重复 600 + 金额 602 + 数量 1,081 + 关联明细 1,489"),
             ("修正", "861", "单价 773 + 商品价 36 + 年龄 27 + 等级 14 + 日期 11"),
             ("标记", "193", "邮箱缺失，保留原值只打标记")]
    y = 4.28
    for name, n, desc in strat:
        text(s, 8.3, y, 0.95, 0.26, name, 11, True, ORANGE)
        text(s, 9.2, y, 0.85, 0.26, n, 11, True, NAVY)
        text(s, 10.05, y, 2.6, 0.5, desc, 9.2, False, GRAY, line=1.3)
        y += 0.62

    rect(s, M, 4.72, 7.15, 1.42, fill=SOFT)
    text(s, M + 0.2, 4.82, 6.7, 0.24, "一个必须讲清楚的判断：阈值为什么不用 P99", 10, True,
         ORANGE)
    text(s, M + 0.2, 5.1, 6.75, 0.94,
         "实测 P99 = 551 万元 —— 因为异常值占 3.8%，已超过 1%，第 99 百分位本身就落在脏数据堆里。"
         "改用 IQR：上限 11,356.33 元，正好落在 5 千到 10 万之间的金额断崖上。", 10.2, False,
         INK, line=1.45)
    note(s, "【1:35–2:15】治理这块我讲三个数。第一，五类脏数据一共 72,156 条问题，"
            "可修复项全部 100%。第二，行数从 114,809 降到 111,037，剔除 3,772 行，3.29%，"
            "每一行都能指到规则。第三，我们不搞一刀切：删除 3,772 行、修正 861 条、标记 193 行，"
            "三种策略在表里都有标记位。这里有个我认为最值得讲的判断："
            "金额阈值没用教科书上的 P99，因为实测 P99 是 551 万——异常值占了 3.8%，"
            "已经把百分位抬到脏数据堆里去了；改用 IQR 得到 11,356 元，"
            "正好落在 5 千到 10 万的金额断崖上。阈值要用数据自己的分布验证一遍。")


def s05_metric(prs):
    s = page_base(prs, "04 指标体系", "指标不是算出来的，是定义出来的", 5)
    # 左：三层结构
    text(s, M, 1.68, 5.4, 0.24, "三层结构：改一处口径，下游自动跟着变", 10.5, True, BLUE)
    tiers = [("复合指标", "客单价 2,508.45 ｜ 坪效 ｜ ARPU 36,116.69", NAVY, 5.3),
             ("派生指标", "月度 GMV ｜ 品类销售额 ｜ 省份 GMV", BLUE, 4.7),
             ("原子指标", "pay_amount ｜ quantity ｜ alloc_amount", SKY, 4.1)]
    y = 2.0
    for name, desc, col, w in tiers:
        rect(s, M, y, w, 0.82, fill=col)
        text(s, M + 0.18, y + 0.1, 1.4, 0.26, name, 11.5, True, WHITE)
        text(s, M + 0.18, y + 0.42, w - 0.36, 0.3, desc, 10.5, False,
             RGBColor(0xE6, 0xEF, 0xF7))
        y += 0.96

    text(s, M, 4.98, 5.4, 0.24, "一致性靠加总校验，而不是靠“看着对”", 10.5, True, BLUE)
    bullets(s, M, 5.28, 5.4, [
        {"lead": "", "body": "DWS 日 / 周 / 月 三个粒度的 GMV 加总全部 = 36,116,687.06"},
        {"lead": "", "body": "6 张订单口径 ADS 表加总全部相等；2 张分摊口径亦相等"},
        {"lead": "", "body": "差异 283,382.65 元 = 114 张无明细订单，可逐笔解释"},
    ], size=11, gap=0.1, accent=SKY)

    # 右：金额三口径
    rect(s, 6.42, 1.68, 6.19, 2.5, fill=SOFT)
    text(s, 6.62, 1.78, 5.8, 0.24, "金额三口径：混用是这类项目最常见的错", 10.5, True, ORANGE)
    rows = [["口径", "字段", "合计（元）", "用途"],
            ["订单", "pay_amount", "36,116,687.06", "GMV / 客单价"],
            ["分摊", "alloc_amount", "35,833,305.06", "品类 / 时段"],
            ["原价", "item_amount", "402,816,786.63", "只能当权重"]]
    table(s, 6.62, 2.08, 5.79, rows, [0.13, 0.24, 0.36, 0.27], size=9.8, row_h=0.4, head_h=0.32,
          align_right=[2])
    text(s, 6.62, 3.66, 5.8, 0.44,
         "订单口径 − 分摊口径 = 283,382.65 元 = 114 张无明细订单的实付；两者相加没有意义。",
         9.6, False, GRAY, line=1.35)

    # 右下：结论卡
    rect(s, 6.42, 4.4, 2.95, 1.66, fill=WHITE, line_color=LINE)
    text(s, 6.6, 4.52, 2.6, 0.24, "全年 GMV", 10, False, GRAY)
    text(s, 6.6, 4.76, 2.6, 0.4, "3,611.67", 24, True, NAVY, line=1.0)
    text(s, 6.6, 5.2, 2.6, 0.24, "万元（订单口径）", 9.5, False, GRAY)
    text(s, 6.6, 5.52, 2.6, 0.44, "有效 GMV 2,418.53 万，占 66.96%", 9.2, False, GRAY,
         line=1.3)

    rect(s, 9.58, 4.4, 3.03, 1.66, fill=WHITE, line_color=LINE)
    text(s, 9.76, 4.52, 2.7, 0.24, "规模", 10, False, GRAY)
    for i, (v, l) in enumerate([("14,398", "订单"), ("1,000", "下单用户"), ("2,508.45", "客单价")]):
        text(s, 9.76, 4.74 + i * 0.36, 1.3, 0.24, v, 11.5, True, NAVY)
        text(s, 11.1, 4.76 + i * 0.36, 1.2, 0.22, l, 9.5, False, GRAY)
    note(s, "【2:15–2:50】指标这块，我最想说的一句话是：指标不是算出来的，是定义出来的。"
            "左边三层：原子、派生、复合，好处是改一处口径，下游九张 DWS、十一张 ADS 自动跟着变。"
            "右边这张表是这类项目最容易翻车的地方——金额有三个口径：订单口径 3,611 万、"
            "分摊口径 3,583 万、明细原价 4 亿。原价只能当分摊权重，谁把它当销售额算，"
            "品类占比立刻错到离谱。两个口径差 28.3 万，正好是 114 张没有明细的订单，"
            "可以逐笔对上。所以我们的原则是：能解释的差异才允许存在。")


def s06_result(prs):
    s = page_base(prs, "05 业务结论", "一年 3,611 万，结构比总量更值得看", 6)
    # 折线
    cd = CategoryChartData()
    cd.categories = MONTHS
    cd.add_series("GMV（万元）", GMV_WAN)
    gf = s.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(M - 0.06), Inches(1.66),
                            Inches(7.25), Inches(3.5), cd)
    ch = gf.chart
    ch.has_title = False
    ch.has_legend = False
    ch.font.size = Pt(9.5)
    ch.font.name = CN
    ch.font.color.rgb = GRAY
    plot = ch.plots[0]
    plot.has_data_labels = False
    ser = plot.series[0]
    ser.format.line.color.rgb = BLUE
    ser.format.line.width = Pt(2.25)
    ser.smooth = False
    ser.marker_size = 5
    ser.marker_style = XL_MARKER_STYLE.CIRCLE
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xE8, 0xEE, 0xF4)
    va.major_gridlines.format.line.width = Pt(0.6)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(9)
    va.tick_labels.font.color.rgb = GRAY
    va.maximum_scale = 340
    va.minimum_scale = 260
    ca = ch.category_axis
    ca.tick_labels.font.size = Pt(9)
    ca.tick_labels.font.color.rgb = GRAY
    ca.format.line.color.rgb = LINE
    ca.major_tick_mark = XL_TICK_MARK.NONE

    text(s, M - 0.06, 5.24, 7.2, 0.24, "月度 GMV（万元）　全年波动仅 ±6%，无明显趋势项", 10,
         True, BLUE)
    bullets(s, M, 5.56, 7.2, [
        {"lead": "结论 1：", "body": "序列接近平稳（CV = 0.187），这直接决定了预测模型很难赢“均值”"},
        {"lead": "结论 2：", "body": "9 月为全年最低（292.95 万），但仅比月均低 2.7%，不足以支撑“季节性下滑”"},
    ], size=10.8, gap=0.12, accent=SKY)

    # 品类条形
    text(s, 8.32, 1.66, 4.3, 0.24, "品类销售额占比（分摊口径，合计 100%）", 10, True, BLUE)
    cats = sorted(CATS, key=lambda z: z[1])
    cd2 = CategoryChartData()
    cd2.categories = [c[0] for c in cats]
    cd2.add_series("占比", [c[1] for c in cats])
    gf2 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(8.26), Inches(1.92),
                             Inches(4.36), Inches(3.1), cd2)
    c2 = gf2.chart
    c2.has_title = False
    c2.has_legend = False
    c2.font.size = Pt(9)
    c2.font.name = CN
    c2.font.color.rgb = INK
    p2 = c2.plots[0]
    p2.has_data_labels = True
    p2.data_labels.font.size = Pt(9)
    p2.data_labels.font.color.rgb = GRAY
    p2.data_labels.number_format = '0.00"%"'
    p2.data_labels.number_format_is_linked = False
    p2.gap_width = 45
    p2.series[0].format.fill.solid()
    p2.series[0].format.fill.fore_color.rgb = RGBColor(0x7F, 0xB3, 0xD9)
    v2 = c2.value_axis
    v2.visible = False
    v2.has_major_gridlines = False
    v2.maximum_scale = 17
    c2.category_axis.tick_labels.font.size = Pt(9)
    c2.category_axis.format.line.fill.background()
    c2.category_axis.major_tick_mark = XL_TICK_MARK.NONE

    rect(s, 8.32, 5.18, 4.29, 1.62, fill=SOFT)
    text(s, 8.5, 5.28, 3.9, 0.24, "另外三个结构", 10, True, BLUE)
    facts = [("渠道", "APP 25.46% ｜ PC 24.99% ｜ 门店 24.93% ｜ 小程序 24.63%"),
             ("支付", "微信 26.77% ｜ 支付宝 26.22% ｜ 银行卡 23.59% ｜ 货到 23.42%"),
             ("区域", "陕西 7.89% 第一，15 省最大差距不足 3 个百分点")]
    y = 5.56
    for k, v in facts:
        text(s, 8.5, y, 0.5, 0.22, k, 9.2, True, NAVY)
        text(s, 9.0, y, 3.5, 0.24, v, 8.6, False, GRAY)
        y += 0.36
    note(s, "【2:50–3:30】结论页我只讲两件事。左边月度曲线：全年在 283 到 316 万之间波动，"
            "波动幅度只有正负 6%，没有明显趋势。这个观察很关键，后面讲预测时会用到。"
            "右边品类：八个类目非常接近，第一名运动户外 14.91%，最后一名母婴玩具 11.12%，"
            "说明这是一个“没有爆品”的结构，运营上更该看渠道与人群，而不是押单品类。"
            "渠道、支付、区域也都非常平均，所以我给的判断是：结构比总量更值得看。"
            "另外提醒一句，品类用的是分摊口径，不能用原价口径。")


def s07_ai(prs):
    s = page_base(prs, "06 AI 能力", "两个 AI 能力，和一个诚实的结论", 7)
    text(s, M, 1.66, 6.0, 0.24, "① GMV 预测：赢朴素基线，但输给“均值”", 10.5, True, BLUE)
    rows = [["模型", "MAE（元）", "MAPE", "结论"],
            ["线性回归", "13,489.58", "12.72%", "比朴素基线好 36.7%"],
            ["朴素基线（昨日=今日）", "19,702.24", "20.08%", "基准对照"],
            ["常数基线（历史均值）", "12,399.38", "12.11%", "反而最优"]]
    table(s, M, 1.96, 6.2, rows, [0.40, 0.22, 0.16, 0.30], size=9.8, row_h=0.4, head_h=0.32,
          align_right=[1, 2])

    rect(s, M, 3.5, 6.2, 1.5, fill=RGBColor(0xFD, 0xF2, 0xE9))
    text(s, M + 0.18, 3.6, 5.85, 0.24, "所以我们的结论是：不上线", 10.5, True, ORANGE)
    text(s, M + 0.18, 3.88, 5.85, 0.98,
         "6 折滚动回测里两者 MAE 相差不到 0.7%，模型没有提供实质增益；"
         "且存在系统性低估（MBE +5,655.56 元）。这条写进了报告，而不是藏起来。",
         10, False, INK, line=1.4)

    text(s, M, 5.18, 6.2, 0.24, "② NL2SQL 问答：一句话 → 一条只读 SQL", 10.5, True, BLUE)
    steps = [("提问", "中文业务问题"), ("生成", "GLM-4-Flash 出 SQL"),
             ("校验", "guard_sql 四规则"), ("执行", "Hive 只读 + LIMIT")]
    x = M
    for i, (k, v) in enumerate(steps):
        rect(s, x, 5.5, 1.36, 0.94, fill=SOFT, line_color=LINE)
        text(s, x + 0.12, 5.6, 1.12, 0.24, k, 10, True, NAVY)
        text(s, x + 0.12, 5.86, 1.14, 0.5, v, 8.6, False, GRAY, line=1.3)
        if i < 3:
            text(s, x + 1.38, 5.82, 0.2, 0.24, "›", 14, True, SKY)
        x += 1.58

    # 右侧：四个数字
    rect(s, 7.2, 1.66, 5.41, 4.78, fill=NAVY)
    text(s, 7.46, 1.8, 4.9, 0.26, "AI 部分的四个可核实数字", 10.5, True, SKY)
    nums = [("3,551", "tokens / 次提问（输入 3,457 + 输出 94）"),
            ("11,969", "行为日志里的购买事件数，用于体量对比"),
            ("4 条", "guard_sql 拦截规则：只读、禁写、带库名、加 LIMIT"),
            ("10 条", "AI 协同记录，其中 5 条是“AI 给错、人工纠正”")]
    y = 2.22
    for v, l in nums:
        text(s, 7.46, y, 4.6, 0.34, v, 20, True, WHITE, line=1.0)
        text(s, 7.46, y + 0.36, 4.75, 0.4, l, 9.5, False, RGBColor(0xB9, 0xC9, 0xD9),
             line=1.3)
        y += 0.94
    text(s, 7.46, 5.98, 4.8, 0.34, "模型不绑定：改 .env 三个变量即可切供应商", 9.2, False,
         RGBColor(0x8F, 0xA6, 0xBA))
    note(s, "【3:30–4:10】AI 部分我讲实话。预测用了线性回归，测试集 MAPE 12.72%，"
            "比“昨天等于今天”的朴素基线好 36.7%，看起来不错；但我们又跑了常数基线，"
            "也就是一律预测历史均值，MAPE 是 12.11%，比模型还低。6 折滚动回测也确认"
            "两者相差不到 0.7%。原因在上一页那张图：序列本身接近平稳，CV 只有 0.187，"
            "这种数据上复杂模型很难有信息增量。所以结论是：不上线，把均值作为基线。"
            "右边四个数字：一次问答约 3.5k tokens；guard_sql 四条规则保证只读；"
            "协同日志十条里有五条是 AI 给错、人工纠正——这是我们团队协作的真实状态。")


def s08_viz(prs):
    s = page_base(prs, "07 可视化与部署", "三个终端，一条命令", 8)
    s.shapes.add_picture(str(IMG / "dashboard.png"), Inches(M - 0.05), Inches(1.66),
                         width=Inches(7.4))
    text(s, M, 5.98, 7.4, 0.24, "ECharts 大屏：7 类图表 · 1920×1080 自适应 · 断网走快照兜底",
         9.6, False, GRAY)

    text(s, 8.16, 1.66, 4.4, 0.24, "三个入口，对应三种角色", 10, True, BLUE)
    entries = [("Superset 仪表板", "管理视角：6 图 + 3 筛选器 + 交叉联动"),
               ("ECharts 大屏", "展厅视角：折线 / 地图 / 热力 / 散点 / 环形"),
               ("Streamlit 问答", "自助视角：提问 → SQL → 表格 → 图")]
    y = 1.96
    for name, desc in entries:
        rect(s, 8.16, y, 4.42, 0.82, fill=SOFT)
        text(s, 8.3, y + 0.1, 4.1, 0.24, name, 10.5, True, NAVY)
        text(s, 8.3, y + 0.38, 4.1, 0.34, desc, 9.2, False, GRAY, line=1.25)
        y += 0.94

    rect(s, 8.16, 4.86, 4.42, 1.86, fill=NAVY)
    text(s, 8.34, 4.96, 4.1, 0.24, "9 个服务：7 常驻 + 2 一次性任务", 9.6, True, SKY)
    text(s, 8.34, 5.24, 4.1, 0.26, "docker compose up -d", 12, True, WHITE)
    text(s, 8.34, 5.56, 4.12, 1.0,
         "mysql · hive-metastore · hive-server · clickhouse · superset · api · app\n"
         "一次性：mysql-init、superset-init（Exited 0 才是正常）",
         8.6, False, RGBColor(0xB9, 0xC9, 0xD9), line=1.5)
    note(s, "【4:10–4:45】这一页是大家最关心的“做出来长什么样”。左边是大屏，七类图表，"
            "1920 乘 1080 的设计尺寸加整体缩放，echarts 和中国地图都本地化，断网也能演示，"
            "接口不通会回落到快照文件，不会白屏。右上三个入口对应三种角色："
            "管理者看 Superset 仪表板，展厅看大屏，业务方自助用问答。"
            "右下是部署：九个服务，七个常驻加两个一次性初始化任务，一条 compose up 就起来。"
            "这里我踩过坑——一次性任务退出是正常的，退出码 0，不要当失败。")


def s09_perf(prs):
    s = page_base(prs, "08 性能优化", "四处优化，每一处都有前后对照", 9)
    cards = [("6.0×", "分区裁剪", "15.44 s → 2.58 s", "用 order_month 而不是 substr"),
             ("2.9×", "ADS 预聚合", "3.25 s → 1.13 s", "把 JOIN / 聚合前移到 ETL"),
             ("6.5×", "服务层缓存", "2,491 ms → 381 ms", "CH 副本 + 10s TTL，20 并发 p50"),
             ("113×", "换读取引擎", "4,418 ms → 39 ms", "Hive(Tez) 会话开销 vs CH 列存")]
    x = M
    for i, (mult, name, pair, why) in enumerate(cards):
        rect(s, x, 1.74, 2.86, 2.42, fill=SOFT)
        text(s, x + 0.2, 1.88, 2.4, 0.5, mult, 30, True, BLUE, line=1.0)
        text(s, x + 0.2, 2.44, 2.5, 0.26, name, 11, True, NAVY)
        text(s, x + 0.2, 2.74, 2.5, 0.26, pair, 10, False, ORANGE)
        text(s, x + 0.2, 3.1, 2.5, 0.86, why, 9, False, GRAY, line=1.35)
        x += 3.0

    rect(s, M, 4.42, 5.85, 2.3, fill=WHITE, line_color=LINE)
    text(s, M + 0.2, 4.54, 5.4, 0.24, "负面结果也留着：分桶 join 实测 16.47 s，无收益", 10,
         True, ORANGE)
    text(s, M + 0.2, 4.84, 5.45, 1.7,
         "dim_user 只有 1,000 行，Hive 会走 map join 直接广播，根本不进 shuffle。\n"
         "写进报告的原因是：优化要测，不能想当然——这条和上面四个倍数同样是结论。",
         9.8, False, INK, line=1.45)

    rect(s, 6.5, 4.42, 6.11, 2.3, fill=NAVY)
    text(s, 6.72, 4.54, 5.7, 0.24, "压测口径（第 4 周，4 组实验）", 9.8, True, SKY)
    for i, (v, l) in enumerate([("20", "并发客户端"), ("0%", "失败率"),
                                ("381 ms", "p50 延迟"), ("4 组", "对照实验")]):
        text(s, 6.72 + i * 1.46, 4.86, 1.3, 0.34, v, 15, True, WHITE, line=1.0)
        text(s, 6.72 + i * 1.46, 5.24, 1.34, 0.24, l, 8.4, False,
             RGBColor(0xA9, 0xBD, 0xD0))
    text(s, 6.72, 5.66, 5.7, 0.6,
         "压测脚本单独成目录，参数可复跑；报告里同时给了“优化前”的原始耗时。",
         9.2, False, RGBColor(0xB9, 0xC9, 0xD9), line=1.35)
    note(s, "【4:45–5:10】性能我放四个倍数：分区裁剪 6 倍、预聚合 2.9 倍、服务缓存 6.5 倍、"
            "换读取引擎 113 倍。每个都有优化前后的原始耗时，不是估的。"
            "左下这条我特意留着：给订单表和用户表做分桶 join，实测 16.47 秒，没有任何收益——"
            "因为用户表只有 1000 行，Hive 直接广播了，根本不进 shuffle。"
            "这条和那四个倍数一样是结论：优化要测，不能想当然。")


def s10_eng(prs):
    s = page_base(prs, "09 工程交付", "交付的是可复现的工程，不是一次演示", 10)
    # 左：Git
    text(s, M, 1.66, 5.4, 0.24, "Git：48 次提交，5 个功能分支，PR #12–#16", 10.5, True, BLUE)
    rows = [["项", "现状"],
            ["提交 / 分支", "48 次 / 5 个（feat 2、docs 3）"],
            ["约定式提交", "97.3%（历史 36/37）→ 本轮 100%"],
            ["PR / Issue", "PR #12–#16 + Issue #16（口径不一致）"],
            ["敏感信息", ".env 未入库，无明文 Key"]]
    table(s, M, 1.96, 6.0, rows, [0.30, 0.70], size=9.8, row_h=0.38, head_h=0.32)
    text(s, M, 4.04, 6.0, 0.44,
         "第 4 周有 3 个提交直接进 main，是本项目 Git 规范上的明确退步；"
         "我们补了成因说明与整改，没有重写已推送的历史。", 9.6, False, GRAY, line=1.4)

    # 左下：文档与自检
    text(s, M, 4.7, 5.4, 0.24, "五篇文档 + 一次端到端自检", 10.5, True, BLUE)
    docs = ["需求文档", "数据质量清洗报告", "架构设计文档", "部署手册", "API 配置指南"]
    x = M
    for i, d in enumerate(docs):
        rect(s, x, 5.0, 1.14, 0.5, fill=SOFT, line_color=LINE)
        text(s, x + 0.06, 5.1, 1.04, 0.28, d, 8.2, False, INK, align=PP_ALIGN.CENTER)
        x += 1.2
    text(s, M, 5.66, 6.0, 0.28, "＋ 英文 README（11 节）　＋ 端到端联调记录（6 个问题）", 9.4,
         False, GRAY)

    # 右：39 项
    rect(s, 7.06, 1.66, 5.55, 4.98, fill=NAVY)
    text(s, 7.3, 1.8, 5.0, 0.26, "一键自检：python 第5周/py/e2e_verify.py", 9.8, True, SKY)
    text(s, 7.3, 2.12, 5.0, 0.6, "39 / 39", 40, True, WHITE, line=1.0)
    text(s, 7.3, 2.78, 5.0, 0.26, "项核对全部通过（约 150 秒）", 9.8, False,
         RGBColor(0xB9, 0xC9, 0xD9))
    checks = [("9", "个服务状态：7 healthy + 2 Exited(0)"),
              ("51", "张表逐层行数：114,809 → 111,037"),
              ("8", "张 ADS 加总与口径交叉校验"),
              ("11", "张 CH 副本逐表行数一致"),
              ("10", "个接口全部 200")]
    y = 3.16
    for v, l in checks:
        text(s, 7.3, y, 0.5, 0.24, v, 11, True, SKY)
        text(s, 7.82, y, 4.6, 0.24, l, 9.2, False, RGBColor(0xC8, 0xD6, 0xE3))
        y += 0.4
    text(s, 7.3, 5.5, 5.0, 0.9,
         "证据落在 evidence/ 里，是真实命令输出，不是截图；换机器重跑一遍即可复核。",
         9.2, False, RGBColor(0x9F, 0xB3, 0xC6), line=1.4)
    note(s, "【5:10–5:35】工程质量这块，我讲两个“可复现”。一个是 Git：48 次提交、"
            "五个功能分支、PR 从 12 到 16，约定式提交历史 97.3%，本轮 100%。"
            "第 4 周有三个提交直接进了 main，这是我们明确的一次退步，"
            "我补了成因说明和整改，但没有重写已经推送的历史。"
            "另一个是自检：一条命令跑 39 项核对，从九个服务到四层行数、"
            "到八张 ADS 的加总、到十一张副本、到十个接口，全过。证据是真实命令输出。")


def s11_review(prs):
    s = page_base(prs, "10 复盘", "三件做对了，三件还不够", 11)
    rect(s, M, 1.7, 5.85, 4.9, fill=SOFT)
    text(s, M + 0.22, 1.82, 5.3, 0.26, "做对的", 10.5, True, BLUE)
    goods = [("先定口径，再写 SQL", "金额三口径、门店按编号、周按 53 周，都在动手前定死"),
             ("先出证据，再写文档", "文档里每个数字都能指回 evidence 里的一行输出"),
             ("不好看的结论也留着", "预测没赢基线、时段是噪声、分桶无收益，全部写进报告")]
    y = 2.16
    for i, (t, d) in enumerate(goods, 1):
        text(s, M + 0.22, y, 0.4, 0.28, f"0{i}", 12, True, SKY)
        text(s, M + 0.62, y, 4.9, 0.28, t, 11.5, True, NAVY)
        text(s, M + 0.62, y + 0.3, 4.95, 0.66, d, 9.4, False, GRAY, line=1.4)
        y += 1.02

    rect(s, 6.72, 1.7, 5.89, 4.9, fill=WHITE, line_color=LINE)
    text(s, 6.94, 1.82, 5.3, 0.26, "还不够的", 10.5, True, ORANGE)
    bads = [("第 4 周的提交没走分支", "为了赶演示，牺牲了过程留痕；提交粒度也过粗"),
            ("NL2SQL 缺评测集", "只能证明“能用”，证明不了“准确率多少”"),
            ("两块图不能下业务结论", "时段热力图是随机字段、漏斗是并列采样")]
    y = 2.16
    for i, (t, d) in enumerate(bads, 1):
        text(s, 6.94, y, 0.4, 0.28, f"0{i}", 12, True, ORANGE)
        text(s, 7.34, y, 4.9, 0.28, t, 11.5, True, NAVY)
        text(s, 7.34, y + 0.3, 4.95, 0.66, d, 9.4, False, GRAY, line=1.4)
        y += 1.02

    text(s, M, 6.72, CW, 0.24,
         "下一步：30 条问题的 NL2SQL 评测集 → 一条日增量链路 → 用 rem / 断点做真正自适应的大屏",
         9.8, False, GRAY, align=PP_ALIGN.CENTER)
    note(s, "【5:35–5:55】最后一页是复盘。做对的三件事：先定口径再写 SQL；"
            "先出证据再写文档；不好看的结论也留着——预测没赢基线、时段热力图是噪声、"
            "分桶 join 没收益，这三条都写在报告里，因为它们同样是结论。"
            "还不够的三件事也得说：第 4 周赶进度没走分支；NL2SQL 没有评测集，"
            "只能说能用，说不出准确率；有两块图只能证明链路通，不能下业务结论。"
            "这三条是我们下一步要补的。")


def s12_end(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, W, H, fill=NAVY)
    rect(s, -1.2, 3.6, 4.6, 4.6, fill=BLUE, shape=MSO_SHAPE.OVAL, alpha=18)
    text(s, M, 2.16, 8.6, 0.78, "谢谢，请老师批评", 34, True, WHITE, line=1.1)
    rect(s, M, 2.96, 1.5, 0.045, fill=ORANGE)
    text(s, M, 3.24, 9.4, 0.7,
         "演示环境已就绪：docker compose ps 可见 7 个 healthy + 2 个 Exited(0)", 13, False,
         RGBColor(0xBF, 0xCF, 0xDD), line=1.4)
    text(s, M, 4.24, 9.4, 0.7,
         "全部数字可用一条 SQL 复现：python 第5周/py/e2e_verify.py", 13, False,
         RGBColor(0xBF, 0xCF, 0xDD), line=1.4)

    text(s, M, 5.5, 2.0, 0.24, "代码仓库", 9.5, True, SKY)
    text(s, M, 5.76, 7.2, 0.28, "github.com/yuyu52525/xmsx　·　main（48 提交）", 11, False, WHITE)
    text(s, M, 6.2, 2.0, 0.24, "文档", 9.5, True, SKY)
    text(s, M, 6.46, 8.6, 0.28, "五篇项目文档 + 英文 README + 端到端联调记录", 11, False, WHITE)
    text(s, W - M - 1.6, 6.4, 1.6, 0.28, "Q & A", 16, True, SKY, align=PP_ALIGN.RIGHT)
    note(s, "【5:55–6:00】这就是我的汇报，谢谢老师。演示环境现在是起着的，"
            "七个常驻服务健康、两个一次性任务已经退出；如果老师想看任何一个数，"
            "我们现场跑一条命令就能回到源头。请老师提问。")


def build() -> Path:
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    for fn in (s01_cover, s02_problem, s03_arch, s04_clean, s05_metric, s06_result,
               s07_ai, s08_viz, s09_perf, s10_eng, s11_review, s12_end):
        fn(prs)
    prs.core_properties.title = "云购生活 · 企业级数据仓库与经营分析可视化系统（答辩）"
    prs.core_properties.author = "余天乐"
    prs.core_properties.subject = "企业项目实战实训 · 第 5 周综合答辩"
    prs.save(str(OUT))
    return OUT


if __name__ == "__main__":
    print(build())