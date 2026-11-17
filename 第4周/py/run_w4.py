"""第 4 周一键运行入口（给双击 .bat 用）

为什么要有这个文件（延续第 3 周的做法）：
  .bat 里直接写中文会被 cmd 的代码页解析坏，实测报"不是内部命令"。
  所以 bat 只做"找 Python + 调这里"，所有逻辑与中文提示都在 Python 里。

命令：
  python run_w4.py check        环境与 8 个服务自检
  python run_w4.py data         初始化可视化数据（建表/装载/校验/导 CH/导 MySQL）
  python run_w4.py export       只重做 ClickHouse + MySQL 两份副本
  python run_w4.py api          本地起数据服务（8000）
  python run_w4.py app          本地起 Streamlit 问答（8501）
  python run_w4.py screen       打开 ECharts 大屏（浏览器）
  python run_w4.py superset     打开 Superset 仪表板（浏览器）
  python run_w4.py verify       三界面自动上机自检 + 截图
  python run_w4.py stress       压力测试（完整）
  python run_w4.py stress-quick 压力测试（快速）
  python run_w4.py docs         markdown 批量转 docx
  python run_w4.py docker-up    一键部署（docker compose up -d）
  python run_w4.py docker-down  停止全部服务（保留数据）
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent            # 第4周
REPO = ROOT.parent            # 仓库根

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass

COMPOSE = ["docker", "compose", "-f", str(REPO / "docker-compose.yml")]


def _sep(title: str) -> None:
    sys.stdout.flush()
    print()
    print("=" * 66)
    print(f"  {title}")
    print("=" * 66)
    sys.stdout.flush()
    print("=" * 66)


def _run(script: str, *args: str, cwd: Path | None = None) -> int:
    return subprocess.call([sys.executable, str(HERE / script), *args],
                           cwd=str(cwd or HERE))


def _compose(*args: str) -> int:
    cmd = COMPOSE + list(args)
    print("$ " + " ".join(cmd))
    return subprocess.call(cmd, cwd=str(REPO))


# ------------------------------------------------------------------ 各命令
def cmd_check() -> int:
    _sep("环境自检")
    print(f"Python : {sys.version.split()[0]}")
    print(f"解释器 : {sys.executable}")
    print(f"仓库   : {REPO}")

    print("\n--- Docker ---")
    try:
        out = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0:
            print(f"  OK    Docker 引擎 {out.stdout.strip()}")
        else:
            print("  MISS  Docker 未运行（请先启动 Docker Desktop）")
            return 1
    except Exception as exc:  # noqa: BLE001
        print(f"  MISS  {type(exc).__name__}: 找不到 docker 命令")
        return 1

    print("\n--- 服务状态 ---")
    services = {
        "mysql": "元数据库", "hive-metastore": "Hive 元数据",
        "hive-server": "HiveServer2", "clickhouse": "CH 缓存",
        "superset": "Superset", "ydsh-api": "数据服务", "ydsh-app": "问答应用",
    }
    bad = []
    for name, desc in services.items():
        r = subprocess.run(["docker", "inspect", "--format",
                            "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}", name],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  MISS  {name:<16}{desc}（容器不存在）")
            bad.append(name)
            continue
        status, health = (r.stdout.strip().split("|") + [""])[:2]
        ok = status == "running" and health in ("healthy", "")
        print(f"  {'OK  ' if ok else 'WARN'}  {name:<16}{desc:<12}{status} {health}")
        if not ok:
            bad.append(name)

    print("\n--- 数据 ---")
    env = dict(os.environ)
    env.setdefault("CLICKHOUSE_HOST", "127.0.0.1")
    env.setdefault("CLICKHOUSE_PORT", "8123")
    env.setdefault("CLICKHOUSE_USER", "ydsh")
    env.setdefault("CLICKHOUSE_PASSWORD", "ydsh123")
    code = """
import hive_client, ch_client
try:
    print("  Hive:", hive_client.ping().split()[0])
    n = len(hive_client.query_df("show tables"))
    print(f"  ydsh_ads 表数: {n}")
except Exception as e:
    print("  Hive 连不上:", type(e).__name__)
try:
    print("  ClickHouse:", ch_client.ping())
    c = ch_client.table_counts()
    print(f"  CH 副本表数: {len(c)}  行数合计: {sum(c.values())}")
except Exception as e:
    print("  ClickHouse 不可用:", type(e).__name__)
