"""第 5 周 · Word 成品自检（结构 + 图片 + 缺图检查）

为什么需要：md2docx 是自研转换器，图片/表格/代码块任何一处走偏都可能静默出错
（最典型的是图片路径解析不到，转出来是一行"[缺图]"）。
写文档时改一句话就要重转一次，每次人工翻一遍不现实，所以交给脚本。

用法：python check_docx.py            # 检查 ../docs 下全部 docx
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

HERE = Path(__file__).resolve().parent
DOCS = HERE.parent / "docs"

BAD_MARKS = ("[缺图]", "[插图失败]")


def check(path: Path) -> bool:
    doc = Document(str(path))
    paras = doc.paragraphs
    tables = doc.tables
    images = len(doc.inline_shapes)
    text = "\n".join(p.text for p in paras)
    bad = [m for m in BAD_MARKS if m in text]

    headings = [p.text for p in paras if p.runs and p.runs[0].font.size
                and p.runs[0].font.size.pt >= 12 and p.runs[0].bold]
    print(f"\n=== {path.name}")
    print(f"  段落 {len(paras)}　表格 {len(tables)}　图片 {images}　标题块 {len(headings)}")
    print(f"  首个标题：{headings[0] if headings else '（无）'}")
    print(f"  字符数 {len(text):,}")
    if bad:
        print(f"  ✗ 存在异常标记：{bad}")
        return False
    if len(tables) == 0:
        print("  ✗ 没有任何表格（本项目的文档都应有表格）")
        return False
    print("  ✓ 结构正常")
    return True


def main() -> int:
    files = sorted(DOCS.glob("*.docx"))
    if not files:
        print("没有 docx")
        return 2
    ok = all(check(p) for p in files)
    print("\n结论：" + ("全部合格" if ok else "有文档存在问题"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())