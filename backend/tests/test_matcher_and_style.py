"""面试官人格 prompt + 简历匹配 Agent 测试(离线,mock LLM)。"""
import json

import pytest

from app.agents import matcher
from app.agents.interviewer.prompts import PERSONAS, build_system_prompt
from app.agents.interviewer.state import initial_state

DIMS = [{"name": "Python 编程", "type": "hard", "weight": 1.0, "keywords": ["asyncio"]}]


def test_persona_prompts_differ():
    systems = {
        s: build_system_prompt(DIMS, job_title="后端", style=s) for s in PERSONAS
    }
    assert len(set(systems.values())) == len(PERSONAS)
    for s, text in systems.items():
        assert PERSONAS[s]["desc"] in text
    # 输出协议与大纲不受人格影响(决策内核不变)
    for text in systems.values():
        assert "CONTINUE_DIMENSION" in text
        assert "Python 编程" in text


def test_unknown_style_falls_back_to_pro():
    assert (
        build_system_prompt(DIMS, style="不存在的风格")
        == build_system_prompt(DIMS, style="pro")
    )


def test_initial_state_carries_style_and_job_title():
    st = initial_state(
        interview_id=1, dimensions=DIMS, job_title="数据分析师", style="pressure"
    )
    assert st["style"] == "pressure"
    assert st["job_title"] == "数据分析师"


FAKE_MATCH = {
    "overall": 68,
    "summary": "技术栈基本匹配,缺高并发实战。",
    "dimension_scores": [
        {"name": "Python 编程", "resume_evidence": "多个 Python 项目", "score": 7}
    ],
    "highlights": ["项目经验真实"],
    "gaps": ["无高并发"],
}


def test_match_resume_to_job_ok(monkeypatch):
    monkeypatch.setattr(matcher, "chat_json", lambda **kw: FAKE_MATCH)
    result = matcher.match_resume_to_job(
        parsed_resume={"basic": {"name": "张三"}},
        resume_text=None,
        job_title="Python 后端",
        jd_text="需要 Python",
        dimensions=DIMS,
    )
    assert result["overall"] == 70
    assert result["dimension_scores"][0]["name"] == "Python 编程"


def test_match_resume_to_job_rejects_bad_output(monkeypatch):
    monkeypatch.setattr(matcher, "chat_json", lambda **kw: {"foo": 1})
    with pytest.raises(ValueError):
        matcher.match_resume_to_job(
            parsed_resume=None,
            resume_text="张三会 Python",
            job_title="x",
            jd_text="y",
            dimensions=DIMS,
        )


def test_matcher_clamps_scores_and_recomputes_overall(monkeypatch):
    monkeypatch.setattr(
        matcher,
        "chat_json",
        lambda **kw: {
            "overall": 100,
            "summary": "模型总分不可信",
            "dimension_scores": [
                {"name": "Python 编程", "resume_evidence": "Python", "score": 99}
            ],
            "highlights": [],
            "gaps": [],
        },
    )
    result = matcher.match_resume_to_job(
        parsed_resume=None,
        resume_text="Python",
        job_title="x",
        jd_text="y",
        dimensions=DIMS,
    )
    assert result["dimension_scores"][0]["score"] == 10
    assert result["overall"] == 100
