"""离线回归：模型格式异常不能变成接口 500 或伪造有效数值。"""
import json
import math

import pytest
from pydantic import ValidationError

from app.agents import jd_analyzer, matcher
from app.agents.interviewer.graph import build_graph
from app.agents.interviewer.state import initial_state
from app.agents.output_validation import normalize_resume
from app.llm import _extract_json


@pytest.mark.parametrize("text", ["null", "[]", '[{"name":"test"}]', '{"score":NaN}', '{"score":Infinity}'])
def test_json_protocol_rejects_non_object_and_non_finite_values(text):
    with pytest.raises(ValueError):
        _extract_json(text)


def test_json_parser_preserves_valid_wrapped_objects():
    assert _extract_json('说明：{"nested":{"items":[1,2]}}') == {"nested": {"items": [1, 2]}}


def test_nullable_resume_sections_have_safe_defaults():
    parsed = normalize_resume({"basic": None, "skills": None, "projects": None})
    assert parsed["basic"]["name"] is None
    assert parsed["skills"]["programming"] == []
    assert parsed["projects"] == []


@pytest.mark.parametrize("raw", [
    {"basic": []}, {"skills": {"programming": {}}},
    {"projects": [{"achievements": ["not text"]}]},
])
def test_invalid_nested_resume_structure_is_rejected(raw):
    with pytest.raises(ValidationError):
        normalize_resume(raw)


@pytest.mark.parametrize("raw", [
    None, [], {"next_question": ["bad"]}, {"next_question": ""},
    {"next_question": "valid question", "assess": []},
])
def test_invalid_decision_uses_a_valid_fallback_turn(raw):
    graph = build_graph(lambda system, user: raw)
    state = initial_state(interview_id=1, dimensions=[{"name": "Python", "type": "hard"}])
    result = graph.invoke(state)
    assert isinstance(result["history"][-1]["text"], str)
    assert result["history"][-1]["text"]
    assert result["finished"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True, "NaN"])
def test_non_finite_weights_and_match_scores_cannot_become_full_marks(value):
    dims = jd_analyzer._normalize_dimensions([
        {"name": "Python", "weight": value},
        {"name": "SQL", "weight": 1},
    ])
    assert dims[0]["weight"] == 0
    assert math.isclose(sum(d["weight"] for d in dims), 1)
    report = matcher._normalize_match(
        {"dimension_scores": [{"name": "Python", "score": value}]},
        [{"name": "Python", "weight": 1}],
    )
    assert report["overall"] == 0
    json.dumps(report, allow_nan=False)
