"""第 4 周 · Hive SQL 批量执行器（把 .sql 文件逐条跑掉并留下证据）

为什么不用 beeline：
  1) 本机没有装 Hive 客户端，容器内 beeline 的 -e 参数会把多语句解析坏
     （实测报 ParseException: cannot recognize input near 'show'）；
  2) 逐条执行才能做到「一条失败不影响其他条」，并把每条的结果写进证据文件。

用法：
  python sql_runner.py ../sql/ads/create_ads_w4.sql
  python sql_runner.py ../sql/ads/verify_ads_w4.sql --out ../evidence/ads_w4_verify.txt
  python sql_runner.py ../sql/ads/verify_ads_w4.sql --database ydsh_ads

说明：
  - 按 ';' 切分语句，自动剥掉整行 '--' 注释与空行，不处理跨行块注释（脚本里没有）；
  - 每个语句单独计时；失败只记录不中断，最后用退出码汇总；
  - 输出统一 UTF-8，避免 Windows 控制台代码页导致中文乱码。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from hive_client import get_conn  # noqa: E402


def parse_statements(sql_text: str) -> list[str]:
    """剥注释 + 按分号切分，返回可执行语句列表。"""
    kept: list[str] = []
    for line in sql_text.splitlines():
        # 整行注释直接丢掉；行尾注释也剥掉（本项目的 SQL 里没有字符串内含 '--' 的情况）
        idx = line.find("--")
        if idx >= 0:
            line = line[:idx]
        kept.append(line)
    body = "\n".join(kept)
    stmts = []
    for raw in body.split(";"):
        s = raw.strip()
        if s:
            stmts.append(" ".join(x.strip() for x in s.splitlines() if x.strip()))
    return stmts


def fmt_rows(cols: list[str], rows: list[tuple], max_rows: int = 40) -> str:
    """把结果集排成等宽表（中文按 2 字符宽对齐）。"""
    def width(s: object) -> int:
        t = "" if s is None else str(s)
        return sum(2 if ord(c) > 127 else 1 for c in t)

    def pad(s: object, w: int) -> str:
        t = "" if s is None else str(s)
        return t + " " * (w - width(t))

    data = [[("NULL" if v is None else v) for v in r] for r in rows[:max_rows]]
    widths = [max([width(c)] + [width(r[i]) for r in data]) for i, c in enumerate(cols)]
    out = ["  " + "  ".join(pad(c, widths[i]) for i, c in enumerate(cols))]
    out.append("  " + "  ".join("-" * w for w in widths))
    for r in data:
        out.append("  " + "  ".join(pad(v, widths[i]) for i, v in enumerate(r)))
    if len(rows) > max_rows:
        out.append(f"  ...（共 {len(rows)} 行，仅显示前 {max_rows} 行）")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="逐条执行 Hive SQL 脚本")
    ap.add_argument("sqlfile", help="要执行的 .sql 文件")
    ap.add_argument("--out", default=None, help="把输出同时写入该证据文件（UTF-8）")
    ap.add_argument("--database", default="ydsh_ads", help="默认连接的库，默认 ydsh_ads")
    ap.add_argument("--stop-on-error", action="store_true", help="遇到错误立即停止")
    args = ap.parse_args()

    path = Path(args.sqlfile)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists():
        print(f"[错误] 找不到 SQL 文件：{path}")
        return 2

    stmts = parse_statements(path.read_text(encoding="utf-8"))
    lines: list[str] = []
    t_all = time.time()
    fails = 0
    ok = 0

    lines.append("=" * 78)
    lines.append(f"SQL 脚本执行：{path}")
    lines.append(f"连接：Hive {os.getenv('HIVE_HOST', 'localhost')}:{os.getenv('HIVE_PORT', '10000')}  库：{args.database}")
    lines.append(f"语句数：{len(stmts)}    开始时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 78)

    try:
        with get_conn(args.database) as conn:
            cur = conn.cursor()
            for i, stmt in enumerate(stmts, 1):
                preview = stmt if len(stmt) <= 150 else stmt[:150] + " ..."
                lines.append("")
                lines.append(f"[{i}/{len(stmts)}] {preview}")
                t0 = time.time()
                try:
                    cur.execute(stmt)
                    dt = time.time() - t0
                    if cur.description:
                        rows = cur.fetchall()
                        cols = [d[0].split(".")[-1] for d in cur.description]
                        lines.append(f"  -> {len(rows)} 行  ({dt:.2f}s)")
                        lines.append(fmt_rows(cols, rows))
                    else:
                        lines.append(f"  -> OK  ({dt:.2f}s)")
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    dt = time.time() - t0
                    fails += 1
                    lines.append(f"  -> 失败 ({dt:.2f}s)：{type(exc).__name__}: {exc}")
                    if os.getenv("SQL_RUNNER_TRACE"):
                        lines.append(traceback.format_exc())
                    if args.stop_on_error:
                        lines.append("\n[已按 --stop-on-error 中止]")
                        break
    except Exception as exc:  # noqa: BLE001  连不上 Hive
        lines.append(f"\n[错误] 连接 Hive 失败：{type(exc).__name__}: {exc}")
        text = "\n".join(lines)
        print(text)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
        return 3

    total = time.time() - t_all
    lines.append("")
    lines.append("=" * 78)
    lines.append(f"汇总：成功 {ok} 条，失败 {fails} 条，总耗时 {total:.1f}s")
    lines.append("=" * 78)

    text = "\n".join(lines)
    print(text)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = (Path.cwd() / out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"\n[证据已保存] {out}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())