"""证据、评分和覆盖率的对抗性回归；只使用合成记录。"""
import pytest

from app.agents import evaluator

DIMS = [{"name": "Python", "weight": 0.6}, {"name": "Communication", "weight": 0.4}]


def run_report(monkeypatch, raw, messages, dimensions=DIMS):
    monkeypatch.setattr(evaluator, "chat_json", lambda *args, **kwargs: raw)
    return evaluator.evaluate(
        job_title="Synthetic job", dimensions=dimensions, parsed_resume=None, messages=messages,
    )


def test_partial_coverage_is_not_a_zero_or_a_complete_score(monkeypatch):
    report = run_report(monkeypatch, {"dimensions": [
        {"name": "Python", "score": 8, "evidence_refs": [{"message_id": 2, "quote": "used asyncio"}]},
    ]}, [{"id": 2, "role": "candidate", "dimension": "Python", "text": "I used asyncio."}])
    assert report["summary_score"] is None
    assert report["assessed_score"] == 80
    assert report["dimensions"][1]["score"] is None
    assert report["dimensions"][1]["status"] == "not_assessed"
    assert report["coverage"] == {"assessed": 1, "total": 2, "percent": 50, "weighted_percent": 60}


@pytest.mark.parametrize("score", [float("nan"), float("inf"), "NaN", True, [], None])
def test_invalid_scores_are_unscored_even_with_a_valid_quote(monkeypatch, score):
    report = run_report(monkeypatch, {"dimensions": [
        {"name": "Python", "score": score, "evidence": ["I do not know"]},
    ]}, [{"id": 2, "role": "candidate", "dimension": "Python", "text": "I do not know"}])
    assert report["dimensions"][0]["status"] == "insufficient_evidence"
    assert report["dimensions"][0]["score"] is None
    assert report["summary_score"] is None


def test_a_poor_answer_can_receive_zero_with_its_actual_evidence(monkeypatch):
    report = run_report(monkeypatch, {"dimensions": [
        {"name": "Python", "score": 0, "evidence": ["I do not know"]},
    ]}, [{"id": 2, "role": "candidate", "dimension": "Python", "text": "I do not know"}], DIMS[:1])
    assert report["dimensions"][0]["status"] == "scored"
    assert report["summary_score"] == 0


@pytest.mark.parametrize("ref", [
    {"message_id": 99, "quote": "actual answer"},
    {"message_id": 3, "quote": "other dimension"},
    {"message_id": 1, "quote": "question text"},
    {"message_id": 2, "quote": "fabricated words"},
])
def test_reference_must_match_role_message_and_dimension(monkeypatch, ref):
    report = run_report(monkeypatch, {"dimensions": [
        {"name": "Python", "score": 10, "evidence_refs": [ref]},
    ]}, [
        {"id": 1, "role": "agent", "dimension": "Python", "text": "question text"},
        {"id": 2, "role": "candidate", "dimension": "Python", "text": "actual answer"},
        {"id": 3, "role": "candidate", "dimension": "Communication", "text": "other dimension"},
    ])
    assert report["dimensions"][0]["evidence_refs"] == []
    assert report["dimensions"][0]["score"] is None


def test_quote_cannot_span_two_separate_answers(monkeypatch):
    report = run_report(monkeypatch, {"dimensions": [
        {"name": "Python", "score": 10, "evidence": ["first\nsecond"]},
    ]}, [
        {"id": 2, "role": "candidate", "dimension": "Python", "text": "first"},
        {"id": 4, "role": "candidate", "dimension": "Python", "text": "second"},
    ])
    assert report["dimensions"][0]["evidence_refs"] == []


def test_later_answer_details_are_in_prompt_and_truncation_is_disclosed(monkeypatch):
    calls = []
    def model(system, user, **kwargs):
        calls.append(user)
        return {"dimensions": [{"name": "Python", "score": 8, "evidence": ["important result"]}]}
    monkeypatch.setattr(evaluator, "chat_json", model)
    message = {"id": 2, "role": "candidate", "dimension": "Python", "text": "x" * 600 + " important result"}
    complete = evaluator.evaluate(job_title="x", dimensions=DIMS[:1], parsed_resume=None, messages=[message])
    assert "important result" in calls[0]
    assert complete["summary_score"] == 80
    message["text"] += "x" * 5000
    partial = evaluator.evaluate(job_title="x", dimensions=DIMS[:1], parsed_resume=None, messages=[message])
    assert partial["input_truncated"] is True
    assert partial["summary_score"] is None
    assert partial["coverage"]["assessed"] == 1
