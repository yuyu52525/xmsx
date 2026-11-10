"""第 3 周 · 大模型 API 调用 + 密钥管理（多供应商通用）

为什么做成"通用"而不是写死 DeepSeek：
  作业/答辩环境经常换 Key 来源（官方申请慢、免费额度到期、学校只给某家），
  如果代码里写死 base_url 和模型名，换一家就要改代码。
  这里统一成 3 个环境变量，任何 OpenAI 兼容服务都能直接用：

      LLM_API_KEY    密钥
      LLM_BASE_URL   接口地址
      LLM_MODEL      模型名

  同时兼容旧的 DEEPSEEK_* 变量名，老配置不用改。

支持的常见供应商（都兼容 OpenAI 协议）：
  - DeepSeek 官方   https://api.deepseek.com                          deepseek-chat
  - 智谱 GLM        https://open.bigmodel.cn/api/paas/v4               glm-4-flash（免费）
  - 硅基流动        https://api.siliconflow.cn/v1                      Qwen/Qwen2.5-7B-Instruct
  - 阿里百炼        https://dashscope.aliyuncs.com/compatible-mode/v1  qwen-plus
  - 本地 Ollama     http://localhost:11434/v1                          qwen2.5:7b

用法：
  python llm_client.py            # 连通性自检（打印返回结构与 usage）
  python llm_client.py --mask     # 只看 Key 是否就位，不调用
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
# 用量记账（本地文件，已在 .gitignore 中排除 *.log）
USAGE_LOG = Path(__file__).resolve().parent.parent / "evidence" / "llm_usage.log"

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class LLMNotConfigured(RuntimeError):
    """没有配置 API Key 时抛出。"""


def load_config() -> None:
    """加载 .env（不覆盖已存在的系统环境变量）。"""
    load_dotenv(ENV_PATH, override=False)


def _pick(*names: str, default: str = "") -> str:
    """按顺序取第一个非空环境变量，便于新旧变量名共存。"""
    for name in names:
        val = os.getenv(name, "").strip()
        if val:
            return val
    return default


def _api_key() -> str:
    load_config()
    return _pick("LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ZHIPU_API_KEY")


def base_url() -> str:
    load_config()
    return _pick("LLM_BASE_URL", "DEEPSEEK_BASE_URL", "OPENAI_BASE_URL",
                 default=DEFAULT_BASE_URL)


def model_name() -> str:
    load_config()
    return _pick("LLM_MODEL", "DEEPSEEK_MODEL", default=DEFAULT_MODEL)


def has_key() -> bool:
    key = _api_key()
    return bool(key) and not key.startswith(("sk-your", "your-", "<"))


def mask_key(key: str | None = None) -> str:
    """脱敏显示 Key：只留前 6 位与后 4 位。"""
    key = key or _api_key()
    if not key:
        return "(未配置)"
    if len(key) <= 12:
        return key[:3] + "***"
    return f"{key[:6]}...{key[-4:]}"


def get_client():
    """构造 OpenAI 兼容客户端。本地 Ollama 不需要真 Key，传占位串即可。"""
    if not has_key():
        raise LLMNotConfigured(
            f"未找到可用的 API Key（LLM_API_KEY / DEEPSEEK_API_KEY）。\n"
            f"请复制 {ENV_PATH.parent / '.env.example'} 为 .env 并填入真实 Key。"
        )
    from openai import OpenAI

    return OpenAI(api_key=_api_key(), base_url=base_url(), timeout=60)


def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024) -> str:
    """发一次对话请求，返回纯文本。messages 为 OpenAI 格式。"""
    client = get_client()
    resp = client.chat.completions.create(
        model=model_name(),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    _log_usage(resp)
    return resp.choices[0].message.content


def _log_usage(resp) -> None:
    """把每次调用的 token 用量追加到 evidence/llm_usage.log。

    「免费」指的是不扣钱，不是不消耗 token——额度、QPS 限制依然存在。
    记下来才能回答「跑一遍到底用多少」。
    """
    try:
        from datetime import datetime

        u = getattr(resp, "usage", None)
        if u is None:
            return
        p = getattr(u, "prompt_tokens", 0) or 0
        c = getattr(u, "completion_tokens", 0) or 0
        t = getattr(u, "total_tokens", None) or (p + c)
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{model_name()}\t{p}\t{c}\t{t}\n")
        print(f"  [用量] 输入 {p} + 输出 {c} = {t} tokens")
    except Exception:  # noqa: BLE001  记账失败不影响主流程
        pass


def print_usage() -> None:
    """汇总本地用量记录（不代表服务商账单，仅供估算）。"""
    if not USAGE_LOG.exists():
        print("暂无用量记录。跑一次 `python llm_client.py` 或 `python nl2sql.py \"问题\"` 后就有了。")
        return
    rows = [ln.split("\t") for ln in USAGE_LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
    tot_p = sum(int(r[2]) for r in rows if len(r) >= 5)
    tot_c = sum(int(r[3]) for r in rows if len(r) >= 5)
    print("=" * 56)
    print("本地用量汇总（不完全等于服务商账单，仅供估算）")
    print("=" * 56)
    print(f"调用次数      : {len(rows)}")
    print(f"累计输入      : {tot_p:,} tokens")
    print(f"累计输出      : {tot_c:,} tokens")
    print(f"累计合计      : {tot_p + tot_c:,} tokens")
    print(f"明细文件      : {USAGE_LOG}")
    print("\n最近 5 次：")
    for r in rows[-5:]:
        if len(r) >= 5:
            print(f"  {r[0]}  {r[1]:<24} 入 {int(r[2]):>5}  出 {int(r[3]):>5}")


def selftest() -> int:
    """最小化连通性验证：一次调用 + 返回格式检查 + 常见错误码提示。"""
    print("=" * 56)
    print("大模型 API 连通性自检")
    print("=" * 56)
    print(f".env 路径   : {ENV_PATH}  ({'存在' if ENV_PATH.exists() else '不存在'})")
    print(f"API Key     : {mask_key()}")
    print(f"Base URL    : {base_url()}")
    print(f"模型        : {model_name()}")

    if not has_key():
        print("\n[结论] 未配置 Key，跳过真实调用。")
        print("       复制 .env.example 为 .env 并填写 Key 后重跑本脚本。")
        return 2

    from openai import (APIConnectionError, APIStatusError, AuthenticationError,
                        NotFoundError, RateLimitError)

    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=model_name(),
            messages=[{"role": "user", "content": "只回复两个字：连通"}],
            temperature=0,
            max_tokens=16,
        )
    except AuthenticationError:
        print("\n[结论] 认证失败（401）：Key 不对、已失效，或与当前 Base URL 不匹配。")
        return 1
    except NotFoundError:
        print(f"\n[结论] 模型不存在（404）：LLM_MODEL={model_name()!r} 在这家供应商下不可用，"
              f"请核对模型名。")
        return 1
    except RateLimitError as exc:
        print(f"\n[结论] 被限流或额度用尽（429）：{exc}")
        return 1
    except APIConnectionError as exc:
        print(f"\n[结论] 连不上 {base_url()}：{exc}\n"
              f"       本地 Ollama 请确认已 `ollama serve`；云端请检查网络/代理。")
        return 1
    except APIStatusError as exc:
        print(f"\n[结论] 服务端返回 {exc.status_code}：{exc.message}")
        return 1

    content = resp.choices[0].message.content
    print("\n--- 返回结构 ---")
    print(f"id      : {resp.id}")
    print(f"model   : {resp.model}")
    print(f"choices : {len(resp.choices)} 个")
    print(f"finish  : {resp.choices[0].finish_reason}")
    print(f"内容    : {content!r}")
    if resp.usage:
        print(f"usage   : prompt={resp.usage.prompt_tokens} "
              f"completion={resp.usage.completion_tokens}")
    ok = isinstance(content, str) and len(content) > 0
    print(f"\n[结论] {'连通正常，返回格式符合预期' if ok else '返回内容为空，需检查模型名/额度'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--usage" in sys.argv:
        load_config()
        print_usage()
        raise SystemExit(0)
    if "--mask" in sys.argv:
        load_config()
        print(f"Key 已配置：{has_key()}　脱敏：{mask_key()}")
        raise SystemExit(0 if has_key() else 2)
    raise SystemExit(selftest())