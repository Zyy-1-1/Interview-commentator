"""LLM 封装:千问 DashScope(OpenAI 兼容协议)。

对外只暴露两个函数:
- chat_text(): 自由文本
- chat_json(): 强制 JSON 输出,解析失败自动重试(≤2 次)
所有 Agent 都通过这里调用,便于统一重试/日志/换模型。
"""
import json
import logging
import re
import time
from typing import Any, Optional

from openai import APIStatusError, OpenAI

from .config import settings

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """惰性创建 OpenAI client(避免无 Key 时启动即报错)。"""
    global _client
    if not settings.dashscope_api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY")
    if _client is None:
        _client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            timeout=settings.llm_timeout_seconds,
            # 由 chat_json 统一控制重试次数，避免 SDK 与业务层叠加重试。
            max_retries=0,
        )
    return _client


def _extract_json(text: str) -> dict:
    """从模型输出中提取 JSON 对象。

    优先 json.loads;失败则尝试剥离 ```json ... ``` 代码块后重试。
    """
    def reject_constant(value: str):
        raise ValueError("模型输出包含非有限数值")

    def parse_object(content: str) -> dict:
        value = json.loads(content, parse_constant=reject_constant)
        if not isinstance(value, dict):
            raise ValueError("模型输出必须为 JSON 对象")
        return value

    try:
        return parse_object(text)
    except json.JSONDecodeError:
        pass
    # 处理被 ```json 包裹的输出
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return parse_object(m.group(1))
    # 最后尝试从第一个 { 到最后一个 } 截取
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return parse_object(text[start : end + 1])
    raise ValueError("无法从模型输出解析 JSON 对象")


def chat_text(
    system: str,
    user: str,
    temperature: float = 0.7,
) -> str:
    started = time.perf_counter()
    resp = get_client().chat.completions.create(
        model=settings.dashscope_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    _log_usage("chat_text", resp, started)
    return resp.choices[0].message.content or ""


def chat_json(
    system: str,
    user: str,
    temperature: float = 0.2,
    max_retries: int = 2,
) -> dict[str, Any]:
    """结构化调用共用重试预算，剩余时间收紧每次网络超时。"""
    client = get_client()
    deadline = time.perf_counter() + settings.llm_total_timeout_seconds
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        started = time.perf_counter()
        remaining = deadline - started
        if remaining <= 0:
            break
        try:
            resp = client.chat.completions.create(
                timeout=min(settings.llm_timeout_seconds, remaining),
                model=settings.dashscope_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            _log_usage("chat_json", resp, started, attempt=attempt + 1)
            return _extract_json(resp.choices[0].message.content or "{}")
        except Exception as e:  # noqa: BLE001  解析失败/网络错误统一重试
            last_err = e
            logger.warning("chat_json 第 %s 次失败: %s", attempt + 1, type(e).__name__)
            if isinstance(e, APIStatusError) and e.status_code < 500 and e.status_code != 429:
                break  # 鉴权/参数错误重试也不会成功。
    raise RuntimeError(f"模型请求失败: {type(last_err).__name__}") from None


def _log_usage(operation: str, response: Any, started: float, *, attempt: int = 1) -> None:
    """只记录延迟与 token 数，不记录简历/JD/对话正文。"""
    usage = getattr(response, "usage", None)
    logger.info(
        "LLM %s 完成: model=%s attempt=%s latency_ms=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
        operation,
        settings.dashscope_model,
        attempt,
        round((time.perf_counter() - started) * 1000),
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
        getattr(usage, "total_tokens", None),
    )
