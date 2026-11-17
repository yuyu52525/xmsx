"""把 /api/all 的结果存成大屏的离线快照

用途：现场演示如果后端临时挂了（或评委电脑没连 Docker），
      `web/assets/app.js` 会自动回落到这份快照，大屏仍然能完整展示——只是数据停在生成时刻。
     页面状态栏会明确标注"离线快照"，不会让人误以为是实时数据。

用法：
  python dump_snapshot.py                      # 从本机 8000 端口取
  python dump_snapshot.py --api http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "web" / "assets" / "snapshot.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    url = args.api.rstrip("/") + "/api/all?nocache=1"
    print(f"拉取 {url} ...")
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    data = r.json()
    data["source"] = "snapshot"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"已写入 {OUT}  ({OUT.stat().st_size:,} 字节)")
    print(f"后端：{data.get('backend')}   生成耗时：{data.get('elapsed_ms')} ms")
    for k in ("kpi", "month", "category", "province", "paytype",
              "hour_category", "store", "rfm", "channel", "daily"):
        v = data.get(k)
        print(f"  {k:<14} {len(v) if isinstance(v, list) else '-'} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())