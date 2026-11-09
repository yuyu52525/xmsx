"""第 3 周 · 大模型 API 最小可用调用 + 密钥管理

设计要点：
  1. Key 只从 .env / 环境变量读取，源码里不出现任何真实 Key；
  2. 缺 Key 时抛 LLMNotConfigured，而不是静默返回空串——
     让调用方明确知道"是没配 Key"，不是"模型返回为空"；
  3. 提供 has_key() 供上层做降级判断；
  4. selftest() 打印一次真实调用的请求/响应结构，用于验证连通性。

用法：
  python llm_client.py            # 连通性自检
  python llm_client.py --mask     # 只看 Key 是否就位（不调用）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"


class LLMNotConfigured(RuntimeError):
    """没有配置 API Key 时抛出。"""


def load_config() -> None:
    """加载 .env（不覆盖已存在的系统环境变量）。"""
    load_dotenv(ENV_PATH, override=False)


def _api_key() -> str:
    load_config()
    return os.getenv("DEEPSEEK_API_KEY", "").strip()


def has_key() -> bool:
    key = _api_key()
    return bool(key) and not key.startswith("sk-your")


def mask_key(key: str | None = None) -> str:
    """脱敏显示 Key：只留前 6 位与后 4 位。"""
    key = key or _api_key()
    if not key:
        return "(未配置)"
    if len(key) <= 12:
        return key[:3] + "***"
    return f"{key[:6]}...{key[-4:]}"


def get_client():
    """构造 OpenAI 兼容客户端（DeepSeek）。"""
    if not has_key():
        raise LLMNotConfigured(
            f"未找到可用的 DEEPSEEK_API_KEY。\n"
            f"请复制 {ENV_PATH.parent / '.env.example'} 为 .env 并填入真实 Key。"
        )
    from openai import OpenAI

    load_config()
    return OpenAI(
        api_key=_api_key(),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        timeout=60,
    )


def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024) -> str:
    """发一次对话请求，返回纯文本。messages 为 OpenAI 格式。"""
    client = get_client()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def selftest() -> int:
    """最小化连通性验证：一次调用 + 返回格式检查。"""
    print("=" * 52)
    print("大模型 API 连通性自检")
    print("=" * 52)
    print(f".env 路径      : {ENV_PATH}  ({'存在' if ENV_PATH.exists() else '不存在'})")
    print(f"DEEPSEEK_API_KEY: {mask_key()}")
    print(f"DEEPSEEK_MODEL  : {os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')}")
    if not has_key():
        print("\n[结论] 未配置 Key，跳过真实调用。")
        print("       复制 .env.example 为 .env 并填写 Key 后重跑本脚本。")
        return 2

    resp = get_client().chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        messages=[{"role": "user", "content": "只回复两个字：连通"}],
        temperature=0,
        max_tokens=16,
    )
    content = resp.choices[0].message.content
    print("\n--- 返回结构 ---")
    print(f"id      : {resp.id}")
    print(f"model   : {resp.model}")
    print(f"choices : {len(resp.choices)} 个")
    print(f"finish  : {resp.choices[0].finish_reason}")
    print(f"内容    : {content!r}")
    print(f"usage   : prompt={resp.usage.prompt_tokens} completion={resp.usage.completion_tokens}")
    ok = isinstance(content, str) and len(content) > 0
    print(f"\n[结论] {'连通正常，返回格式符合预期' if ok else '返回内容为空，需检查模型名/额度'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--mask" in sys.argv:
        load_config()
        print(f"Key 已配置：{has_key()}　脱敏：{mask_key()}")
        raise SystemExit(0 if has_key() else 2)
    raise SystemExit(selftest())