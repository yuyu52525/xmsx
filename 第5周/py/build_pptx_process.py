"""第 5 周 · 答辩 PPT（过程版）生成脚本 —— 16 页 / 约 7 分 10 秒

与《答辩PPT_第5周.pptx》的区别：
  那一版是"结论式"（12 页 6 分钟，讲结果与判断）；
  这一版是"过程式"（16 页），按任务书的 12 个子任务走一遍流水线：
  每页固定四块 —— 这一步要解决什么 / 怎么做 / 产出什么 / 踩了什么坑，
  底部带 12 格进度条，评委随时知道讲到第几步。

为什么复用 build_pptx.py 的助手：版式常量、字体、表格样式已经在那一版调好，
这里只换叙事结构，避免两套字号与配色。

用法：python build_pptx_process.py
输出：../docs/答辩PPT_第5周_过程版.pptx
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pptx.chart.data import CategoryChartData          # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE, XL_TICK_MARK  # noqa: E402
from pptx.enum.text import PP_ALIGN                    # noqa: E402
from pptx.enum.shapes import MSO_SHAPE                 # noqa: E402
from pptx.dml.color import RGBColor                    # noqa: E402
from pptx.util import Inches, Pt                       # noqa: E402

from build_pptx import (                               # noqa: E402
    W, H, M, CW, NAVY, INK, BLUE, SKY, ORANGE, GRAY, LINE, SOFT, WHITE,
    text, rect, table, note, style,
)

DOCS = HERE.parent / "docs"
OUT = DOCS / "答辩PPT_第5周_过程版.pptx"

TOTAL_STEPS = 12
STEPS = [
    "搭环境", "导入 ODS", "质量评估", "数据清洗", "建 DWD", "建 DWS",
    "建 ADS", "做预测", "NL2SQL", "可视化", "部署", "联调收口",
]
PHASE = {1: "数据准备", 2: "数据准备", 3: "数据准备", 4: "数据准备",
         5: "数仓建模", 6: "数仓建模", 7: "数仓建模",
         8: "分析智能", 9: "分析智能",
         10: "应用交付", 11: "应用交付", 12: "应用交付"}


# ------------------------------------------------------------------ 版式组件
def progress(s, current: int) -> None:
    """底部 12 格进度条：已讲过=浅蓝，当前=深蓝，未讲=灰。"""
    bw, gap = 0.86, 0.1
    x = M
    for i in range(1, TOTAL_STEPS + 1):
        fill = NAVY if i == current else (SKY if i < current else LINE)
        rect(s, x, 6.58, bw, 0.075, fill=fill)
        x += bw + gap


def head(s, step: int, title: str, page: int) -> None:
    """步骤页页眉：步骤徽标 + 阶段 + 标题 + 页码。"""
    rect(s, M, 0.48, 1.28, 0.44, fill=NAVY)
    text(s, M, 0.54, 1.28, 0.24, f"步骤 {step:02d}", 10.5, True, WHITE,
         align=PP_ALIGN.CENTER)
    text(s, M + 1.44, 0.5, 5.2, 0.24,
         f"{PHASE[step]}　·　{STEPS[step - 1]}", 10.5, True, BLUE)
    text(s, W - M - 0.8, 0.5, 0.8, 0.24, f"{page:02d}", 10, False, GRAY,
         align=PP_ALIGN.RIGHT)
    text(s, M, 1.04, CW, 0.52, title, 23, True, NAVY, line=1.2)


def label(s, x, y, txt: str, color=BLUE) -> None:
    rect(s, x, y + 0.03, 0.055, 0.16, fill=color)
    text(s, x + 0.14, y, 4.0, 0.22, txt, 10, True, color)


def actions(s, x, y, w, items: list[tuple[str, str]], size: float = 11.6) -> float:
    """三步做法：数字圆点 + 粗标题 + 说明。返回占用高度。"""
    cy = y
    for i, (title, desc) in enumerate(items, 1):
        rect(s, x, cy + 0.02, 0.3, 0.3, fill=BLUE, shape=MSO_SHAPE.OVAL)
        text(s, x, cy + 0.06, 0.3, 0.22, str(i), 9.5, True, WHITE, align=PP_ALIGN.CENTER)
        text(s, x + 0.42, cy - 0.01, w - 0.42, 0.26, title, size, True, NAVY)
        lines = max(1, int(len(desc) / max(8, (w - 0.42) * 72 / (size - 2.4))))
        text(s, x + 0.42, cy + 0.28, w - 0.42, 0.22 * lines + 0.05, desc, size - 2.2,
             False, GRAY, line=1.35)
        cy += 0.34 + 0.2 * lines + 0.3
    return cy - y


def pitfall(s, y, title: str, body: str) -> None:
    """踩坑条：一处具体问题 + 怎么解的。"""
    rect(s, M, y, CW, 0.78, fill=RGBColor(0xFD, 0xF2, 0xE9))
    rect(s, M, y, 0.05, 0.78, fill=ORANGE)
    text(s, M + 0.18, y + 0.1, 1.5, 0.24, title, 9.8, True, ORANGE)
    text(s, M + 1.35, y + 0.1, CW - 1.5, 0.58, body, 10, False, INK, line=1.4)


def out_card(s, x, y, w, h, items: list[tuple[str, str]]) -> None:
    """产出卡：左侧竖排若干"数字 + 说明"。"""
    rect(s, x, y, w, h, fill=SOFT)
    cy = y + 0.16
    for v, l in items:
        text(s, x + 0.18, cy, w - 0.3, 0.3, v, 17, True, BLUE, line=1.0)
        text(s, x + 0.18, cy + 0.3, w - 0.3, 0.2, l, 9.2, False, GRAY)
        cy += 0.56


# ------------------------------------------------------------------ 各页
def s01_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, W, H, fill=NAVY)
    rect(s, 9.3, -1.9, 6.4, 6.4, fill=BLUE, shape=MSO_SHAPE.OVAL, alpha=20)
    rect(s, 11.2, 4.6, 3.2, 3.2, fill=SKY, shape=MSO_SHAPE.OVAL, alpha=12)

    text(s, M, 1.4, 8.6, 0.3, "企业项目实战实训 · 第 5 周综合答辩（过程版）", 12.5, True, SKY)
    text(s, M, 1.86, 9.6, 0.86, "从 6 张 CSV", 46, True, WHITE, line=1.05)
    text(s, M, 2.72, 9.6, 0.86, "到 3 个终端", 46, True, WHITE, line=1.05)
    rect(s, M, 3.86, 1.5, 0.045, fill=ORANGE)
    text(s, M, 4.06, 9.2, 0.7,
         "12 个步骤走完一条可复现的数据流水线：每一步都有输入、动作、产出和踩过的坑",
         14.5, False, RGBColor(0xBF, 0xCF, 0xDD), line=1.4)

    items = [("12", "个步骤"), ("5", "周 / 16 课时/周"), ("51", "张数仓表"), ("9", "个容器服务")]
    x = M
    for i, (v, l) in enumerate(items):
        text(s, x, 5.5, 1.9, 0.42, v, 25, True, SKY, line=1.0)
        text(s, x, 5.94, 1.95, 0.24, l, 10, False, RGBColor(0x9F, 0xB3, 0xC6))
        if i < 3:
            rect(s, x + 1.66, 5.54, 0.008, 0.5, fill=RGBColor(0x2E, 0x4A, 0x66))
        x += 2.2

    text(s, M, 6.62, 9.0, 0.26, "余天乐　20230308098　·　数据科学与大数据技术　·　团队 乐天",
         10.5, False, RGBColor(0x9F, 0xB3, 0xC6))
    note(s, "【0:00–0:20】各位老师好，我是余天乐。这次我换一个讲法：不先讲结论，"
            "而是把这条流水线走一遍——从 6 张 CSV 开始，到 3 个可视化终端为止，一共 12 个步骤。"
            "每讲到一步，我都会说清楚四件事：这一步要解决什么、我怎么做、产出了什么、踩了什么坑。"
            "这样各位能看清这套系统是怎么一步步搭起来的。")


def s02_pipeline(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, M, 0.48, 0.055, 0.2, fill=BLUE)
    text(s, M + 0.16, 0.45, 6.0, 0.24, "全流程", 10.5, True, BLUE)
    text(s, W - M - 0.8, 0.48, 0.8, 0.24, "02", 10, False, GRAY, align=PP_ALIGN.RIGHT)
    text(s, M, 0.76, CW, 0.6, "12 个步骤，四段推进，任何一步都能单独验收", 24, True, NAVY)

    colors = {"数据准备": SKY, "数仓建模": BLUE, "分析智能": NAVY, "应用交付": RGBColor(0x2A, 0x4A, 0x6B)}
    # 两行六列
    bw, bh, gx, gy = 1.62, 1.14, 0.34, 0.5
    for i in range(12):
        step = i + 1
        col = colors[PHASE[step]]
        row, c = divmod(i, 6)
        x = M + c * (bw + gx)
        y = 1.72 + row * (bh + gy)
        rect(s, x, y, bw, bh, fill=col)
        text(s, x + 0.14, y + 0.1, bw - 0.24, 0.22, f"{step:02d}", 9, True,
             RGBColor(0xDC, 0xE6, 0xF1))
        text(s, x + 0.14, y + 0.4, bw - 0.2, 0.5, STEPS[i], 12.5, True, WHITE, line=1.3)
        if c < 5:
            text(s, x + bw + 0.06, y + bh / 2 - 0.14, 0.24, 0.28, "›", 15, True,
                 RGBColor(0xB6, 0xC5, 0xD3))

    # 图例
    lx = M
    for name, col in colors.items():
        rect(s, lx, 5.02, 0.14, 0.14, fill=col)
        text(s, lx + 0.2, 4.99, 1.7, 0.22, name, 9.5, False, GRAY)
        lx += 1.62

    rect(s, M, 5.42, CW, 1.0, fill=SOFT)
    text(s, M + 0.2, 5.52, CW - 0.4, 0.24,
         "为什么按步骤讲：每一步都对应任务书的一个子任务，也都有可检查的产出", 10, True, BLUE)
    text(s, M + 0.2, 5.78, CW - 0.4, 0.56,
         "第 1～4 步把脏数据变成可算的数据；第 5～7 步把它组织成能复用的数仓；"
         "第 8～9 步在数仓上做预测与问答；第 10～12 步把它交付成别人能用的系统。", 10.5, False,
         INK, line=1.45)
    note(s, "【0:20–0:55】先看全景。一共 12 步，分成四段：前三步到第四步是数据准备，"
            "五六七是数仓建模，八九是分析智能，十到十二是应用交付。"
            "我之所以按步骤讲，是因为每一步都对应任务书里的一个子任务，"
            "而且每一步都有能拿出来的东西——脚本、表、图、或者一份证据。"
            "下面开始，第一步：把环境跑起来。")


def s03_map(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, M, 0.48, 0.055, 0.2, fill=BLUE)
    text(s, M + 0.16, 0.45, 6.0, 0.24, "任务书对照", 10.5, True, BLUE)
    text(s, W - M - 0.8, 0.48, 0.8, 0.24, "03", 10, False, GRAY, align=PP_ALIGN.RIGHT)
    text(s, M, 0.76, CW, 0.6, "五周任务书，一共 20 个子任务，全部有产出", 24, True, NAVY)

    rows = [["周次", "任务书主题", "关键子任务", "对应步骤"],
            ["第 1 周", "环境 · Git · 导入 · 清洗（一）", "环境搭建 / Git 规范 / ODS 6 表 / 五维预评估 / 缺失与重复", "1 2 3"],
            ["第 2 周", "清洗（二）· 四层建模 · 探索分析", "枚举标准化 / 异常值格式 / 拆分合并 / 架构与 DWD / EDA", "4 5"],
            ["第 3 周", "DWS/ADS · 预测 · AI 协同", "DWS 9 表 / ADS 9 表 / KPI / 预测建模 / NL2SQL / AI 洞察", "6 7 8 9"],
            ["第 4 周", "可视化 · 部署", "Superset / ECharts 大屏 / Streamlit / Compose / 压测优化", "10 11"],
            ["第 5 周", "整合 · 文档 · 答辩", "端到端联调 / 五篇文档 / Git 审查 / 英文 README / 答辩", "12"]]
    table(s, M, 1.62, CW, rows, [0.13, 0.28, 0.45, 0.14], size=10.2, row_h=0.62, head_h=0.36)

    rect(s, M, 5.5, CW, 0.92, fill=SOFT)
    text(s, M + 0.2, 5.6, CW - 0.4, 0.24,
         "这张表是我用来防止“漏做”的清单：每周收尾时对一遍，缺哪项补哪项", 10, True, BLUE)
    text(s, M + 0.2, 5.86, CW - 0.4, 0.46,
         "20 个子任务里有 3 个是“软要求”（团队分工、答辩表达、协作记录），其余 17 个都有可验证产物。",
         10.5, False, INK, line=1.4)
    note(s, "【0:55–1:20】这是五周任务书的对照表，20 个子任务我全部过了一遍。"
            "做这张表的用处很实际：每周收尾时对一遍，防止漏项——"
            "第 5 周我就是靠它发现“Git 分支记录”这一项第 4 周漏了。"
            "接下来按步骤走，每页右上角都有页码，底部有进度条。")


def s04_env(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 1, "先把“能跑起来”这件事解决，再谈数据", 4)
    label(s, M, 1.62, "这一步要解决什么")
    text(s, M, 1.9, 4.15, 1.2,
         "六张 CSV 躺在硬盘上，没有任何服务能读它。\n"
         "第一步是把“数据仓库的操作系统”装上：Docker、Hive、MySQL、Git。", 11.6, False, INK,
         line=1.5)
    label(s, M, 3.06, "产出什么")
    out_card(s, M, 3.34, 4.15, 2.0, [
        ("Hive 4.0.0", "beeline 能连、能 show databases"),
        ("MySQL 8.0", "metastore 用它存元数据"),
        ("环境笔记", "8 个问题 + 解法，共 8.5 KB"),
    ])

    label(s, 5.06, 1.62, "怎么做")
    actions(s, 5.06, 1.94, 7.1, [
        ("装 Docker Desktop + WSL2", "确认 docker ps 有输出、容器引擎版本可用，才算环境通了"),
        ("用 compose 起 Hive 与 MySQL", "metastore 依赖 MySQL；hive-server 依赖 metastore，按依赖顺序起"),
        ("写 8 条踩坑记录", "端口冲突、驱动缺失、WSL 未更新……每条都写“现象 → 原因 → 解法”"),
    ])
    pitfall(s, 5.62, "最典型的坑",
            "hive-metastore 反复重启：先看日志确认是等 MySQL 超时，再补 JDBC 驱动并加 healthcheck；"
            "3306 端口被占用时改映射到 3307。这两条后来写进了部署手册。")
    progress(s, 1)
    note(s, "【1:20–1:45】第一步搭环境。这一步最容易卡住人，我记了 8 个坑。"
            "最典型的是 metastore 反复重启——日志里其实写着连不上 MySQL，"
            "但一开始我以为是内存不够，白折腾了半天。"
            "后来养成习惯：先看日志第一行，再猜原因。这一步的产出不是数据，是一份能复现的环境笔记。")


def s05_ods(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 2, "6 张 CSV 原样搬进 ODS，一行都不改", 5)
    label(s, M, 1.62, "这一步要解决什么")
    text(s, M, 1.9, 4.15, 1.2,
         "把外部文件变成能用 SQL 查的表。\n"
         "原则是“贴源”：脏数据也一起搬进来，先看清原样，再决定怎么治。", 11.6, False, INK,
         line=1.5)
    label(s, M, 3.06, "产出什么")
    out_card(s, M, 3.34, 4.15, 2.0, [
        ("6 张 ODS 表", "user / product / store / order / item / behavior"),
        ("114,809 行", "与数据字典逐表核对一致"),
        ("2 个脚本", "create_ods.sql、load_ods.sql"),
    ])

    label(s, 5.06, 1.62, "怎么做")
    actions(s, 5.06, 1.94, 7.1, [
        ("建 6 张外部表，全用 TEXTFILE", "逗号分隔、字段全 string——先用字符串接住，后面再转型，脏值不会静默变 NULL"),
        ("加载时跳过表头", "tblproperties('skip.header.line.count'='1')，否则第一行数据是字段名"),
        ("逐表 count(*) 对数据字典", "6 张表分别核对，合计 114,809 行才算导入成功"),
    ])
    pitfall(s, 5.62, "踩过的坑",
            "日期字段一开始建成 date 类型，导入时脏日期被静默转成 NULL，脏数据“消失”了；"
            "改成 string 全部接住，问题才暴露出来。这条后来成了全项目的字段约定。")
    progress(s, 2)
    note(s, "【1:45–2:10】第二步导入。这里有个决定影响后面所有事：字段全用 string。"
            "我第一版把日期建成 date，结果脏日期导入后变成 NULL，脏数据凭空消失——"
            "问题不是被修好了，是被藏起来了。改成 string 之后，问题才浮出来。"
            "所以“贴源层原样接住”不是偷懒，是为了让问题可见。")


def s06_quality(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 3, "先用 SQL 把问题数清楚，再动手改", 6)
    label(s, M, 1.62, "这一步要解决什么")
    text(s, M, 1.9, 4.15, 1.3,
         "不能“看着像脏的就删”。先按五个维度全量扫描，\n"
         "把每一类问题变成可统计的数字，清洗才有依据。", 11.6, False, INK, line=1.5)

    label(s, M, 3.16, "五个维度扫出 72,156 条问题")
    dims = [("完整性", "255", "空值率"), ("唯一性", "600", "主键重复"), ("有效性", "60,520", "枚举取值"),
            ("一致性", "8,217", "格式统一"), ("准确性", "2,564", "取值合理")]
    y = 3.46
    for name, v, note_ in dims:
        text(s, M, y, 1.0, 0.24, name, 10, True, NAVY)
        text(s, M + 1.0, y, 1.1, 0.24, v, 11, True, ORANGE)
        text(s, M + 2.15, y, 1.9, 0.24, note_, 9, False, GRAY)
        y += 0.34

    label(s, 5.06, 1.62, "怎么做")
    actions(s, 5.06, 1.94, 7.1, [
        ("枚举字段先 select distinct", "把 6～16 种写法全列出来，才能写全映射；漏一个值就会多出一组“脏分类”"),
        ("数值字段看分布，不只看阈值", "分位数、箱线图、直方图一起看：异常值占 3.8%，P99 已经被污染"),
        ("结果落成一张预评估表", "每个字段的问题数、样例值、建议处理方式，一张表交代清楚"),
    ])
    pitfall(s, 5.62, "为什么这一步不能省",
            "如果跳过评估直接清洗，就会出现“删了但说不清删了多少”的情况；"
            "有了这张表，后面每个删除/修正动作都能指回具体数字。")
    progress(s, 3)
    note(s, "【2:10–2:35】第三步评估。这一步的目标不是改数据，是把问题数字化。"
            "五个维度扫下来一共 72156 条，其中六成是枚举写法不统一。"
            "这里有个经验：枚举字段一定要先 select distinct 看全集，"
            "我第一版映射漏了 silver，结果 12 条银卡用户掉成了空值。")


def s07_clean(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 4, "清洗不是“删干净”，是“每一步都说得出理由”", 7)
    label(s, M, 1.58, "清洗前后")
    text(s, M, 1.86, 2.0, 0.34, "114,809", 20, True, NAVY, line=1.0)
    text(s, M + 2.0, 1.94, 0.4, 0.24, "→", 12, True, GRAY)
    text(s, M + 2.4, 1.86, 1.9, 0.34, "111,037", 20, True, BLUE, line=1.0)
    rect(s, M, 2.28, 4.0, 0.1, fill=RGBColor(0xC9, 0xD6, 0xE2))
    rect(s, M, 2.28, 4.0 * 0.9671, 0.1, fill=BLUE)
    text(s, M, 2.46, 4.1, 0.24, "剔除 3,772 行（3.29%），逐行可追溯", 9.5, False, GRAY)

    rows = [["五类问题", "怎么处理", "条数"],
            ["缺失", "年龄均值填、邮箱只标记、上架日期按类目补", "255"],
            ["重复", "同号异构也删，按 order_id 取第一条", "600"],
            ["格式", "日期 / 手机号 / 时间统一成一种写法", "8,217"],
            ["异常", "金额按 IQR 删、单价按商品中位数修", "2,564"],
            ["枚举", "映射到中文标准值（8 种→3 种等）", "60,520"]]
    table(s, M, 2.8, 6.4, rows, [0.16, 0.66, 0.18], size=9.6, row_h=0.4, head_h=0.34,
          align_right=[2])

    label(s, 6.96, 1.58, "三种策略，不做一刀切")
    strat = [("3,772", "行", "删除", "重复 600 + 金额 602 + 数量 1,081 + 关联明细 1,489"),
             ("861", "条", "修正", "单价 773 + 商品价 36 + 年龄 27 + 等级 14 + 日期 11"),
             ("193", "行", "标记", "邮箱缺失：业务上允许为空，只打 email_missing 标记")]
    y = 1.88
    for num, unit, name, desc in strat:
        rect(s, 6.96, y, 5.4, 0.66, fill=SOFT)
        text(s, 7.12, y + 0.08, 0.72, 0.28, num, 15, True, BLUE, line=1.0)
        text(s, 7.86, y + 0.16, 0.26, 0.2, unit, 8.4, False, GRAY)
        text(s, 8.24, y + 0.1, 0.62, 0.24, name, 9.6, True, NAVY)
        text(s, 8.94, y + 0.1, 3.3, 0.5, desc, 8.6, False, GRAY, line=1.35)
        y += 0.74
    text(s, 6.96, 4.14, 5.4, 0.24,
         "三者计量单位不同（行 / 字段 / 行），不做加总。", 8.8, False, GRAY)

    pitfall(s, 5.35, "一个判断值得单说",
            "金额上限没用教科书的 P99（实测 551 万元，因为异常值占 3.8%，百分位已落在脏数据堆里），"
            "改用 IQR 得 11,356 元，正好落在 5 千到 10 万之间的金额断崖上。")
    progress(s, 4)
    note(s, "【2:35–3:05】第四步清洗。核心是一句话：清洗不是删干净，是每一步都说得出理由。"
            "行数从 114809 到 111037，剔除 3772 行，三种策略分别对应删除、修正、标记。"
            "最值得讲的是金额阈值：教科书写用 P99，但这里 P99 是 551 万——"
            "因为异常值占了 3.8%，已经把百分位抬进脏数据堆了；改用 IQR 得到 11356 元，"
            "正好卡在真实的金额断崖上。阈值要用数据自己的分布验证。")


def s08_dwd(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 5, "把“一张大表”拆成“事实 + 维度”", 8)
    label(s, M, 1.58, "星型模型：谁在什么时候、在哪、买了什么")
    # 四个维度
    dims = [("用户", "1,000"), ("商品", "600"), ("门店", "60"), ("日期", "731")]
    x = M
    for name, n in dims:
        rect(s, x, 1.9, 1.36, 0.66, fill=SOFT, line_color=LINE)
        text(s, x, 1.96, 1.36, 0.24, name, 10, True, NAVY, align=PP_ALIGN.CENTER)
        text(s, x, 2.2, 1.36, 0.24, n, 9.5, False, GRAY, align=PP_ALIGN.CENTER)
        x += 1.48
    # 事实
    facts = [("订单 dwd_order", "14,398 单"), ("明细 dwd_order_item", "34,979 行"),
             ("行为 dwd_user_behavior", "60,000 条")]
    x = M
    for name, n in facts:
        rect(s, x, 2.72, 1.96, 0.6, fill=NAVY)
        text(s, x, 2.78, 1.96, 0.24, name, 9.4, True, WHITE, align=PP_ALIGN.CENTER)
        text(s, x, 3.02, 1.96, 0.22, n, 9, False, RGBColor(0xC8, 0xD6, 0xE3),
             align=PP_ALIGN.CENTER)
        x += 2.1

    label(s, M, 3.54, "另外还有 4 张编码表 + 14 张清洗中间表，用来“看得见每一步”")
    text(s, M, 3.82, 6.2, 1.3,
         "编码表把“状态码 → 是否计入营收”这类业务规则从 SQL 里挪进表；\n"
         "中间表保留每一步的行数变化，答辩时可以逐段演示哪一步吃掉了多少行。", 10.2, False,
         GRAY, line=1.45)

    label(s, 7.1, 1.58, "三个设计决定")
    actions(s, 7.1, 1.9, 5.2, [
        ("按月分区，不按天", "按天会有 366 个不到 40 行的小分区；按月 12 个，正合月度分析"),
        ("只给订单表按 user_id 分 8 桶", "用户级分析是主场景；1.4 万行分 8 桶，每桶约 1,800 行"),
        ("金额存两套字段", "item_amount 是原价、alloc_amount 是分摊后的成交额，避免口径混用"),
    ], size=10.6)

    pitfall(s, 5.42, "最容易错的地方",
            "明细原价合计是订单实付的 11.2 倍，直接用 `item_amount` 算品类占比，加起来不等于 100%；"
            "所以造了 `alloc_amount`，把订单实付按明细占比分摊下去，分摊合计与实付只差 0.65 元。")
    progress(s, 5)
    note(s, "【3:05–3:35】第五步建 DWD。以前六张表各说各话，现在按“谁在什么时候、在哪、买了什么”"
            "组织成四张维度表加三张事实表。三个决定里，最关键的是金额存两套："
            "原价和分摊后的成交额。因为明细原价加起来是订单实付的 11 倍，"
            "直接拿它算品类占比，加起来不是 100%，图就废了。")


def s09_dws(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 6, "先按“粒度”预汇总，别让每个图表都回头算明细", 9)
    label(s, M, 1.58, "9 张汇总表，按不同粒度各司其职")
    rows = [["表", "粒度", "行数", "服务什么"],
            ["dws_sales_day", "日 × 渠道", "1,464", "日趋势"],
            ["dws_sales_week", "周 × 渠道", "212", "周对比"],
            ["dws_sales_month", "月 × 渠道", "48", "月度趋势"],
            ["dws_category_month", "月 × 品类", "96", "品类结构"],
            ["dws_store_month", "月 × 门店", "720", "门店排行"],
            ["dws_province_month", "月 × 省份", "180", "区域地图"],
            ["dws_user_month", "月 × 用户", "8,448", "用户价值"],
            ["dws_behavior_day", "日 × 行为", "368", "行为漏斗"]]
    table(s, M, 1.88, 7.5, rows, [0.30, 0.24, 0.16, 0.30], size=9.4, row_h=0.37, head_h=0.32,
          align_right=[2])

    label(s, 8.66, 1.58, "为什么值得单独一层")
    text(s, 8.66, 1.88, 3.8, 1.9,
         "ADS 和图表都要按维度聚合。\n"
         "如果每个图都从 3.5 万行明细现算，慢且容易各算各的；\n"
         "预汇总一次，后面所有图都读这一份，口径自然一致。", 10.2, False, INK, line=1.5)
    label(s, 8.66, 3.94, "一道自检")
    text(s, 8.66, 4.22, 3.8, 0.9,
         "日、周、月三个粒度的 GMV 加总，必须都等于 36,116,687.06；"
         "不相等说明有重复计数或漏渠道。", 10, False, GRAY, line=1.45)

    pitfall(s, 5.36, "一个数字陷阱",
            "dws_sales_week 是 212 行不是 208：2024 年按 ISO 有 53 周，最后一周只有 12-30、12-31 两天，"
            "所以那一周数值偏小，不能拿它说“最后一周最差”。")
    progress(s, 6)
    note(s, "【3:35–4:00】第六步 DWS。这一层解决的是“别让每张图都回头算明细”。"
            "九张表按不同粒度预汇总，日、周、月、品类、门店、省份、用户、行为各有分工。"
            "上面有一道自检：三个粒度的 GMV 加总必须完全相等，不等就说明重复计费或漏了渠道。"
            "底下这个坑也值得说：周表是 212 行而不是 208 行，因为 2024 年有 53 个 ISO 周。")


def s10_ads(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 7, "ADS 一层只做一件事：一张表服务一类图", 10)
    label(s, M, 1.58, "11 张应用表")
    ads = [("指标卡", "ads_kpi_overview"), ("月度趋势", "ads_kpi_month"), ("日趋势", "ads_sales_daily"),
           ("品类榜", "ads_category_rank"), ("省份地图", "ads_province_sales"), ("门店排行", "ads_store_rank"),
           ("渠道结构", "ads_channel_month"), ("行为漏斗", "ads_behavior_funnel"),
           ("用户分层", "ads_user_rfm"), ("支付方式", "ads_pay_type_month"), ("时段热力", "ads_hour_category")]
    for i, (name, tbl) in enumerate(ads):
        col, row = i % 3, i // 3
        bx, by = M + col * 2.13, 1.88 + row * 0.72
        rect(s, bx, by, 2.05, 0.62, fill=SOFT, line_color=LINE)
        text(s, bx + 0.1, by + 0.07, 1.85, 0.24, name, 9.4, True, NAVY)
        text(s, bx + 0.1, by + 0.32, 1.88, 0.22, tbl, 7.2, False, GRAY)

    rect(s, M, 4.86, 6.2, 0.82, fill=RGBColor(0xFD, 0xF2, 0xE9))
    text(s, M + 0.18, 4.94, 5.9, 0.24, "设计原则：指标口径写死在表里", 9.6, True, ORANGE)
    text(s, M + 0.18, 5.18, 5.9, 0.44,
         "BI 端不再做二次计算——“图上显示的数”和“文档里写的数”必然是同一个数。", 9.4, False,
         INK, line=1.3)

    text(s, M, 5.86, 6.2, 0.4,
         "11 张表共 2,666 行，最大的表 1,000 行——所以能全量预计算，图表点开就有。", 9.2, False,
         GRAY, line=1.35)

    label(s, 7.1, 1.58, "核心指标（每个都能回算）")
    kpis = [("36,116,687.06", "GMV（订单口径，元）"), ("24,185,272.59", "有效 GMV（66.96%）"),
            ("14,398 / 1,000", "订单量 / 下单用户"), ("2,508.45 / 36,116.69", "客单价 / ARPU")]
    y = 1.9
    for v, l in kpis:
        text(s, 7.1, y, 5.2, 0.3, v, 16, True, BLUE, line=1.0)
        text(s, 7.1, y + 0.28, 5.2, 0.22, l, 9, False, GRAY)
        y += 0.62

    text(s, 7.1, 4.5, 5.2, 0.86,
         "⚠ 金额有三个口径：订单 3,611.67 万、分摊 3,583.33 万、原价 4.03 亿。"
         "原价只能当权重，两个口径相加没有意义。", 9.2, False, GRAY, line=1.4)
    progress(s, 7)
    note(s, "【4:00–4:25】第七步 ADS。这一层很朴素：一张表服务一类图，十一张表对应十一类图。"
            "好处是口径写死在表里，BI 端不再二次计算，图上显示的数就是文档里写的数。"
            "右边六个核心指标，每一个都能从 DWD 回算出来——这是我在第五周做联调时反复验证的。")


def s11_forecast(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 8, "预测做了五步，最后一步是“承认它不如均值”", 11)
    label(s, M, 1.58, "五步流程")
    steps = [("取数", "ads_sales_daily 366 天"), ("造特征", "lag_1 / lag_7 / ma_7 / ma_14 + 星期 / 月份"),
             ("切分", "按时间切，不随机打乱"), ("三个模型对照", "线性回归 / 朴素基线 / 常数基线"),
             ("回测", "6 折滚动起点，看稳定性")]
    y = 1.9
    for i, (name, desc) in enumerate(steps, 1):
        text(s, M, y, 0.34, 0.24, str(i), 10, True, BLUE)
        text(s, M + 0.36, y - 0.01, 1.7, 0.24, name, 10.5, True, NAVY)
        text(s, M + 2.1, y, 4.4, 0.22, desc, 9.4, False, GRAY)
        y += 0.42

    cd = CategoryChartData()
    cd.categories = ["常数基线", "线性回归", "朴素基线"]
    cd.add_series("MAPE", [12.11, 12.72, 20.08])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(M - 0.08), Inches(4.18),
                            Inches(5.9), Inches(1.72), cd)
    ch = gf.chart
    ch.has_title = False
    ch.has_legend = False
    ch.font.size = Pt(8.5)
    ch.font.name = "微软雅黑"
    plot = ch.plots[0]
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(9)
    plot.data_labels.number_format = '0.00"%"'
    plot.data_labels.number_format_is_linked = False
    plot.gap_width = 40
    plot.series[0].format.fill.solid()
    plot.series[0].format.fill.fore_color.rgb = RGBColor(0x8F, 0xB8, 0xD8)
    va = ch.value_axis
    va.visible = False
    va.has_major_gridlines = False
    va.maximum_scale = 24
    ch.category_axis.tick_labels.font.size = Pt(8.5)
    ch.category_axis.format.line.fill.background()

    label(s, 6.5, 1.58, "结论：不上线")
    rect(s, 6.5, 1.9, 5.9, 1.5, fill=RGBColor(0xFD, 0xF2, 0xE9))
    text(s, 6.7, 2.0, 5.5, 0.24, "赢朴素基线，但输给常数基线", 10, True, ORANGE)
    text(s, 6.7, 2.26, 5.55, 1.02,
         "线性回归 MAPE 12.72%，比“昨天=今天”好 36.7%；但常数基线的 12.11% 更低，"
         "6 折回测两者 MAE 相差不到 0.7%。", 9.6, False, INK, line=1.4)

    label(s, 6.5, 3.56, "为什么")
    text(s, 6.5, 3.84, 5.9, 1.9,
         "这条序列接近平稳：日均 GMV 的变异系数只有 0.187，没有趋势项。\n"
         "没有趋势时，“预测均值”本身就是很难被打败的基线。\n"
         "与其硬套一个会退化成均值的复杂模型，不如把均值作为显式基线。", 10, False, GRAY,
         line=1.5)
    progress(s, 8)
    note(s, "【4:25–4:55】第八步做预测。五步：取数、造特征、按时间切分、三个模型对照、六折回测。"
            "重点是第三步“按时间切，不随机打乱”——时间序列随机切会泄露未来信息，分数会虚高。"
            "结果很诚实：线性回归 12.72%，比朴素基线好，但常数基线是 12.11%，比模型还低。"
            "原因是这条序列接近平稳，CV 只有 0.187。所以结论是不上线。")


def s12_nl2sql(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 9, "让不会写 SQL 的人，用中文问出数字", 12)
    label(s, M, 1.58, "四步链路")
    chain = [("① 提问", "中文业务问题\n如“各省销售额排名”"), ("② 生成 SQL", "模型读表结构\n只生成 SELECT"),
             ("③ 校验", "guard_sql 四条规则\n不合格直接拒绝"), ("④ 执行", "Hive 只读执行\n表格 + 图")]
    x = M
    for i, (name, desc) in enumerate(chain):
        rect(s, x, 1.9, 2.6, 1.16, fill=SOFT, line_color=LINE)
        text(s, x + 0.16, 1.98, 2.3, 0.24, name, 10.5, True, NAVY)
        text(s, x + 0.16, 2.28, 2.34, 0.7, desc, 9, False, GRAY, line=1.4)
        if i < 3:
            text(s, x + 2.66, 2.36, 0.24, 0.24, "›", 15, True, SKY)
        x += 2.9

    label(s, M, 3.24, "四条硬规则（应用层的安全边界）")
    rules = [("只读开头", "必须以 SELECT / WITH 开头，其他一律拒绝"),
             ("禁止写操作", "insert / update / delete / drop / alter 全部拦截"),
             ("必须带库名", "防止落到 default 库，也便于审计"),
             ("自动加 LIMIT", "最多返回 200 行，避免误拉全表")]
    y = 3.54
    for t, d in rules:
        text(s, M, y, 0.24, 0.24, "✓", 10.5, True, BLUE)
        text(s, M + 0.3, y, 1.4, 0.24, t, 9.8, True, NAVY)
        text(s, M + 1.75, y, 4.5, 0.22, d, 9, False, GRAY)
        y += 0.4

    pitfall(s, 5.3, "踩过的坑",
            "一次问“12 月各支付方式占比”，微信算成 2.43%、四个数合计 9.4%——"
            "示例 SQL 里把分母写死成全年常数，模型照抄。改成窗口函数现算当月分母，并加硬约束。")
    progress(s, 9)
    note(s, "【4:55–5:25】第九步 NL2SQL。四步：提问、生成 SQL、校验、执行。"
            "关键是第三步：模型生成的东西不能直接跑，所以加了四条规则——只读、禁写、必须带库名、自动加 LIMIT。"
            "这里也踩过坑：问“12 月各支付方式占比”，微信被算成 2.43%，四个数加起来才 9.4%，"
            "因为示例里分母写死成全年。改成窗口函数现算当月分母才对。")


def s13_viz(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 10, "同一份指标，三种看法：管理、展厅、自助", 13)
    label(s, M, 1.58, "三端各解决一类人的问题")
    ends = [("Superset 仪表板", "管理者", "6 图 + 3 筛选器 + 交叉联动；全部用 REST API 自动建，可重跑"),
            ("ECharts 数据大屏", "展厅 / 汇报", "7 类图，1920×1080 设计 + overall 缩放；资源本地化，断网可演示"),
            ("Streamlit 问答", "业务方自助", "提问 → SQL → 表格 → 图；含历史、错误提示、CSV 下载")]
    y = 1.9
    for name, who, desc in ends:
        rect(s, M, y, 6.6, 1.06, fill=SOFT)
        text(s, M + 0.18, y + 0.1, 3.4, 0.26, name, 10.8, True, NAVY)
        text(s, M + 3.7, y + 0.12, 1.0, 0.22, who, 8.8, False, ORANGE)
        text(s, M + 0.18, y + 0.42, 6.2, 0.5, desc, 9.2, False, GRAY, line=1.4)
        y += 1.18

    label(s, 7.5, 1.58, "三个“不做就会翻车”的细节")
    details = [("图表怎么来的", "Superset 用 API 建 2 数据源 / 8 数据集 / 6 图表，bootstrap 幂等重跑"),
               ("断网怎么办", "echarts.min.js 与中国地图 json 放本地；接口挂了回落 snapshot.json"),
               ("8000 挂了怎么办", "数据服务带 10 秒缓存 + ClickHouse 副本，Hive 慢也不影响大屏")]
    y = 1.9
    for t, d in details:
        text(s, 7.5, y, 4.9, 0.24, t, 9.8, True, BLUE)
        text(s, 7.5, y + 0.24, 4.9, 0.52, d, 9, False, GRAY, line=1.4)
        y += 0.9

    pitfall(s, 5.52, "最花时间的一处",
            "Superset 用 API 建仪表板时，图表建好了但面板全显示“图表已删除”——"
            "原因是图表与仪表板的关联表没写进去，最后改用模型层写 dashboard_slices 才通。")
    progress(s, 10)
    note(s, "【5:25–5:50】第十步可视化。三端对应三类人：管理者看仪表板，展厅看大屏，业务方自助问答。"
            "下面三个细节都是“不做就翻车”的：图表是 API 自动建的，可以重跑；"
            "大屏资源本地化，断网也能演示；接口挂了有快照兜底，不会白屏。"
            "最花时间的是 Superset 那个坑——图表建好了但面板显示“已删除”，"
            "因为关联表没写，最后用模型层补进去才通。")


def s14_deploy(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 11, "九个服务，一条命令，顺序由健康检查兜住", 14)
    label(s, M, 1.58, "启动顺序（不是写着好看）")
    row1 = [("mysql", "元数据库"), ("mysql-init", "一次性建库"), ("hive-metastore", "元数据服务"),
            ("hive-server", "HiveServer2")]
    x = M
    for i, (n, d) in enumerate(row1):
        rect(s, x, 1.9, 1.98, 0.74, fill=BLUE)
        text(s, x + 0.12, 1.98, 1.8, 0.24, n, 9.6, True, WHITE)
        text(s, x + 0.12, 2.24, 1.8, 0.22, d, 8.4, False, RGBColor(0xDD, 0xE8, 0xF2))
        if i < 3:
            text(s, x + 2.0, 2.16, 0.2, 0.24, "›", 14, True, RGBColor(0xB6, 0xC5, 0xD3))
        x += 2.2
    row2 = [("clickhouse", "服务层缓存"), ("superset", "BI 仪表板"), ("superset-init", "一次性建看板"),
            ("api", "数据服务"), ("app", "Streamlit 问答")]
    x = M
    for i, (n, d) in enumerate(row2):
        rect(s, x, 2.82, 1.98, 0.74, fill=NAVY)
        text(s, x + 0.12, 2.9, 1.8, 0.24, n, 9.6, True, WHITE)
        text(s, x + 0.12, 3.16, 1.8, 0.22, d, 8.4, False, RGBColor(0xC8, 0xD6, 0xE3))
        if i < 4:
            text(s, x + 2.0, 3.08, 0.2, 0.24, "›", 14, True, RGBColor(0xB6, 0xC5, 0xD3))
        x += 2.2

    text(s, M, 3.72, 8.4, 0.24,
         "7 个常驻 + 2 个一次性任务 = 9 个服务；Hive 冷启动 60～120 秒，抢跑就会重启循环",
         10, False, GRAY)

    label(s, M, 4.06, "为什么能“一条命令”")
    bullets_y = 4.34
    items = [("healthcheck 定顺序", "depends_on 只保证“起来了”，healthcheck 才保证“能用了”"),
             ("密钥走 .env", "仓库里只有占位符模板，`git status` 看不到真实 Key"),
             ("两个一次性任务", "mysql-init 建库、superset-init 建看板；Exited(0) 才是正常")]
    for t, d in items:
        text(s, M, bullets_y, 1.9, 0.24, t, 9.6, True, NAVY)
        text(s, M + 2.0, bullets_y, 5.6, 0.22, d, 9, False, GRAY)
        bullets_y += 0.42

    rect(s, 8.5, 4.06, 3.9, 1.72, fill=SOFT)
    text(s, 8.68, 4.16, 3.6, 0.24, "命令就一句", 9.6, True, BLUE)
    text(s, 8.68, 4.42, 3.6, 0.3, "docker compose up -d", 12, True, NAVY)
    text(s, 8.68, 4.78, 3.6, 0.9,
         "期望：7 个 healthy + 2 个 Exited(0)。\n停止用 down，不加 -v 就不会丢数据。", 8.8, False,
         GRAY, line=1.45)
    progress(s, 11)
    note(s, "【5:50–6:15】第十一步部署。九个服务，七个常驻加两个一次性任务。"
            "上面一行是基础设施，下面一行是应用与展示。"
            "为什么能一条命令起来？靠的是健康检查定顺序——depends_on 只保证容器起来了，"
            "healthcheck 才保证它真的能用了。Hive 冷启动要一到两分钟，抢跑就会进重启循环。")


def s15_integration(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 12, "收口：39 项核对，修掉 6 个“文档与实际不一致”", 15)
    label(s, M, 1.58, "怎么核对")
    text(s, M, 1.86, 4.3, 1.5,
         "不看图、看数：按数据流向逐层对，\n"
         "每一层给出“期望值 + 实测值 + 判定”。\n"
         "写成脚本，可重复跑。", 10.8, False, INK, line=1.5)
    out_card(s, M, 3.3, 4.3, 1.9, [
        ("39 / 39", "项核对全部通过（约 150 秒）"),
        ("114,809 → 111,037", "逐层行数都对得上"),
    ])

    label(s, 5.2, 1.58, "修掉的 6 个问题")
    rows = [["#", "问题", "实际情况"],
            ["1", "服务数写 8 个", "compose 里是 9 个（漏算 mysql-init）"],
            ["2", "剔除率 3.28%", "3,772 / 114,809 = 3.29%"],
            ["3", "门店第一 132 万", "按 store_id 是 70.8 万（同名被合并）"],
            ["4", "周表 208 行", "53 周 × 4 渠道 = 212 行"],
            ["5", "第 5 周脚本容器内不可见", "compose 没挂载第 5 周目录"],
            ["6", "一次性任务被判失败", "退出后 health 残留 unhealthy"]]
    table(s, 5.2, 1.88, 7.2, rows, [0.07, 0.34, 0.59], size=9.2, row_h=0.42, head_h=0.3)

    rect(s, M, 5.4, CW, 0.92, fill=SOFT)
    text(s, M + 0.2, 5.5, CW - 0.4, 0.24,
         "第 5 周真正的价值，不是多做功能，而是把前四周的“两套说法”统一成一套", 10, True, BLUE)
    text(s, M + 0.2, 5.76, CW - 0.4, 0.46,
         "同时补齐五篇文档（需求 / 清洗 / 架构 / 部署 + API）、英文 README、Git 分支与 PR 记录。",
         10.5, False, INK, line=1.4)
    progress(s, 12)
    note(s, "【6:15–6:45】最后一步收口。方法是写一个脚本，按数据流向逐层核对 39 项，"
            "每项都给期望值、实测值和判定。跑下来全过，但过程中发现 6 个问题——"
            "有四个是“文档与实际不一致”：服务数、剔除率、门店排名、周数。"
            "所以我理解的第五周不是继续加功能，而是把前四周的两种说法统一成一种。")


def s16_review(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, M, 0.48, 0.055, 0.2, fill=BLUE)
    text(s, M + 0.16, 0.45, 6.0, 0.24, "复盘", 10.5, True, BLUE)
    text(s, W - M - 0.8, 0.48, 0.8, 0.24, "16", 10, False, GRAY, align=PP_ALIGN.RIGHT)
    text(s, M, 0.76, CW, 0.6, "五个坑，五条经验，一条总结", 24, True, NAVY)

    rows = [["坑", "当时的现象", "怎么解的"],
            ["日期建成 date", "脏日期变 NULL，脏数据“消失”", "全字段 string，先接住再转"],
            ["金额阈值用 P99", "上限被抬到 551 万，脏数据被当正常", "改用 IQR，落在金额断崖上"],
            ["明细直接算占比", "品类加起来不等于 100%", "造 alloc_amount 分摊字段"],
            ["Superset 用 API 建板", "面板全显示“图表已删除”", "模型层写 dashboard_slices"],
            ["子串截取做分区条件", "比全表还慢（15.89 秒）", "用分区列 order_month（2.58 秒）"]]
    table(s, M, 1.6, 7.6, rows, [0.26, 0.38, 0.36], size=9.4, row_h=0.52, head_h=0.32)

    rect(s, 8.7, 1.6, 3.7, 2.5, fill=SOFT)
    text(s, 8.88, 1.7, 3.4, 0.24, "三条经验", 9.8, True, BLUE)
    tips = ["先让问题可见，再修问题", "阈值要用数据自己验证", "能解释的差异才允许存在"]
    y = 2.0
    for i, t in enumerate(tips, 1):
        text(s, 8.88, y, 0.3, 0.24, f"0{i}", 9.6, True, SKY)
        text(s, 9.2, y, 3.0, 0.58, t, 9.6, False, INK, line=1.35)
        y += 0.66

    rect(s, 8.7, 4.28, 3.7, 1.9, fill=NAVY)
    text(s, 8.9, 4.4, 3.3, 0.24, "谢谢，请老师提问", 12, True, WHITE)
    text(s, 8.9, 4.72, 3.35, 1.3,
         "演示环境已就绪\n仓库 github.com/yuyu52525/xmsx\n任一数字可现场跑命令回到源头", 8.6, False,
         RGBColor(0xC8, 0xD6, 0xE3), line=1.6)

    text(s, M, 5.5, 7.6, 0.9,
         "一句话总结：这套系统的价值不在“做了多少图”，而在于每个数字都能沿着"
         "“CSV → ODS → DWD → DWS → ADS → 图”这条路走回它的原始字段。", 10.2, False, GRAY,
         line=1.5)
    note(s, "【6:45–7:10】最后复盘五个坑。它们有个共同点：都不是“不会写”，而是“想当然”——"
            "日期想当然用 date、阈值想当然用 P99、占比想当然用原价、分区想当然用 substr。"
            "所以三条经验都是同一件事：先让问题可见，再用数据验证，最后只接受能解释的差异。"
            "我的汇报到这里，谢谢老师。")


def build() -> Path:
    from pptx import Presentation
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    for fn in (s01_cover, s02_pipeline, s03_map, s04_env, s05_ods, s06_quality,
               s07_clean, s08_dwd, s09_dws, s10_ads, s11_forecast, s12_nl2sql,
               s13_viz, s14_deploy, s15_integration, s16_review):
        fn(prs)
    prs.core_properties.title = "云购生活数仓 · 答辩（过程版）"
    prs.core_properties.author = "余天乐"
    prs.core_properties.subject = "12 步走完一条数据流水线"
    prs.save(str(OUT))
    return OUT


if __name__ == "__main__":
    print(build())