"""
    sys.stdout.flush()
    subprocess.call([sys.executable, "-c", code], cwd=str(HERE), env=env)

    print("\n--- 接口 ---")
    try:
        import requests

        for url in ("http://127.0.0.1:8000/api/health", "http://127.0.0.1:8501/_stcore/health",
                    "http://127.0.0.1:8088/health"):
            try:
                r = requests.get(url, timeout=10)
                print(f"  OK    {url} -> {r.status_code}")
            except Exception as exc:  # noqa: BLE001
                print(f"  MISS  {url} ({type(exc).__name__})")
    except Exception:  # noqa: BLE001
        print("  （没装 requests，跳过接口探测）")

    print("\n" + "-" * 66)
    print("结论：" + ("有一项以上未就绪，按提示处理" if bad else "全部就绪，可以演示"))
    return 0 if not bad else 1


def cmd_data() -> int:
    _sep("初始化可视化数据（建表 → 装载 → 校验 → 导 CH → 导 MySQL）")
    rc = 0
    rc |= _run("sql_runner.py", str(ROOT / "sql/ads/create_ads_w4.sql"),
               "--out", str(ROOT / "evidence/ads_w4_create.txt"))
    rc |= _run("sql_runner.py", str(ROOT / "sql/ads/load_ads_w4.sql"),
               "--out", str(ROOT / "evidence/ads_w4_load.txt"))
    rc |= _run("sql_runner.py", str(ROOT / "sql/ads/verify_ads_w4.sql"),
               "--out", str(ROOT / "evidence/ads_w4_verify.txt"))
    rc |= cmd_export()
    return rc


def cmd_export() -> int:
    _sep("同步服务层副本（ClickHouse）+ 业务库快照（MySQL）")
    env = dict(os.environ)
    env.setdefault("CLICKHOUSE_HOST", "127.0.0.1")
    env.setdefault("CLICKHOUSE_PORT", "8123")
    env.setdefault("CLICKHOUSE_USER", "ydsh")
    env.setdefault("CLICKHOUSE_PASSWORD", "ydsh123")
    r1 = subprocess.call([sys.executable, str(HERE / "export_to_clickhouse.py")],
                         cwd=str(HERE), env=env)
    r2 = _run("export_to_mysql.py")
    return r1 | r2


def cmd_api() -> int:
    _sep("数据服务（本地 8000）")
    print("浏览器打开 http://localhost:8000/ 看大屏；Ctrl+C 结束")
    return _run("api_server.py")


def cmd_app() -> int:
    _sep("Streamlit 问答（本地 8501）")
    print("浏览器打开 http://localhost:8501/ ；Ctrl+C 结束")
    cmd = [sys.executable, "-m", "streamlit", "run", str(HERE / "streamlit_app.py"),
           "--server.port", "8501", "--browser.gatherUsageStats", "false"]
    return subprocess.call(cmd, cwd=str(HERE))


def cmd_screen() -> int:
    _sep("打开 ECharts 数据大屏")
    webbrowser.open("http://localhost:8000/")
    return 0


def cmd_superset() -> int:
    _sep("打开 Superset 仪表板（admin / admin）")
    webbrowser.open("http://localhost:8088/superset/dashboard/ydgmv-overview/")
    return 0


def cmd_verify() -> int:
    _sep("三界面自动上机自检（无头浏览器真实点击 + 截图）")
    return _run("ui_check.py")


def cmd_stress() -> int:
    _sep("压力测试（完整，约 8~12 分钟）")
    return _run_stress([])


def cmd_stress_quick() -> int:
    _sep("压力测试（快速，约 4 分钟）")
    return _run_stress(["--quick"])


def _run_stress(args: list[str]) -> int:
    env = dict(os.environ)
    env.setdefault("CLICKHOUSE_HOST", "127.0.0.1")
    env.setdefault("CLICKHOUSE_PORT", "8123")
    env.setdefault("CLICKHOUSE_USER", "ydsh")
    env.setdefault("CLICKHOUSE_PASSWORD", "ydsh123")
    return subprocess.call([sys.executable, str(ROOT / "stress" / "stress_test.py"), *args],
                           cwd=str(ROOT / "stress"), env=env)


def cmd_docs() -> int:
    _sep("Markdown → Word")
    return _run("md2docx.py", "--all")


def cmd_docker_up() -> int:
    _sep("一键部署")
    return _compose("up", "-d")


def cmd_docker_down() -> int:
    _sep("停止全部服务（保留数据卷）")
    return _compose("down")


COMMANDS = {
    "check": cmd_check,
    "data": cmd_data,
    "export": cmd_export,
    "api": cmd_api,
    "app": cmd_app,
    "screen": cmd_screen,
    "superset": cmd_superset,
    "verify": cmd_verify,
    "stress": cmd_stress,
    "stress-quick": cmd_stress_quick,
    "docs": cmd_docs,
    "docker-up": cmd_docker_up,
    "docker-down": cmd_docker_down,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("可用命令：" + " / ".join(COMMANDS))
        return 0
    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    raise SystemExit(main())