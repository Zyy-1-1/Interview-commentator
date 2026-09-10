"""重试共用时间预算，不访问真实模型。"""
from types import SimpleNamespace

import httpx
import pytest
from openai import APIStatusError

from app import llm


def test_timeouts_share_one_retry_budget(monkeypatch):
    clock = [0.0]
    timeouts = []
    def create(**kwargs):
        timeouts.append(kwargs["timeout"])
        clock[0] += kwargs["timeout"]
        raise TimeoutError("synthetic timeout")
    monkeypatch.setattr(llm.settings, "llm_timeout_seconds", 25)
    monkeypatch.setattr(llm.settings, "llm_total_timeout_seconds", 40)
    monkeypatch.setattr(llm.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    with pytest.raises(RuntimeError):
        llm.chat_json("system", "synthetic input")
    assert timeouts == [25, 15]


def test_authentication_error_is_not_retried(monkeypatch):
    calls = []
    def create(**kwargs):
        calls.append(1)
        response = httpx.Response(401, request=httpx.Request("POST", "https://example.invalid"))
        raise APIStatusError("synthetic auth failure", response=response, body=None)
    monkeypatch.setattr(llm, "get_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    with pytest.raises(RuntimeError):
        llm.chat_json("system", "synthetic input")
    assert calls == [1]


def test_call_can_use_a_separate_timeout_budget(monkeypatch):
    clock = [0.0]
    timeouts = []

    def create(**kwargs):
        timeouts.append(kwargs["timeout"])
        clock[0] += kwargs["timeout"]
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(llm.time, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(
        llm,
        "get_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    with pytest.raises(RuntimeError):
        llm.chat_json(
            "system",
            "synthetic input",
            max_retries=1,
            timeout_seconds=90,
            total_timeout_seconds=180,
        )
    assert timeouts == [90, 90]
