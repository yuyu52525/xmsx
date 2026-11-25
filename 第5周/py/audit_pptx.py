"""第 5 周 · 答辩 PPT 自检（结构 / 文字溢出 / 图表数据）

为什么需要：python-pptx 不会排版，也不会告诉你"这行字被挤出文本框"。
本机当前模型不能读图，无法用渲染出的图片做视觉检查，所以退一步用几何估算兜底：
按字号与框宽估算每个文本框需要几行、需要多高，超过框高或超出画布就报出来。

局限（写清楚，别当成渲染验证）：这是估算，不是渲染结果；
它能抓到"明显溢出/超出边界/文本为空"这类硬问题，抓不到"差 2 毫米的视觉拥挤"。

用法：python audit_pptx.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

HERE = Path(__file__).resolve().parent
PPTX = HERE.parent / "docs" / "答辩PPT_第5周.pptx"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

SW, SH = 13.333, 7.5


def char_w(ch: str, size_pt: float) -> float:
    """估算单字符宽度（英寸）：中文/全角 = 1em，ASCII 约 0.55em。"""
    em = size_pt / 72
    if ord(ch) > 0x2E80 or ch in "，。、；：（）“”‘’—…·":
        return em
    if ch == " ":
        return em * 0.3
    return em * 0.55


def est_lines(txt: str, width_in: float, size_pt: float) -> int:
    if not txt.strip():
        return 0
    avail = max(0.2, width_in)
    lines, cur = 1, 0.0
    for ch in txt:
        w = char_w(ch, size_pt)
        if cur + w > avail:
            lines += 1
            cur = w
        else:
            cur += w
    return lines


def shape_text(sh) -> tuple[str, float]:
    """返回 (合并文本, 最大字号)。"""
    if not sh.has_text_frame:
        return "", 0
    parts, size = [], 0
    for p in sh.text_frame.paragraphs:
        for r in p.runs:
            if r.font.size:
                size = max(size, r.font.size.pt)
        line = "".join(r.text for r in p.runs)
        if line:
            parts.append(line)
    return "\n".join(parts), (size or 12)


def audit() -> int:
    prs = Presentation(str(PPTX))
    print(f"文件：{PPTX.name}")
    print(f"页数：{len(prs.slides)}　画布：{SW}×{SH} in")

    problems: list[str] = []
    chart_rows: list[str] = []

    for idx, slide in enumerate(prs.slides, 1):
        n_txt = n_pic = n_tbl = n_chart = 0
        notes = slide.notes_slide.notes_text_frame.text.strip() if slide.has_notes_slide else ""

        for sh in slide.shapes:
            l, t = sh.left / 914400, sh.top / 914400
            w, h = sh.width / 914400, sh.height / 914400

            if sh.shape_type == 13 or sh.has_chart is False and sh.shape_type == 13:
                n_pic += 1
            if getattr(sh, "has_chart", False) and sh.has_chart:
                n_chart += 1
                try:
                    ch = sh.chart
                    cats = list(ch.plots[0].categories)
                    vals = list(ch.series[0].values)
                    chart_rows.append(
                        f"  p{idx:02d} 图表：{len(cats)} 个类别，"
                        f"首值 {vals[0]:.2f}，末值 {vals[-1]:.2f}，"
                        f"合计 {sum(vals):.2f}")
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"p{idx} 图表读取失败：{exc}")
            if sh.has_table:
                n_tbl += 1
                tb = sh.table
                # 表格文字溢出：列宽够不够放下最长单元格
                for c_i, col in enumerate(tb.columns):
                    col_w = col.width / 914400
                    for r_i, row in enumerate(tb.rows):
                        cell = tb.cell(r_i, c_i)
                        txt = cell.text
                        if not txt:
                            continue
                        size = 11.5
                        for p in cell.text_frame.paragraphs:
                            for r in p.runs:
                                if r.font.size:
                                    size = r.font.size.pt
                        need = est_lines(txt, col_w - 0.18, size) * size * 1.05 / 72
                        if need > row.height / 914400 + 0.06:
                            problems.append(
                                f"p{idx} 表格单元格({r_i},{c_i}) 可能换行：{txt[:18]}")
            if sh.has_text_frame and sh.text_frame.text.strip():
                n_txt += 1
                txt, size = shape_text(sh)
                if not size:
                    continue
                need_h = 0.0
                for para in txt.split("\n"):
                    need_h += est_lines(para, w - 0.04, size) * size * 1.36 / 72
                # 超出画布
                if l < -0.02 or t < -0.02 or l + w > SW + 0.02 or t + need_h > SH + 0.02:
                    problems.append(
                        f"p{idx} 文本超出画布：'{txt[:16]}' 需高 {need_h:.2f}，顶 {t:.2f}")
                # 明显溢出文本框
                elif need_h > h + 0.16:
                    problems.append(
                        f"p{idx} 文本可能溢出：'{txt[:16]}' 框高 {h:.2f} 需 {need_h:.2f}")

        print(f"  p{idx:02d} 文本 {n_txt:>2} 表 {n_tbl} 图 {n_chart} 图注 {len(notes):>4} 字")
        if not notes:
            problems.append(f"p{idx} 缺少演讲备注")

    print("\n图表数据：")
    print("\n".join(chart_rows))

    print("\n检查结果：")
    if problems:
        for p in problems:
            print("  ✗ " + p)
        print(f"  共 {len(problems)} 项待处理")
        return 1
    print("  ✓ 未发现结构 / 溢出 / 缺备注问题")
    return 0


if __name__ == "__main__":
    raise SystemExit(audit())