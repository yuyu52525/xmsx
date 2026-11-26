"""第 5 周 · 答辩 PPT（过程版 v2）生成脚本 —— 17 页

v2 相比 v1 的四个改动：
  1. 内容加厚：每个步骤页由 3 条做法改为 3～4 条，产出卡补到 3～4 项
  2. 标注归属：每页页眉写明"大任务几 · 第几周任务书 · 哪个子任务"
  3. 增加"现场可展示"：每页底部写明这一刻该打开哪个网址 / 哪个文件 / 跑哪条命令
  4. 取消复盘页：遇到的问题不再每页讲，统一收到倒数第二页做索引，只提一句

标题全部改为名词性正式表述（如"五类脏数据的识别与治理"），不用口语化句式。

用法：python build_pptx_process.py
输出：../docs/答辩PPT_第5周_过程版.pptx
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pptx.chart.data import CategoryChartData            # noqa: E402
from pptx.dml.color import RGBColor                      # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE                # noqa: E402
from pptx.enum.shapes import MSO_SHAPE                   # noqa: E402
from pptx.enum.text import PP_ALIGN                      # noqa: E402
from pptx.util import Inches, Pt                         # noqa: E402

from build_pptx import (                                 # noqa: E402
    W, H, M, CW, NAVY, INK, BLUE, SKY, ORANGE, GRAY, LINE, SOFT, WHITE,
    text, rect, table, note,
)

DOCS = HERE.parent / "docs"
OUT = DOCS / "答辩PPT_第5周_过程版.pptx"

TOTAL_STEPS = 12
STEPS = ["搭环境", "导入 ODS", "质量评估", "数据清洗", "建 DWD", "建 DWS",
         "建 ADS", "做预测", "NL2SQL", "可视化", "部署", "联调收口"]

# 步骤 → (大任务, 任务书位置, 正式标题)
META = {
    1: ("大任务一 · 数据接入与质量治理", "第 1 周任务书 · 子任务 2 环境搭建",
        "开发环境搭建与服务就绪"),
    2: ("大任务一 · 数据接入与质量治理", "第 1 周任务书 · 子任务 4 数据导入 ODS",
        "原始数据接入 ODS 贴源层"),
    3: ("大任务一 · 数据接入与质量治理", "第 1 周任务书 · 子任务 5 质量预评估",
        "五维度数据质量预评估"),
    4: ("大任务一 · 数据接入与质量治理", "第 1–2 周任务书 · 子任务 6/7 与 2-1/2-2",
        "五类脏数据的识别与治理"),
    5: ("大任务二 · 四层数仓建模", "第 2 周任务书 · 子任务 5 四层架构与 DWD",
        "DWD 明细层与星型模型建设"),
    6: ("大任务二 · 四层数仓建模", "第 3 周任务书 · 子任务 1 DWS/ADS 与 KPI",
        "DWS 汇总层多粒度预聚合"),
    7: ("大任务二 · 四层数仓建模", "第 3 周任务书 · 子任务 1 DWS/ADS 与 KPI",
        "ADS 应用层与 KPI 指标体系"),
    8: ("大任务三 · 分析与 AI 能力", "第 3 周任务书 · 子任务 2 预测建模",
        "GMV 时间序列预测与基线对照"),
    9: ("大任务三 · 分析与 AI 能力", "第 3 周任务书 · 子任务 3/4 大模型接入与 NL2SQL",
        "NL2SQL 自然语言取数链路"),
    10: ("大任务四 · 可视化交付与集成", "第 4 周任务书 · 子任务 1/2/3 三端可视化",
         "三端可视化应用建设"),
    11: ("大任务四 · 可视化交付与集成", "第 4 周任务书 · 子任务 4 Compose 部署",
         "Docker Compose 多服务编排部署"),
    12: ("大任务四 · 可视化交付与集成", "第 5 周任务书 · 子任务 1/2/3 联调与文档",
         "端到端联调与交付物收口"),
}

# 步骤 → 现场可展示（网址 / 文件 / 命令）
DEMO = {
    1: "命令　docker compose ps　（期望 7 个 healthy + 2 个 Exited）　　文件　第1周/docs/环境搭建笔记.md",
    2: "查询　容器内 select count(*) 六表合计 114,809　　目录　第1周/evidence/（建表与加载输出）",
    3: "文件　第1周/docs/数据质量预评估表.xlsx（五维度、逐字段）",
    4: "文件　第2周/docs/数据质量对比报告.docx（修复率表 + 三类策略）",
    5: "查询　describe formatted ydsh_dwd.dwd_order（12 分区 / 8 桶）　　文件　第2周/docs/数仓架构设计文档.docx",
    6: "查询　select sum(gmv) from ydsh_dws.dws_sales_month　→ 36,116,687.06　　文件　第3周/docs/DWS-ADS层建模与KPI口径说明.docx",
    7: "网址　http://localhost:8000/ 顶部指标卡　　网址　http://localhost:8088/ 仪表板指标卡",
    8: "文件　第3周/docs/预测建模分析报告.docx（MAPE / MBE / 三模型对比图）",
    9: "网址　http://localhost:8501/ 提问「各支付方式的销售额占比是多少？」",
    10: "网址　8000 大屏　·　8088 仪表板　·　8501 问答　（三个入口依次演示）",
    11: "命令　docker compose up -d　　文件　第5周/docs/部署手册.docx（9 服务 + 20 条常见问题）",
    12: "命令　python 第5周/py/e2e_verify.py　　文件　第5周/evidence/e2e_verify.txt（39 项）",
}


# ------------------------------------------------------------------ 组件
def progress(s, current: int) -> None:
    bw, gap = 0.86, 0.1
    x = M
    for i in range(1, TOTAL_STEPS + 1):
        fill = NAVY if i == current else (SKY if i < current else LINE)
        rect(s, x, 6.62, bw, 0.07, fill=fill)
        x += bw + gap


def head(s, step: int, page: int) -> None:
    """页眉：步骤徽标 + 大任务 + 任务书位置 + 正式标题 + 页码。"""
    big, where, title = META[step]
    rect(s, M, 0.42, 1.22, 0.38, fill=NAVY)
    text(s, M, 0.48, 1.22, 0.22, f"步骤 {step:02d}", 9.8, True, WHITE, align=PP_ALIGN.CENTER)
    text(s, M + 1.36, 0.47, 4.6, 0.24, big, 10.2, True, BLUE)
    text(s, 7.0, 0.48, 5.0, 0.22, where, 8.8, False, GRAY, align=PP_ALIGN.RIGHT)
    text(s, W - M - 0.55, 0.47, 0.55, 0.22, f"{page:02d}", 9.5, False, GRAY, align=PP_ALIGN.RIGHT)
    text(s, M, 0.92, CW, 0.58, title, 24, True, NAVY, line=1.15)


def label(s, x, y, txt: str, color=BLUE, w: float = 4.0) -> None:
    rect(s, x, y + 0.03, 0.055, 0.15, fill=color)
    text(s, x + 0.13, y, w, 0.2, txt, 9.6, True, color)


def actions(s, x, y, w, items: list[tuple[str, str]], size: float = 10.6) -> float:
    cy = y
    for i, (t, d) in enumerate(items, 1):
        rect(s, x, cy + 0.02, 0.26, 0.26, fill=BLUE, shape=MSO_SHAPE.OVAL)
        text(s, x, cy + 0.05, 0.26, 0.2, str(i), 8.8, True, WHITE, align=PP_ALIGN.CENTER)
        text(s, x + 0.36, cy - 0.02, w - 0.36, 0.22, t, size, True, NAVY)
        text(s, x + 0.36, cy + 0.24, w - 0.36, 0.24, d, size - 2.0, False, GRAY, line=1.3)
        cy += 0.84
    return cy - y


def out_card(s, x, y, w, h, items: list[tuple[str, str]], step: float = 0.52) -> None:
    rect(s, x, y, w, h, fill=SOFT)
    cy = y + 0.14
    for v, l in items:
        text(s, x + 0.16, cy, w - 0.28, 0.28, v, 15, True, BLUE, line=1.0)
        text(s, x + 0.16, cy + 0.27, w - 0.28, 0.2, l, 8.8, False, GRAY)
        cy += step


def demo(s, txt: str) -> None:
    """底部“现场可展示”条：说到这一步，打开什么。"""
    rect(s, M, 5.44, CW, 0.76, fill=RGBColor(0xE8, 0xF1, 0xF9))
    rect(s, M, 5.44, 0.05, 0.76, fill=BLUE)
    text(s, M + 0.18, 5.52, 1.3, 0.22, "现场可展示", 9.4, True, BLUE)
    text(s, M + 1.42, 5.52, CW - 1.6, 0.6, txt, 9.6, False, INK, line=1.4)


def plain_head(s, kicker: str, title: str, page: int, total: int = 17) -> None:
    rect(s, M, 0.5, 0.055, 0.2, fill=BLUE)
    text(s, M + 0.16, 0.47, 6.0, 0.22, kicker, 10.2, True, BLUE)
    text(s, W - M - 0.55, 0.47, 0.55, 0.22, f"{page:02d}", 9.5, False, GRAY,
         align=PP_ALIGN.RIGHT)
    text(s, M, 0.9, CW, 0.58, title, 24, True, NAVY, line=1.15)


def footer(s) -> None:
    rect(s, M, 7.04, CW, 0.008, fill=LINE)
    text(s, M, 7.12, 6.4, 0.2, "云购生活数仓 · 第 5 周综合答辩", 8.6, False, GRAY)
    text(s, W - M - 2.4, 7.12, 2.4, 0.2, "余天乐 · 20230308098", 8.6, False, GRAY,
         align=PP_ALIGN.RIGHT)


# ------------------------------------------------------------------ 1 封面
def s01(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, W, H, fill=NAVY)
    rect(s, 9.3, -1.9, 6.4, 6.4, fill=BLUE, shape=MSO_SHAPE.OVAL, alpha=20)
    rect(s, 11.2, 4.6, 3.2, 3.2, fill=SKY, shape=MSO_SHAPE.OVAL, alpha=12)
    text(s, M, 1.36, 8.8, 0.28, "企业项目实战实训 · 第 5 周综合答辩", 12, True, SKY)
    text(s, M, 1.8, 9.6, 0.86, "从 6 张 CSV", 44, True, WHITE, line=1.05)
    text(s, M, 2.6, 9.6, 0.86, "到 3 个终端", 44, True, WHITE, line=1.05)
    rect(s, M, 3.66, 1.5, 0.045, fill=ORANGE)
    text(s, M, 3.86, 9.4, 0.66,
         "12 个实施步骤，对应五周任务书的 20 个子任务；每一步说明做什么、产出什么、可现场展示什么",
         13.5, False, RGBColor(0xBF, 0xCF, 0xDD), line=1.4)
    items = [("12", "个步骤"), ("20", "个子任务"), ("51", "张数仓表"), ("9", "个容器服务")]
    x = M
    for i, (v, l) in enumerate(items):
        text(s, x, 4.86, 1.9, 0.4, v, 24, True, SKY, line=1.0)
        text(s, x, 5.28, 1.95, 0.22, l, 9.6, False, RGBColor(0x9F, 0xB3, 0xC6))
        if i < 3:
            rect(s, x + 1.62, 4.9, 0.008, 0.46, fill=RGBColor(0x2E, 0x4A, 0x66))
        x += 2.16
    text(s, M, 5.96, 9.2, 0.72,
         "四层数仓 ODS → DWD → DWS → ADS　·　指标体系　·　预测与 NL2SQL　·　Superset / ECharts / Streamlit　·　Docker 一键部署",
         10.4, False, RGBColor(0x9F, 0xB3, 0xC6), line=1.5)
    text(s, M, 6.78, 9.0, 0.22, "余天乐　20230308098　·　数据科学与大数据技术　·　团队 乐天",
         9.6, False, RGBColor(0x8F, 0xA6, 0xBA))
    note(s, "【0:00–0:20】各位老师好，我是余天乐。今天按实施过程汇报：这条流水线分成 12 个步骤，"
            "正好覆盖五周任务书的 20 个子任务。每一步我会说三件事——做什么、产出什么、"
            "以及这一步能现场展示什么，需要的话我随时切过去。")


# ------------------------------------------------------------------ 2 路线图
def s02(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    plain_head(s, "实施路线", "总体实施路线：四个大任务、十二个步骤", 2)
    phases = [("大任务一", "数据接入与质量治理", "第 1–2 周", [1, 2, 3, 4], SKY),
              ("大任务二", "四层数仓建模", "第 2–3 周", [5, 6, 7], BLUE),
              ("大任务三", "分析与 AI 能力", "第 3 周", [8, 9], NAVY),
              ("大任务四", "可视化交付与集成", "第 4–5 周", [10, 11, 12], RGBColor(0x2A, 0x4A, 0x6B))]
    x = M
    for name, desc, week, steps, col in phases:
        rect(s, x, 1.6, 2.86, 0.28, fill=col)
        text(s, x + 0.12, 1.63, 2.6, 0.22, f"{name}　{week}", 9.2, True, WHITE)
        text(s, x, 1.96, 2.8, 0.24, desc, 10.4, True, NAVY)
        y = 2.28
        for st in steps:
            rect(s, x, y, 2.86, 0.52, fill=SOFT, line_color=LINE)
            text(s, x + 0.12, y + 0.05, 0.46, 0.2, f"{st:02d}", 9, True, col)
            text(s, x + 0.58, y + 0.05, 2.2, 0.2, STEPS[st - 1], 9.4, True, INK)
            y += 0.6
        x += 3.03

    rect(s, M, 5.1, CW, 1.16, fill=SOFT)
    text(s, M + 0.2, 5.2, CW - 0.4, 0.22, "读法", 9.6, True, BLUE)
    text(s, M + 0.2, 5.46, CW - 0.4, 0.7,
         "前四步把脏数据变成可算的数据；第五到七步把它组织成能复用的数仓；"
         "第八、九步在数仓上做预测与问答；最后三步把成果交付成别人能用的系统。"
         "每页页眉都标了所在的大任务与任务书位置，便于对照。", 10, False, INK, line=1.45)
    footer(s)
    note(s, "【0:20–0:50】先看路线。四个大任务：数据接入与治理、四层建模、分析与 AI、可视化交付。"
            "十二个步骤分布在这四段里，对应五周的任务书。"
            "后面每一页的页眉都会写清楚：现在在第几步、属于哪个大任务、对应第几周任务书的哪个子任务。")


# ------------------------------------------------------------------ 3 对照表
def s03(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    plain_head(s, "任务书对照", "任务书要求与本项目实施步骤的对应关系", 3)
    rows = [["周次", "任务书主题", "主要子任务", "步骤"],
            ["第 1 周", "环境 · Git · 导入 · 清洗（一）", "环境搭建、Git 规范、ODS 六表、五维预评估、缺失与重复清洗", "1–4"],
            ["第 2 周", "清洗（二）· 四层建模 · 探索分析", "枚举标准化、异常值与格式、拆分合并、四层架构与 DWD、EDA", "4–5"],
            ["第 3 周", "DWS/ADS · 预测 · AI 协同", "DWS 九表、ADS 九表、KPI、预测建模、NL2SQL、AI 洞察", "6–9"],
            ["第 4 周", "可视化 · 部署", "Superset、ECharts 大屏、Streamlit、Compose 部署、压测优化", "10–11"],
            ["第 5 周", "整合 · 文档 · 答辩", "端到端联调、五篇文档、Git 审查、英文 README、答辩", "12"]]
    table(s, M, 1.58, CW, rows, [0.11, 0.27, 0.48, 0.14], size=9.8, row_h=0.62, head_h=0.34)

    rect(s, M, 5.06, 5.9, 1.2, fill=SOFT)
    text(s, M + 0.18, 5.16, 5.5, 0.22, "为什么要有这张表", 9.4, True, BLUE)
    text(s, M + 0.18, 5.4, 5.55, 0.76,
         "每周收尾时逐项核对，防止漏做——第 5 周就是靠它发现第 4 周的 Git 分支记录缺失。", 9.4,
         False, INK, line=1.4)
    rect(s, 6.86, 5.06, 5.75, 1.2, fill=SOFT)
    text(s, 7.04, 5.16, 5.4, 0.22, "子任务完成情况", 9.4, True, BLUE)
    text(s, 7.04, 5.4, 5.45, 0.76,
         "20 个子任务中 17 个有可验证产物，3 个为过程性要求（分工、表达、协作记录），均已在文档中留痕。",
         9.4, False, INK, line=1.4)
    footer(s)
    note(s, "【0:50–1:15】这张表是任务书与实施步骤的对照。它的实际用途是防漏：每周收尾对一遍。"
            "20 个子任务里 17 个有可验证的产物，3 个是过程性要求，都已经在文档里留痕。"
            "下面进入具体步骤。")


# ------------------------------------------------------------------ 步骤页
def s04(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 1, 4)
    label(s, M, 1.62, "本步目标")
    text(s, M, 1.86, 4.2, 1.0,
         "六张 CSV 还没有任何服务能读。先把运行环境搭起来：Docker、Hive 4.0.0、MySQL 8.0、Git。",
         10.4, False, INK, line=1.45)
    label(s, M, 2.92, "产出")
    out_card(s, M, 3.18, 4.2, 2.1, [
        ("Hive 4.0.0", "beeline 可连，show databases 正常"),
        ("MySQL 8.0", "承载 metastore 元数据"),
        ("8 条环境问题", "每条含现象、原因、解法"),
        ("Git 仓库", "含 .gitignore 与首次推送"),
    ])
    label(s, 5.2, 1.62, "实施要点")
    actions(s, 5.2, 1.9, 7.2, [
        ("安装 Docker Desktop 与 WSL2", "确认 docker ps 有输出、引擎版本可用，才算环境通了"),
        ("按依赖顺序启动 MySQL 与 Hive", "metastore 依赖 MySQL，hive-server 依赖 metastore，不能并行抢跑"),
        ("beeline 连通性验证", "show databases、建库建表各跑一次，确认不是“起得来但用不了”"),
        ("记录问题与解法", "端口冲突、驱动缺失、WSL 未更新等 8 条，写进环境笔记备查"),
    ])
    demo(s, DEMO[1])
    progress(s, 1)
    footer(s)
    note(s, "【1:15–1:40】第一步搭环境。四件事：装 Docker、按依赖顺序起 MySQL 和 Hive、"
            "用 beeline 验证真的能查、把 8 个问题记下来。"
            "这一步的产出不是数据，是一份能让别人复现的环境笔记。")


def s05(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 2, 5)
    label(s, M, 1.62, "本步目标")
    text(s, M, 1.86, 4.2, 1.0,
         "把外部文件变成能用 SQL 查询的表。原则是贴源：脏数据一起进来，先看清原样再治理。",
         10.4, False, INK, line=1.45)
    label(s, M, 2.92, "产出")
    out_card(s, M, 3.18, 4.2, 2.1, [
        ("6 张 ODS 表", "user / product / store / order / item / behavior"),
        ("114,809 行", "与数据字典逐表核对一致"),
        ("2 个脚本", "create_ods.sql、load_ods.sql"),
        ("全字段 string", "脏值不会被静默转成 NULL"),
    ])
    label(s, 5.2, 1.62, "实施要点")
    actions(s, 5.2, 1.9, 7.2, [
        ("建 6 张外部表，TEXTFILE 逗号分隔", "字段统一 string，先接住再转型，避免导入阶段丢信息"),
        ("加载时跳过表头", "tblproperties('skip.header.line.count'='1')，否则首行会变成数据"),
        ("逐表 count(*) 与字典核对", "六表分别核对，合计 114,809 行才算成功"),
        ("保留脏数据不做处理", "ODS 只做搬运；清洗在 DWD 阶段做，保证原始层可回溯"),
    ])
    demo(s, DEMO[2])
    progress(s, 2)
    footer(s)
    note(s, "【1:40–2:05】第二步导入。关键决定是全字段 string。"
            "我第一版把日期建成 date，脏日期导入后变成 NULL，问题被藏起来了；改成 string 才暴露。"
            "所以贴源层不做任何加工，是为了让问题可见。")


def s06(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 3, 6)
    label(s, M, 1.62, "本步目标")
    text(s, M, 1.86, 4.2, 0.86,
         "不凭感觉删数据。先按五个维度全量扫描，把问题变成可统计的数字，后面的清洗才有依据。",
         10.4, False, INK, line=1.45)
    label(s, M, 2.82, "扫描结果：72,156 条问题")
    dims = [("完整性", "255", "空值率"), ("唯一性", "600", "主键重复"),
            ("有效性", "60,520", "枚举取值"), ("一致性", "8,217", "格式统一"),
            ("准确性", "2,564", "取值合理")]
    y = 3.12
    for name, v, note_ in dims:
        text(s, M, y, 0.9, 0.22, name, 9.4, True, NAVY)
        text(s, M + 0.92, y, 1.0, 0.22, v, 10.2, True, ORANGE)
        text(s, M + 2.0, y, 2.1, 0.22, note_, 8.6, False, GRAY)
        y += 0.34
    label(s, 5.2, 1.62, "实施要点")
    actions(s, 5.2, 1.9, 7.2, [
        ("枚举字段先 select distinct", "把 6～16 种写法全部列出再写映射，漏一个值就会多出一组错误分类"),
        ("数值字段看分布而非只看阈值", "分位数、箱线图、直方图一起看：异常值占 3.8%，P99 已被污染"),
        ("重复要区分整行重复与同号异构", "整行相同 400 条、同号不同字段 200 条，处理方式不同"),
        ("结果落成预评估表", "每字段问题数、样例值、建议处理方式，一张表交代清楚"),
    ])
    demo(s, DEMO[3])
    progress(s, 3)
    footer(s)
    note(s, "【2:05–2:30】第三步评估。目标不是改数据，是把问题数字化。"
            "五维度扫出 72156 条，其中六成是枚举写法不统一。"
            "这里也发现重复有两种：整行重复和同号不同字段，后者如果只按整行去重会漏 200 条。")


def s07(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 4, 7)
    label(s, M, 1.58, "本步目标与结果")
    text(s, M, 1.82, 4.2, 0.62,
         "把 72,156 条问题按五类分别处理，每一行变动都能指到规则。", 10.2, False, INK, line=1.4)
    text(s, M, 2.44, 2.0, 0.3, "114,809", 17, True, NAVY, line=1.0)
    text(s, M + 1.96, 2.5, 0.4, 0.22, "→", 11, True, GRAY)
    text(s, M + 2.36, 2.44, 1.9, 0.3, "111,037", 17, True, BLUE, line=1.0)
    rect(s, M, 2.82, 4.0, 0.09, fill=RGBColor(0xC9, 0xD6, 0xE2))
    rect(s, M, 2.82, 4.0 * 0.9671, 0.09, fill=BLUE)
    text(s, M, 2.98, 4.2, 0.22, "剔除 3,772 行（3.29%）", 8.8, False, GRAY)

    rows = [["五类", "处理方式", "条数"],
            ["缺失", "年龄均值填、邮箱标记、日期按类目补", "255"],
            ["重复", "含同号异构，按 order_id 取一条", "600"],
            ["格式", "日期 / 手机号 / 时间统一写法", "8,217"],
            ["异常", "金额按 IQR 删、单价按中位数修", "2,564"],
            ["枚举", "映射到中文标准值（如 8 种→3 种）", "60,520"]]
    table(s, M, 3.3, 5.0, rows, [0.14, 0.66, 0.20], size=8.6, row_h=0.38, head_h=0.3,
          align_right=[2])

    label(s, 6.0, 1.58, "实施要点")
    actions(s, 6.0, 1.86, 6.4, [
        ("枚举标准化：先列全集再映射", "7 个字段取值收敛到 3～8 种，为下游 group by 扫清障碍"),
        ("异常值：删除与修正分开", "金额、数量删除 1,683 行；单价、商品价、年龄按中位数修正 861 条"),
        ("格式统一到同一套正则", "日期三种写法、手机号带横线、时间缺秒，全部规范化"),
        ("拆分合并与编码表", "时间戳合并、省市合并成大区、4 张编码表承载业务口径"),
    ])
    demo(s, DEMO[4])
    progress(s, 4)
    footer(s)
    note(s, "【2:30–3:00】第四步清洗。左边是结果：114809 到 111037，剔除 3772 行。"
            "右边四条要点：枚举先列全集、异常值删除与修正分开、格式统一、以及拆分合并。"
            "这里最值得记住的是金额阈值——没照抄 P99，因为异常值占 3.8% 已经污染了百分位，"
            "改用 IQR 得到 11356 元，正好落在真实的金额断崖上。")


def s08(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 5, 8)
    label(s, M, 1.6, "本步目标")
    text(s, M, 1.84, 4.2, 1.0,
         "把六张平铺的表组织成星型模型：四个维度描述“谁、什么、在哪、何时”，三张事实表存度量。",
         10.4, False, INK, line=1.45)
    label(s, M, 2.92, "产出：25 张表")
    out_card(s, M, 3.18, 4.2, 2.1, [
        ("4 张维度表", "用户 1,000 / 商品 600 / 门店 60 / 日期 731"),
        ("3 张事实表", "订单 14,398 / 明细 34,979 / 行为 60,000"),
        ("4 张编码表", "会员等级、支付、状态、渠道"),
        ("14 张中间表", "每一步的行数变化可追溯"),
    ])
    label(s, 5.2, 1.6, "实施要点")
    actions(s, 5.2, 1.88, 7.2, [
        ("按“度量进事实、描述进维度”拆表", "金额数量进事实表，类目省份会员等级进维度表"),
        ("按月分区而非按天", "366 个不到 40 行的小分区不划算；12 个月分区正合月度分析"),
        ("订单表按 user_id 分 8 桶", "用户级分析是主场景；1.4 万行分 8 桶，每桶约 1,800 行"),
        ("金额存两套字段避免口径混用", "item_amount 是原价，alloc_amount 是按订单实付分摊后的成交额"),
    ])
    demo(s, DEMO[5])
    progress(s, 5)
    footer(s)
    note(s, "【3:00–3:30】第五步建 DWD。四个维度加三张事实表，另有编码表和中间表。"
            "四个要点里最关键的是金额双字段：明细原价是订单实付的 11 倍，"
            "直接拿来算品类占比，加起来不等于 100%，所以必须有分摊字段。")


def s09(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 6, 9)
    label(s, M, 1.6, "本步目标")
    text(s, M, 1.84, 4.2, 0.94,
         "按不同粒度预先汇总，让后面每张图都读同一份结果，而不是各自回明细重算。",
         10.4, False, INK, line=1.45)
    label(s, M, 2.86, "产出：9 张汇总表")
    rows = [["表", "粒度", "行数"],
            ["dws_sales_day", "日 × 渠道", "1,464"],
            ["dws_sales_week", "周 × 渠道", "212"],
            ["dws_sales_month", "月 × 渠道", "48"],
            ["dws_category_month", "月 × 品类", "96"],
            ["dws_store_month", "月 × 门店", "720"],
            ["dws_province_month", "月 × 省份", "180"],
            ["dws_user_month", "月 × 用户", "8,448"],
            ["dws_behavior_day", "日 × 行为", "368"]]
    table(s, M, 3.14, 4.2, rows, [0.50, 0.30, 0.20], size=8.2, row_h=0.26, head_h=0.26,
          align_right=[2])

    label(s, 5.2, 1.6, "实施要点")
    actions(s, 5.2, 1.88, 7.2, [
        ("三张销售表覆盖日 / 周 / 月", "同一份 GMV 三个粒度，互为校验：加总必须完全相等"),
        ("维度表拆到品类 / 门店 / 省份", "每张表服务一类图，避免一张表被多个口径复用"),
        ("用户粒度单独出 dws_user_month", "RFM 与复购都从这里取，避免每次回订单表重算"),
        ("行为只覆盖 10～12 月", "数据本身只有三个月，368 行；不假装有全年漏斗"),
    ])
    demo(s, DEMO[6])
    progress(s, 6)
    footer(s)
    note(s, "【3:30–3:55】第六步 DWS。九张表按粒度分工。这里有个自检很重要："
            "日、周、月三个粒度的 GMV 加总必须完全相等，不等就说明重复计数或漏渠道。"
            "另外行为数据只有三个月，我就不假装有全年漏斗。")


def s10(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 7, 10)
    label(s, M, 1.58, "本步目标")
    text(s, M, 1.82, 4.2, 0.62,
         "一张表服务一类图，把指标口径写死在表里，BI 端不再二次计算。", 10.2, False, INK,
         line=1.4)
    text(s, M, 2.44, 1.0, 0.24, "11 张表", 13, True, BLUE, line=1.0)
    text(s, M + 1.1, 2.46, 3.1, 0.22, "合计 2,666 行，全部可预计算", 9, False, GRAY)

    ads = [("指标卡", "ads_kpi_overview"), ("月度趋势", "ads_kpi_month"),
           ("日趋势", "ads_sales_daily"), ("品类榜", "ads_category_rank"),
           ("省份地图", "ads_province_sales"), ("门店排行", "ads_store_rank"),
           ("渠道结构", "ads_channel_month"), ("行为漏斗", "ads_behavior_funnel"),
           ("用户分层", "ads_user_rfm"), ("支付方式", "ads_pay_type_month"),
           ("时段热力", "ads_hour_category")]
    for i, (name, tbl) in enumerate(ads):
        col, row = i % 2, i // 2
        bx, by = M + col * 2.14, 2.82 + row * 0.5
        rect(s, bx, by, 2.02, 0.44, fill=SOFT, line_color=LINE)
        text(s, bx + 0.08, by + 0.04, 0.9, 0.2, name, 8.4, True, NAVY)
        text(s, bx + 0.98, by + 0.05, 1.0, 0.2, tbl.replace("ads_", ""), 6.4, False, GRAY)

    label(s, 5.2, 1.58, "实施要点")
    actions(s, 5.2, 1.86, 7.2, [
        ("先定指标再建表", "GMV、有效 GMV、客单价、ARPU、坪效等指标，公式写进表注释"),
        ("金额三口径物理隔离", "订单口径 3,611.67 万、分摊口径 3,583.33 万、原价 4.03 亿，分别落在不同表"),
        ("每张表加加总自检", "6 张订单口径加总等于 GMV，2 张分摊口径加总等于分摊总额"),
        ("不追求一张表通吃", "宁可多建两张表，也不让一张表承担两种口径"),
    ])
    demo(s, DEMO[7])
    progress(s, 7)
    footer(s)
    note(s, "【3:55–4:20】第七步 ADS。十一张表，一张服务一类图。"
            "两个原则：指标公式写进表注释；金额三个口径物理隔离到不同表。"
            "每条指标都能从 DWD 回算，这是我在第五周反复验证的。")


def s11(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 8, 11)
    label(s, M, 1.58, "五步实施")
    steps = [("取数", "ads_sales_daily 全年 366 天"),
             ("特征工程", "lag_1 / lag_7 / ma_7 / ma_14 + 星期 / 月份"),
             ("按时间切分", "不打乱顺序，避免未来信息泄露"),
             ("三模型对照", "线性回归 / 朴素基线 / 常数基线"),
             ("六折滚动回测", "看稳定性，而不只看一次分数")]
    y = 1.86
    for i, (n, d) in enumerate(steps, 1):
        text(s, M, y, 0.26, 0.22, str(i), 9.4, True, BLUE)
        text(s, M + 0.28, y, 1.15, 0.22, n, 9.4, True, NAVY)
        text(s, M, y + 0.22, 3.0, 0.4, d, 8.2, False, GRAY, line=1.3)
        y += 0.62

    cd = CategoryChartData()
    cd.categories = ["常数基线", "线性回归", "朴素基线"]
    cd.add_series("MAPE", [12.11, 12.72, 20.08])
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(M - 0.1), Inches(4.06),
                            Inches(4.3), Inches(1.24), cd)
    ch = gf.chart
    ch.has_title = False
    ch.has_legend = False
    ch.font.size = Pt(7.5)
    ch.font.name = "微软雅黑"
    pl = ch.plots[0]
    pl.has_data_labels = True
    pl.data_labels.font.size = Pt(8)
    pl.data_labels.number_format = '0.00"%"'
    pl.data_labels.number_format_is_linked = False
    pl.gap_width = 35
    pl.series[0].format.fill.solid()
    pl.series[0].format.fill.fore_color.rgb = RGBColor(0x8F, 0xB8, 0xD8)
    va = ch.value_axis
    va.visible = False
    va.has_major_gridlines = False
    va.maximum_scale = 24
    ch.category_axis.tick_labels.font.size = Pt(7.5)
    ch.category_axis.format.line.fill.background()

    label(s, 5.2, 1.58, "实施要点")
    actions(s, 5.2, 1.86, 7.2, [
        ("先定义可比基线再谈模型", "朴素基线（昨日=今日）与常数基线（历史均值）同时跑，缺一个都说明不了问题"),
        ("报 MAPE 也报 MBE", "MAPE 看不出系统性高估/低估；本次 MBE +5,655.56 元，说明存在低估"),
        ("回测用滚动起点", "一次留出会受单次切分影响；六折滚动看的是稳定性"),
        ("结论按数据说话", "模型赢朴素基线 36.7%，但常数基线更低；序列 CV 仅 0.187，无趋势可学"),
    ])
    demo(s, DEMO[8])
    progress(s, 8)
    footer(s)
    note(s, "【4:20–4:45】第八步预测。五步：取数、特征、按时间切分、三模型对照、六折回测。"
            "左边这张柱状图就是结论：常数基线 12.11%，比线性回归的 12.72% 还低。"
            "所以我给的建议不上线，把均值作为基线。")


def s12(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 9, 12)
    label(s, M, 1.58, "四步链路")
    chain = [("① 提问", "中文业务问题"), ("② 生成", "模型输出 SELECT"),
             ("③ 校验", "guard_sql 四规则"), ("④ 执行", "Hive 只读 + 表格图")]
    y = 1.86
    for name, desc in chain:
        rect(s, M, y, 1.74, 0.5, fill=SOFT, line_color=LINE)
        text(s, M + 0.1, y + 0.06, 1.6, 0.2, name, 9, True, NAVY)
        text(s, M, y + 0.3, 1.7, 0.2, "", 7, False, GRAY)
        text(s, M + 0.1, y + 0.28, 1.62, 0.2, desc, 7.4, False, GRAY)
        y += 0.58

    label(s, M, 4.36, "四条硬规则")
    rules = [("只读开头", "必须是 SELECT / WITH"),
             ("禁止写操作", "insert / delete / drop 等"),
             ("必须带库名", "防止落到 default"),
             ("自动加 LIMIT", "最多 200 行")]
    for i, (t, d) in enumerate(rules):
        bx = M + (i % 2) * 2.1
        by = 4.64 + (i // 2) * 0.34
        text(s, bx, by, 0.2, 0.2, "✓", 9.2, True, BLUE)
        text(s, bx + 0.22, by, 0.86, 0.2, t, 8.2, True, NAVY)
        text(s, bx + 1.1, by, 1.0, 0.2, d, 7.2, False, GRAY)

    label(s, 5.2, 1.58, "实施要点")
    actions(s, 5.2, 1.86, 7.2, [
        ("表结构要进提示词", "把 ADS 表名、字段、注释摘要给模型，比让它猜表名准确得多"),
        ("示例 SQL 的分母不能写死", "曾经把分母写成全年常数，导致 12 月占比只有 2.43%，四项合计 9.4%"),
        ("校验在应用层做，不靠模型自觉", "guard_sql 不合格直接拒绝，并把拒绝原因返回给用户"),
        ("保留 SQL 与用量日志", "每次提问的 SQL 与 token 都落盘，可审计、可复现"),
    ])
    demo(s, DEMO[9])
    progress(s, 9)
    footer(s)
    note(s, "【4:45–5:10】第九步 NL2SQL。四步链路，关键是第三步校验："
            "模型生成的东西不能直接跑，所以有四条硬规则。"
            "这里有一个真实事故：示例里分母写死成全年，模型照抄，12 月微信占比只有 2.43%。"
            "改成窗口函数现算才对。")


def s13(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 10, 13)
    label(s, M, 1.58, "三端定位")
    ends = [("Superset 仪表板", "管理视角", "6 图 + 3 筛选器 + 交叉联动；REST API 全自动创建，可重跑"),
            ("ECharts 数据大屏", "展厅视角", "7 类图；1920×1080 设计 + 整体缩放；资源本地化，断网可演示"),
            ("Streamlit 问答", "自助视角", "提问 → SQL → 表格 → 图；含历史、错误提示、CSV 下载")]
    y = 1.86
    for name, who, desc in ends:
        rect(s, M, y, 4.3, 0.94, fill=SOFT)
        text(s, M + 0.14, y + 0.08, 2.2, 0.22, name, 9.8, True, NAVY)
        text(s, M + 3.3, y + 0.1, 0.9, 0.2, who, 8, False, ORANGE)
        text(s, M + 0.14, y + 0.36, 4.0, 0.5, desc, 8.2, False, GRAY, line=1.35)
        y += 1.04

    label(s, 5.2, 1.58, "实施要点")
    actions(s, 5.2, 1.86, 7.2, [
        ("仪表板用 API 自动建，不用手工点", "2 数据源 / 8 数据集 / 6 图表 / 1 仪表板，bootstrap 幂等可重跑"),
        ("大屏两份兜底", "echarts 与地图 json 本地化；接口不通回落 snapshot.json，避免白屏"),
        ("问答必须能看见 SQL", "表格旁边直接显示生成的 SQL，出了问题能定位到哪一句"),
        ("三端共用一套 ADS", "不各自算数，保证同一指标在三个界面上的值完全一致"),
    ])
    demo(s, DEMO[10])
    progress(s, 10)
    footer(s)
    note(s, "【5:10–5:35】第十步可视化。三端对应三类人：管理者、展厅、业务方自助。"
            "三条要点：仪表板用 API 自动建、大屏有本地化和快照两层兜底、问答必须把 SQL 亮出来。"
            "三端共用一套 ADS，所以同一指标在哪个界面都是同一个数。")


def s14(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 11, 14)
    label(s, M, 1.56, "服务组成：7 个常驻 + 2 个一次性任务")
    services = [("mysql", "元数据库", True), ("mysql-init", "建库·一次性", False),
                ("hive-metastore", "元数据", True), ("hive-server", "HiveServer2", True),
                ("clickhouse", "服务层缓存", True), ("superset", "BI 仪表板", True),
                ("superset-init", "建看板·一次性", False), ("api", "数据服务", True),
                ("app", "问答应用", True)]
    for k, (name, role,常驻) in enumerate(services):
        col, row = k % 3, k // 3
        bx, by = M + col * 1.4, 1.82 + row * 0.56
        rect(s, bx, by, 1.32, 0.48, fill=NAVY if 常驻 else RGBColor(0x5A, 0x77, 0x94))
        text(s, bx + 0.06, by + 0.04, 1.22, 0.18, name, 7.4, True, WHITE)
        text(s, bx + 0.06, by + 0.24, 1.22, 0.18, role, 6.2, False,
             RGBColor(0xC8, 0xD6, 0xE3))

    label(s, M, 3.62, "一条命令")
    text(s, M, 3.86, 4.2, 0.28, "docker compose up -d", 11.5, True, NAVY)
    text(s, M, 4.18, 4.2, 0.7,
         "期望 7 个 healthy + 2 个 Exited(0)。\n停止用 down，不加 -v 不丢数据。", 8.4, False,
         GRAY, line=1.4)
    text(s, M, 4.92, 4.2, 0.44, "深色块为常驻服务，浅色块为一次性任务。", 7.8, False, GRAY,
         line=1.3)

    label(s, 5.2, 1.58, "实施要点")
    actions(s, 5.2, 1.86, 7.2, [
        ("healthcheck 决定启动顺序", "depends_on 只保证容器起来，健康检查才保证可用"),
        ("密钥只走 .env", "仓库里只有占位符模板，git status 看不到真实 Key"),
        ("一次性任务单独处理", "mysql-init 建库、superset-init 建看板；Exited(0) 才是正常"),
        ("数据用命名卷与目录挂载", "MySQL 与 Hive 走目录挂载，ClickHouse 走命名卷（Windows 下 bind mount 写不进去）"),
    ])
    demo(s, DEMO[11])
    progress(s, 11)
    footer(s)
    note(s, "【5:35–6:00】第十一步部署。九个服务，七个常驻两个一次性。"
            "能一条命令起来，靠的是健康检查定顺序。"
            "四个要点里最后一条是 Windows 上的坑：ClickHouse 用目录挂载会写不进去，必须用命名卷。")


def s15(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    head(s, 12, 15)
    label(s, M, 1.58, "本步目标")
    text(s, M, 1.82, 4.2, 0.86,
         "端到端跑一遍，逐层核对数字是否吻合；把前四周的口径统一成一套，并补齐交付文档。",
         10.4, False, INK, line=1.45)
    label(s, M, 2.8, "产出")
    out_card(s, M, 3.06, 4.2, 2.2, [
        ("39 / 39 项", "服务、四层行数、口径、副本、接口全部通过"),
        ("五篇文档", "需求 / 清洗 / 架构 / 部署 / API"),
        ("英文 README", "11 节，作为开源门面"),
        ("Git 记录", "分支 + PR + Issue，规范率 97.3%"),
    ])
    label(s, 5.2, 1.58, "实施要点")
    actions(s, 5.2, 1.86, 7.2, [
        ("按数据流向逐层核对", "服务 → ODS → DWD → DWS → ADS → 副本 → 接口，每层给期望值与实测值"),
        ("核对写成脚本而不是手工看", "e2e_verify.py 一条命令跑 39 项，换机器可复验"),
        ("口径不一致要查清而不是选一个", "服务数 8/9、剔除率 3.28/3.29、门店 132/70.8 万、周表 208/212"),
        ("错误也在这一层修", "第 5 周脚本未挂载、一次性任务误判失败等，都在联调阶段解决"),
    ])
    demo(s, DEMO[12])
    progress(s, 12)
    footer(s)
    note(s, "【6:00–6:30】最后一步收口。方法是写脚本按数据流向逐层核对 39 项。"
            "这一阶段最大的价值不是加功能，而是把前四周的两种说法统一成一种——"
            "服务数、剔除率、门店排名、周数，这四处都出现过两套数。")


# ------------------------------------------------------------------ 问题页
def s16(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    plain_head(s, "问题索引", "实施过程中的主要问题与解决方式", 16)
    rows = [["#", "问题现象", "根本原因", "解决方式"],
            ["1", "hive-server 反复重启", "容器内 pid 文件残留", "force-recreate 重建容器，数据不动"],
            ["2", "字段中文注释变问号", "metastore 注释列是 latin1", "6 条 ALTER TABLE 改 utf8mb4"],
            ["3", "脏日期导入后变 NULL", "字段建成 date 类型", "全字段 string，先接住再转型"],
            ["4", "金额上限被抬到 551 万", "P99 落在异常值堆里", "改用 IQR，上限 11,356 元"],
            ["5", "品类占比合计不等于 100%", "明细原价与实付不同口径", "造 alloc_amount 分摊字段"],
            ["6", "Superset 建数据源报 422", "Hive 引擎会执行 SHOW CATALOGS", "配置里关闭目录探测"],
            ["7", "面板显示“图表已删除”", "图表与仪表板关联表为空", "模型层写 dashboard_slices"],
            ["8", "分区条件比全表还慢", "substr 让分区裁剪失效", "直接用分区列 order_month"],
            ["9", "Tez 报 Too many counters", "单条 SQL 的 union all 超过 8 路", "拆语句，一条一张表"]]
    table(s, M, 1.56, CW, rows, [0.05, 0.30, 0.29, 0.36], size=8.6, row_h=0.42, head_h=0.3)

    text(s, M, 5.86, CW, 0.5,
         "以上问题在《第5周_AI协同日志》与《部署手册》第 6 节均有完整记录（现象 → 原因 → 解法），此处仅作索引，不展开。",
         9, False, GRAY, line=1.4)
    footer(s)
    note(s, "【6:30–6:45】这一页是问题索引，不展开讲。九个问题分成三类：环境类、口径类、工具类。"
            "共同点都是“想当然”——日期想当然用 date、阈值想当然用 P99、分区想当然用 substr。"
            "详细的现象和原因写在 AI 协同日志和部署手册里，老师有兴趣我可以翻到具体那一页。")


# ------------------------------------------------------------------ 结束
def s17(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, W, H, fill=NAVY)
    rect(s, -1.2, 3.4, 4.4, 4.4, fill=BLUE, shape=MSO_SHAPE.OVAL, alpha=16)
    text(s, M, 2.16, 9.0, 0.76, "汇报结束，请老师提问", 32, True, WHITE, line=1.1)
    rect(s, M, 3.0, 1.5, 0.045, fill=ORANGE)
    text(s, M, 3.24, 9.6, 0.66,
         "演示环境已就绪：7 个常驻服务健康、2 个一次性任务已退出；任一数字可现场跑命令回到源头。",
         12, False, RGBColor(0xBF, 0xCF, 0xDD), line=1.45)
    text(s, M, 4.1, 2.0, 0.22, "代码仓库", 9.2, True, SKY)
    text(s, M, 4.34, 8.0, 0.24, "github.com/yuyu52525/xmsx　·　main（含第 5 周 PR #16）", 10.4, False,
         WHITE)
    text(s, M, 4.76, 2.0, 0.22, "核验入口", 9.2, True, SKY)
    text(s, M, 5.0, 8.4, 0.24, "python 第5周/py/e2e_verify.py　·　第5周/evidence/e2e_verify.txt",
         10.4, False, WHITE)
    text(s, M, 5.42, 2.0, 0.22, "文档", 9.2, True, SKY)
    text(s, M, 5.66, 8.6, 0.24, "五篇项目文档 + 两版答辩 PPT + 部署手册（20 条常见问题）", 10.4, False,
         WHITE)
    text(s, W - M - 1.4, 6.5, 1.4, 0.26, "Q & A", 14, True, SKY, align=PP_ALIGN.RIGHT)
    note(s, "【6:45–6:50】汇报到这里，谢谢老师。环境是起着的，老师想看任何一层的数据，"
            "我们现场跑命令就能回到源头。请老师提问。")


def build() -> Path:
    from pptx import Presentation
    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    for fn in (s01, s02, s03, s04, s05, s06, s07, s08, s09, s10, s11, s12,
               s13, s14, s15, s16, s17):
        fn(prs)
    prs.core_properties.title = "云购生活数仓 · 答辩（过程版 v2）"
    prs.core_properties.author = "余天乐"
    prs.core_properties.subject = "四个大任务、十二个实施步骤"
    prs.save(str(OUT))
    return OUT


if __name__ == "__main__":
    print(build())