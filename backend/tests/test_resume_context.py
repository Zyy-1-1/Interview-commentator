"""简历上下文的出处、大小、会话隔离和提问输入回归。"""
import json
from pathlib import Path

import pytest

from app.agents.interviewer.graph import build_graph, _transition_question
from app.agents.interviewer.prompts import build_system_prompt, build_user_prompt
from app.agents.interviewer.resume_context import build_resume_facts, project_anchor, MAX_CONTEXT_CHARS
from app.agents.interviewer.state import initial_state, ACTION_NEXT_DIMENSION

FIXTURES = Path(__file__).parent / "fixtures"
DIMS = [{"name": "Python", "type": "hard", "keywords": ["asyncio"], "weight": 1}]


def test_facts_have_original_offsets_and_exclude_ungrounded_claims():
    source = (FIXTURES / "resume_async.md").read_text(encoding="utf-8")
    parsed = {
        "basic": {"name": "PRIVATE NAME", "age": "22"},
        "projects": [{"name": "校园通知平台", "tech_stack": ["asyncio"], "achievements": "invented achievement"}],
    }
    facts = build_resume_facts(parsed, source)
    assert facts
    for fact in facts:
        assert source[fact["source_start"]:fact["source_end"]] == fact["text"]
    assert "invented" not in json.dumps(facts)
    assert "PRIVATE" not in json.dumps(facts)
    assert sum(len(f["text"]) for f in facts) <= MAX_CONTEXT_CHARS


@pytest.mark.parametrize("parsed, source", [(None, None), ("bad JSON", "text"), ({"projects": None}, "text")])
def test_missing_or_legacy_resume_is_safe(parsed, source):
    assert build_resume_facts(parsed, source) == []


@pytest.mark.parametrize("style", ["pro", "friendly", "pressure"])
def test_same_resume_context_is_available_to_all_styles(style):
    source = (FIXTURES / "resume_async.md").read_text(encoding="utf-8")
    facts = build_resume_facts({"projects": [{"name": "校园通知平台", "tech_stack": ["asyncio"]}]}, source)
    state = initial_state(interview_id=1, dimensions=DIMS, style=style, resume_facts=facts)
    calls = []
    def judge(system, user):
        calls.append((system, user))
        return {"next_question": "请简要介绍项目经历", "action": "CONTINUE_DIMENSION"}
    state = build_graph(judge).invoke(state)
    assert "校园通知平台" in calls[0][1]
    assert "source_start" in calls[0][1]
    assert "不代表能力已经核验" in calls[0][0]
    state["candidate_reply"] = "我负责了其中的任务重试"
    assert "校园通知平台" in build_user_prompt(state)
    assert state["resume_facts"] == facts


def test_large_resume_facts_are_bounded_without_losing_source_positions():
    projects = [{"name": f"Project {i} " + "x" * 500, "achievements": f"Result {i} " + "y" * 900,
                 "tech_stack": [f"Tool {i}-{j} " + "z" * 500 for j in range(4)]} for i in range(3)]
    source = "\n".join(value for project in projects for value in [
        project["name"], project["achievements"], *project["tech_stack"],
    ])
    facts = build_resume_facts({"projects": projects}, source)
    assert sum(len(f["text"]) for f in facts) == MAX_CONTEXT_CHARS
    assert len(facts) <= 16
    for fact in facts:
        assert source[fact["source_start"]:fact["source_end"]] == fact["text"]


def test_transition_selects_the_relevant_project():
    source = "校园通知平台 Python asyncio。课程预约系统 MySQL EXPLAIN。"
    parsed = {"projects": [
        {"name": "校园通知平台", "tech_stack": ["asyncio"]},
        {"name": "课程预约系统", "tech_stack": ["MySQL", "EXPLAIN"]},
    ]}
    facts = build_resume_facts(parsed, source)
    target = {"name": "数据库", "type": "hard", "keywords": ["MySQL", "EXPLAIN"]}
    assert project_anchor({"resume_facts": facts}, target) == "课程预约系统"
    state = initial_state(interview_id=1, dimensions=[DIMS[0], target], resume_facts=facts)
    question = _transition_question(state, ACTION_NEXT_DIMENSION)
    assert "课程预约系统" in question
    assert "校园通知平台" not in question
    assert project_anchor(state, {"name": "网络安全", "type": "hard", "keywords": ["TLS"]}) == ""
