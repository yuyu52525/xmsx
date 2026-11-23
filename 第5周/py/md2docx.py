"""Markdown → Word（.docx）转换器（第 5 周文档统一排版用）

与 `第4周/py/md2docx.py` 的唯一差别：**新增图片支持**（`![说明](相对路径.png)`）。
前四周的文档图片是事后手工插进 docx 的，第 5 周的文档要求"改一行 md 就能重出一版 Word"，
所以这里把图片也纳入转换规则：宽度固定 15 cm（A4 减左右页边距后正好一行），
路径相对 md 文件解析，找不到图片时降级为一行灰字提示，不中断整篇转换。

为什么不直接改第 4 周那一份：第 4 周 5 篇 docx 已经定稿交付，改转换器会让它们在
"重跑 --all 时"外观发生变化；第 5 周独立一份，各自可复现。

支持：# / ## / ### 标题、段落、- 无序列表、1. 有序列表、
     | 表格 |、```代码块```、> 引用、**粗体**、`行内代码`、水平线 ---、![图](路径)

用法：
  python md2docx.py ../docs/需求文档.md
  python md2docx.py --all          # 转换 ../docs/ 下所有 .md
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"

CN_FONT = "微软雅黑"
CODE_FONT = "Consolas"
ACCENT = RGBColor(0x1F, 0x6F, 0xB2)
IMG_WIDTH_CM = 15.0


def add_image(doc: Document, md_path: Path, target: str, alt: str) -> None:
    """插入图片：路径相对 md 文件解析；尺寸按 A4 版心宽度等比缩放。"""
    rel = target.strip().replace("\\", "/")
    candidates = [md_path.parent / rel, DOCS / rel, HERE.parent / rel]
    img = next((p for p in candidates if p.exists()), None)
    if img is None:
        p = doc.add_paragraph()
        run = p.add_run(f"[缺图] {alt or rel}（未找到 {rel}）")
        set_cn_font(run, CN_FONT, 9, color=RGBColor(0xC0, 0x30, 0x30))
        return
    try:
        doc.add_picture(str(img), width=Cm(IMG_WIDTH_CM))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if alt:
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap.add_run(alt)
            set_cn_font(run, CN_FONT, 9, color=RGBColor(0x66, 0x66, 0x66))
            cap.paragraph_format.space_after = Pt(6)
    except Exception as exc:  # noqa: BLE001
        p = doc.add_paragraph()
        run = p.add_run(f"[插图失败] {alt or rel}：{type(exc).__name__}")
        set_cn_font(run, CN_FONT, 9, color=RGBColor(0xC0, 0x30, 0x30))


# ------------------------------------------------------------------ 基础工具
def set_cn_font(run, font: str = CN_FONT, size: float | None = None,
                bold: bool | None = None, color: RGBColor | None = None) -> None:
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def shade(cell, hex_color: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def add_code_block(doc: Document, lines: list[str]) -> None:
    """代码块：单格表格 + 浅灰底 + 等宽字体，跨页不会散。"""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    shade(cell, "F4F6F8")
    cell.text = ""
    for i, ln in enumerate(lines):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.line_spacing = 1.05
        run = p.add_run(ln if ln else " ")
        set_cn_font(run, CODE_FONT, 8.5, color=RGBColor(0x33, 0x33, 0x33))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_inline(paragraph, text: str) -> None:
    """处理 **粗体** 与 `行内代码`，其余按普通文本。"""
    tokens = re.split(r"(\*\*.+?\*\*|`[^`]+`)", text)
    for tk in tokens:
        if not tk:
            continue
        if tk.startswith("**") and tk.endswith("**"):
            run = paragraph.add_run(tk[2:-2])
            set_cn_font(run, CN_FONT, 10.5, bold=True)
        elif tk.startswith("`") and tk.endswith("`"):
            run = paragraph.add_run(tk[1:-1])
            set_cn_font(run, CODE_FONT, 9.5, color=RGBColor(0xB0, 0x30, 0x60))
        else:
            run = paragraph.add_run(tk)
            set_cn_font(run, CN_FONT, 10.5)


def add_table(doc: Document, rows: list[list[str]]) -> None:
    cols = max(len(r) for r in rows)
    tbl = doc.add_table(rows=len(rows), cols=cols)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r_i, row in enumerate(rows):
        for c_i in range(cols):
            cell = tbl.cell(r_i, c_i)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.space_before = Pt(1)
            txt = row[c_i] if c_i < len(row) else ""
            if r_i == 0:
                shade(cell, "1F6FB2")
                run = p.add_run(txt.replace("**", ""))
                set_cn_font(run, CN_FONT, 9.5, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
            else:
                add_inline(p, txt)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


# ------------------------------------------------------------------ 主转换
def convert(md_path: Path, docx_path: Path | None = None) -> Path:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = docx_path or md_path.with_suffix(".docx")

    doc = Document()
    # A4 纵向 + 适中页边距
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.4)
    sec.top_margin = sec.bottom_margin = Cm(2.2)

    style = doc.styles["Normal"]
    style.font.name = CN_FONT
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()

        # 代码块
        if line.startswith("```"):
            i += 1
            buf: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i].rstrip())
                i += 1
            i += 1
            add_code_block(doc, buf)
            continue

        # 图片
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
        if m:
            add_image(doc, md_path, m.group(2), m.group(1))
            i += 1
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 表格
        if line.lstrip().startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", lines[i + 1]):
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:\-|]+$", "|".join(cells)):
                    rows.append(cells)
                i += 1
            add_table(doc, rows)
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if level == 1:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(title)
                set_cn_font(run, CN_FONT, 19, bold=True, color=ACCENT)
                p.paragraph_format.space_after = Pt(14)
            else:
                size = {2: 14, 3: 12, 4: 11}.get(level, 10.5)
                p = doc.add_paragraph()
                run = p.add_run(title)
                set_cn_font(run, CN_FONT, size, bold=True, color=ACCENT)
                p.paragraph_format.space_before = Pt(10 if level == 2 else 7)
                p.paragraph_format.space_after = Pt(5)
            i += 1
            continue

        # 引用
        if line.startswith(">"):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            run = p.add_run(line.lstrip("> ").replace("**", ""))
            set_cn_font(run, CN_FONT, 10, color=RGBColor(0x60, 0x60, 0x60))
            i += 1
            continue

        # 水平线
        if re.match(r"^-{3,}$", line.strip()):
            p = doc.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            pbdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:color"), "CCCCCC")
            pbdr.append(bottom)
            pPr.append(pbdr)
            i += 1
            continue

        # 列表
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.left_indent = Cm(0.75 + 0.4 * (len(m.group(1)) // 2))
            p.paragraph_format.space_after = Pt(2)
            add_inline(p, m.group(2))
            i += 1
            continue

        m = re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", line)
        if m:
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.left_indent = Cm(0.75 + 0.4 * (len(m.group(1)) // 2))
            p.paragraph_format.space_after = Pt(2)
            add_inline(p, m.group(3))
            i += 1
            continue

        # 普通段落
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.35
        add_inline(p, line.strip())
        i += 1

    doc.save(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?", help="单个 md 文件")
    ap.add_argument("--all", action="store_true", help="转换 docs/ 下全部 md")
    args = ap.parse_args()

    if args.all:
        targets = sorted(DOCS.glob("*.md"))
    elif args.md:
        targets = [Path(args.md)]
    else:
        print(__doc__)
        return 2

    for t in targets:
        out = convert(t)
        print(f"  {t.name}  ->  {out.name}  ({out.stat().st_size:,} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())