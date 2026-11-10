"""本地模拟大模型端点（仅用于联调测试，不参与交付）

为什么需要它：
  真实 Key 申请下来之前，没法验证"配好 .env 之后代码到底能不能跑"。
  这个脚本起一个最小的 OpenAI 兼容 HTTP 服务，返回固定的假响应，
  用来证明 llm_client / nl2sql / ai_insight 的**请求构造、响应解析、
  SQL 清洗、安全校验、结果执行**整条链路是通的。

  它返回的内容是写死的假数据，**不代表任何模型能力**。
  真实效果必须配真 Key 才能验证。

用法：
  python tools/mock_llm_server.py            # 默认 127.0.0.1:18080
  python tools/mock_llm_server.py 18081      # 换端口

然后另开一个终端：
  $env:LLM_API_KEY="test-key"
  $env:LLM_BASE_URL="http://127.0.0.1:18080/v1"
  $env:LLM_MODEL="mock-model"
  python llm_client.py
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 针对 NL2SQL 的提问，故意返回**带 ``` 围栏**的 SQL，
# 用来验证 nl2sql.cleanse_sql() 能不能把围栏去掉。
NL2SQL_REPLY = """```sql
select stat_month, province, cast(round(gmv, 2) as decimal(18, 2)) as gmv, order_cnt
from ydsh_ads.ads_province_sales
where province = '广东省' and stat_month = '2024-12'
```"""

INSIGHT_REPLY = (
    "[模拟响应] 2024 年日 GMV 波动以订单量驱动为主：1 月 20 日与 7 月 28 日订单量降至"
    "全年均值 56%，客单价基本持平，属「量跌」；10 月 8 日订单量正常但客单价降至 67%，"
    "属「价跌」。建议优先排查量跌日的流量来源，价跌日核查促销与品类结构。"
)


def build_reply(payload: dict) -> str:
    """按提问内容返回不同的假答案，方便一次跑通三个脚本。"""
    text = " ".join(
        m.get("content", "") for m in payload.get("messages", []) if isinstance(m.get("content"), str)
    )
    if "Hive SQL" in text or "NL2SQL" in text:
        return NL2SQL_REPLY
    if "经营分析摘要" in text or "数据分析师" in text:
        return INSIGHT_REPLY
    return "连通"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            payload = {}

        reply = build_reply(payload)
        body = {
            "id": f"chatcmpl-mock-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model", "mock-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": max(1, len(raw) // 4),
                "completion_tokens": max(1, len(reply) // 4),
                "total_tokens": max(2, (len(raw) + len(reply)) // 4),
            },
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        print(f"  <- {payload.get('model', '?')} | 返回 {len(reply)} 字符")

    def do_GET(self) -> None:  # noqa: N802
        data = b'{"status":"mock server up"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # 关掉默认访问日志，输出干净些
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18080
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("=" * 56)
    print(f"模拟大模型端点已启动： http://127.0.0.1:{port}/v1")
    print("返回的是写死的假数据，仅用于验证链路，不代表模型能力。")
    print("Ctrl+C 停止")
    print("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()