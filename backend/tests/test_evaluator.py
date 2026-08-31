"""评估 Agent 测试(mock chat_json,可离线运行)。

验证:报告结构透传、user prompt 包含岗位/维度/候选人原话、缺维度兜底抛错。
"""
import pytest

from app.agents import evaluator

DIMS = [
    {"name": "Python 编程", "type": "hard", "weight": 0.3, "keywords": ["Python", "asyncio"]},
    {"name": "沟通表达", "type": "soft", "weight": 0.2, "keywords": ["协作"]},
]

FAKE_REPORT = {
    "summary_score": 78,
    "suggestion": "建议进入二面",
    "dimensions": [{"name": "Python 编程", "score": 8.0, "evidence": ["候选人原话:用 asyncio 优化"]}],
    "strengths": ["技术基础扎实"],
    "risks": ["行为维度考察不充分"],
    "next_step_questions": ["二面重点考察系统设计"],
}


def _capture_chat_json(monkeypatch):
    """monkeypatch evaluator.chat_json,捕获调用并返回 FAKE_REPORT。"""
    calls = {}

    def fake(system, user, **kw):
        calls["system"] = system
        calls["user"] = user
        return FAKE_REPORT

    monkeypatch.setattr(evaluator, "chat_json", fake)
    return calls


def test_evaluate_returns_report(monkeypatch):
    calls = _capture_chat_json(monkeypatch)
    report = evaluator.evaluate(
        job_title="Python 后端",
        dimensions=DIMS,
        parsed_resume='{"基础": "3 年"}',
        messages=[{"role": "agent", "text": "自我介绍?"}, {"role": "candidate", "text": "我是张三"}],
    )
    assert report == FAKE_REPORT
    # user prompt 应包含岗位与面试记录标签
    assert "Python 后端" in calls["user"]
    assert "应聘者" in calls["user"]


def test_evaluate_prompt_contains_original_words(monkeypatch):
    calls = _capture_chat_json(monkeypatch)
    evaluator.evaluate(
        job_title="Python 后端",
        dimensions=DIMS,
        parsed_resume=None,
        messages=[
            {"role": "agent", "text": "介绍一下你的项目"},
            {"role": "candidate", "text": "我用 asyncio 把接口 QPS 优化到 300"},
        ],
    )
    # 证据来源要求:原话必须出现在喂给评估的输入里
    assert "asyncio" in calls["user"]
    assert "QPS" in calls["user"]


def test_evaluate_missing_dimensions_raises(monkeypatch):
    monkeypatch.setattr(evaluator, "chat_json", lambda system, user, **kw: {})
    with pytest.raises(ValueError, match="评估未产出有效维度打分"):
        evaluator.evaluate(job_title="x", dimensions=DIMS, parsed_resume=None, messages=[])
