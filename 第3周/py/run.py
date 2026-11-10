"""一键运行入口（给双击 .bat 用）

为什么要有这个文件：
  .bat 里写中文会因 cmd 的代码页问题被解析坏（实测报 'y"' 不是内部命令）。
  所以把逻辑和中文提示全部搬到 Python 里，bat 只做「找 Python + 调这里」。

用法（在 py 目录下）：
  python run.py check      环境自检
  python run.py llm        大模型连通性自检
  python run.py nl2sql     交互式提问
  python run.py insight    生成 AI 洞察
  python run.py forecast   重跑预测模型
  python run.py kpi        导出 KPI 表格
  python run.py usage      查看 token 用量
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Windows 下 stdout 的默认编码跟控制台代码页可能不一致（管道/重定向时尤其明显），
# 不统一成 UTF-8 会出现「中文变问号」。放在最前面，后续所有 print 都受益。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

MODULES = ["pandas", "numpy", "sklearn", "matplotlib", "pyhive", "thrift",
           "openai", "langchain_core", "dotenv", "openpyxl"]


def _sep(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _run(script: str, *args: str) -> int:
    """用当前解释器跑本目录下的脚本（子进程，便于统一收错误）。"""
    return subprocess.call([sys.executable, str(HERE / script), *args], cwd=str(HERE))


def cmd_check() -> int:
    _sep("环境自检")
    print(f"Python : {sys.version.split()[0]}")
    print(f"解释器 : {sys.executable}")
    print(f"工作目录: {HERE}")

    print("\n--- 依赖 ---")
    missing = []
    for m in MODULES:
        try:
            importlib.import_module(m)
            print(f"  OK    {m}")
        except Exception as exc:  # noqa: BLE001
            missing.append(m)
            print(f"  MISS  {m}  ({type(exc).__name__})")

    print("\n--- 配置 ---")
    env = HERE / ".env"
    print(f"  {'OK   ' if env.exists() else 'MISS '} .env {'存在' if env.exists() else '不存在（复制 .env.example 为 .env 并填 Key）'}")

    print("\n--- Hive ---")
    try:
        from hive_client import ping
        print("  OK    Hive 可连接" if ping() else "  MISS  Hive 连不上（执行 docker compose up -d）")
    except Exception as exc:  # noqa: BLE001
        print(f"  MISS  连接失败：{type(exc).__name__}")

    print("\n" + "-" * 60)
    if missing:
        print(f"结论：缺少依赖 {', '.join(missing)}")
        print("解决：pip install pandas numpy scikit-learn matplotlib pyhive thrift "
              "openai langchain-core python-dotenv openpyxl")
        return 1
    print("结论：环境就绪")
    return 0


def cmd_llm() -> int:
    _sep("大模型连通性自检（约 13 tokens）")
    return _run("llm_client.py")


def cmd_nl2sql() -> int:
    _sep("NL2SQL 自然语言查询（每次约 3000 tokens）")
    print("示例问题：")
    print("  1) 广东省2024年12月的销售额是多少？")
    print("  2) 2024年各品类销量前5名是哪些？")
    print("  3) 2024年12月各渠道的GMV占比")
    print()
    try:
        q = input("请输入你的问题（直接回车用示例 3）：").strip()
    except EOFError:
        q = ""
    if not q:
        q = "2024年12月各渠道的GMV占比是多少？"
    print("\n正在生成 SQL 并执行 ...")
    print("-" * 60)
    return _run("nl2sql.py", q)


def cmd_insight() -> int:
    _sep("AI 智能洞察（约 4000 tokens）")
    rc = _run("ai_insight.py", "--llm")
    if rc == 0:
        print("\n报告已生成：evidence/ai_insight.md")
    return rc


def cmd_forecast() -> int:
    _sep("GMV 预测建模（纯本地计算，不消耗 token，约 1~2 分钟）")
    rc = _run("forecast_gmv.py")
    if rc == 0:
        print("\n图表已生成：docs/images/")
    return rc


def cmd_kpi() -> int:
    _sep("导出 KPI 结果表 Excel（纯本地查询，不消耗 token）")
    return _run("export_kpi_xlsx.py")


def cmd_usage() -> int:
    _sep("本地 token 用量统计")
    return _run("llm_client.py", "--usage")


COMMANDS = {
    "check": cmd_check,
    "llm": cmd_llm,
    "nl2sql": cmd_nl2sql,
    "insight": cmd_insight,
    "forecast": cmd_forecast,
    "kpi": cmd_kpi,
    "usage": cmd_usage,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("可用命令：" + " / ".join(COMMANDS))
        return 0
    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main())