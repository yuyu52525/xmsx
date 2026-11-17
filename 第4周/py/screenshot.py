"""第 4 周 · 浏览器截图 + 页面自检工具（Chromium DevTools Protocol）

为什么不用 `msedge --screenshot`：
  1) 无头模式的 `--dump-dom` 走 GUI 子系统，PowerShell 抓不到 stdout，拿不到页面几何；
  2) 只看截图无法判断"面板有没有重叠/文字有没有溢出"，而这两件事恰恰是大屏评分点。
  所以用 CDP 起一个调试端口，直接 evaluate JS 取布局数据，再顺手截图。

依赖：websockets（streamlit 依赖里已有）、requests、本机 Edge/Chrome。

用法：
  python screenshot.py --url "http://127.0.0.1:8000/?debug=1" --out ../docs/images/screen.png
  python screenshot.py --url "http://127.0.0.1:8501" --out ../docs/images/streamlit.png --width 1600 --height 1000
  python screenshot.py --url ... --eval "document.getElementById('geomReport').textContent"
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from websockets.sync.client import connect

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str:
    for p in EDGE_CANDIDATES:
        if Path(p).exists():
            return p
    for name in ("msedge", "chrome", "chromium"):
        hit = shutil.which(name)
        if hit:
            return hit
    raise SystemExit("找不到 Edge/Chrome，可改用 --browser 指定路径")


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class DevTools:
    def __init__(self, browser: str, width: int, height: int, scale: float = 1.0):
        self.port = free_port()
        self.profile = tempfile.mkdtemp(prefix="cdp_profile_")
        self.proc = subprocess.Popen(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--remote-allow-origins=*",
                f"--remote-debugging-port={self.port}",
                f"--user-data-dir={self.profile}",
                f"--window-size={width},{height}",
                f"--force-device-scale-factor={scale}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.ws = None
        self._connect(width, height)

    def _connect(self, width: int, height: int) -> None:
        base = f"http://127.0.0.1:{self.port}"
        for _ in range(60):
            try:
                ver = requests.get(base + "/json/version", timeout=1).json()
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        else:
            raise SystemExit("浏览器调试端口没起来")
        # 新建一个标签页
        try:
            target = requests.put(base + "/json/new?about:blank", timeout=5).json()
        except Exception:  # noqa: BLE001
            target = requests.get(base + "/json/new?about:blank", timeout=5).json()
        self.ws = connect(target["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024)
        self.msg_id = 0
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Emulation.setDeviceMetricsOverride",
                  {"width": width, "height": height, "deviceScaleFactor": 0, "mobile": False})

    def call(self, method: str, params: dict | None = None, timeout: float = 90.0) -> dict:
        self.msg_id += 1
        mid = self.msg_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self.ws.recv(timeout=max(0.1, deadline - time.time()))
            msg = json.loads(raw)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method} 失败：{msg['error']}")
                return msg.get("result", {})
        raise TimeoutError(method)

    def goto(self, url: str, settle: float = 3.0) -> None:
        self.call("Page.navigate", {"url": url})
        time.sleep(settle)

    def js(self, expr: str):
        res = self.call("Runtime.evaluate", {
            "expression": expr, "returnByValue": True, "awaitPromise": True,
        })
        return res.get("result", {}).get("value")

    def shot(self, path: Path, full_page: bool = False) -> None:
        params = {"format": "png"}
        if full_page:
            params["captureBeyondViewport"] = True
        data = self.call("Page.captureScreenshot", params)["data"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(data))

    def close(self) -> None:
        try:
            if self.ws:
                self.ws.close()
        except Exception:  # noqa: BLE001
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", default=None, help="截图输出路径（.png）")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--settle", type=float, default=6.0, help="导航后等待秒数（Hive 慢，可给 20）")
    ap.add_argument("--eval", default=None, help="导航后执行的 JS 表达式，结果打印为 JSON")
    ap.add_argument("--browser", default=None)
    args = ap.parse_args()

    dev = DevTools(args.browser or find_browser(), args.width, args.height, args.scale)
    try:
        dev.goto(args.url, settle=args.settle)
        title = dev.js("document.title")
        print(f"[页面] {title}  ({args.url})")
        if args.eval:
            val = dev.js(args.eval)
            print("[执行结果]")
            print(json.dumps(val, ensure_ascii=False, indent=1) if not isinstance(val, str) else val)
        if args.out:
            out = Path(args.out)
            dev.shot(out)
            print(f"[截图] {out}  {out.stat().st_size} 字节")
    finally:
        dev.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())