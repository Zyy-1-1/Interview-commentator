"""LLM 封装:DeepSeek(OpenAI 兼容协议)。

对外只暴露两个函数:
- chat_text(): 自由文本
- chat_json(): 强制 JSON 输出,解析失败自动重试(≤2 次)
所有 Agent 都通过这里调用,便于统一重试/日志/换模型。
"""
import json
import logging
import re
from typing import Any, Optional

from openai import OpenAI

from .config import settings

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """惰性创建 OpenAI client(避免无 Key 时启动即报错)。"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.deepseek_api_key or "sk-empty",
            base_url=settings.deepseek_base_url,
        )
    return _client


def _extract_json(text: str) -> dict:
    """从模型输出中提取 JSON 对象。

    优先 json.loads;失败则尝试剥离 ```json ... ``` 代码块后重试。
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 处理被 ```json 包裹的输出
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # 最后尝试从第一个 { 到最后一个 } 截取
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError(f"无法从模型输出解析 JSON: {text[:200]}")


def chat_text(
    system: str,
    user: str,
    temperature: float = 0.7,
) -> str:
    resp = get_client().chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def chat_json(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_retries: int = 2,
) -> dict[str, Any]:
    """强制模型输出 JSON,失败自动重试。用于结构化抽取/决策协议。"""
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = get_client().chat.completions.create(
                model=settings.deepseek_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return _extract_json(resp.choices[0].message.content or "{}")
        except Exception as e:  # noqa: BLE001  解析失败/网络错误统一重试
            last_err = e
            logger.warning("chat_json 第 %s 次失败: %s", attempt + 1, e)
    raise RuntimeError(f"chat_json 多次失败: {last_err}")
