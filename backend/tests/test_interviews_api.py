"""答题闭环 API 集成测试(临时 SQLite + mock LLM,可离线运行)。

验证:创建面试 → 开场白 → 多轮回答(追问/推进/收尾)→ state 持久化 → 消息留痕 → 结束后拒绝继续。
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from app.agents import evaluator
from app.agents.interviewer.graph import build_graph
from app.agents.interviewer.state import (
    ACTION_CLOSING,
    ACTION_CONTINUE_DIMENSION,
    ACTION_GO_BEHAVIORAL,
    ACTION_GO_CANDIDATE_QA,
    ACTION_NEXT_DIMENSION,
)
from app.api import interviews as interviews_api
from app.db import Base, get_db
from app.main import app
from app.models import Candidate, Interview, Job
from app.security import hash_candidate_token

ACCESS_TOKEN = "candidate-test-token"
CANDIDATE_HEADERS = {"X-Candidate-Token": ACCESS_TOKEN}

FAKE_REPORT = {
    "summary_score": 78,
    "suggestion": "建议进入二面",
    "dimensions": [
        {"name": "Python 编程", "score": 8.0, "evidence": ["用 asyncio 优化过接口"]},
        {"name": "沟通表达", "score": 7.0, "evidence": ["曾经跨部门协作过一个项目"]},
    ],
    "strengths": ["技术扎实"],
    "risks": ["行为维度不足"],
    "next_step_questions": ["二面问系统设计"],
}

DIMS = [
    {"name": "Python 编程", "type": "hard", "weight": 0.3, "keywords": ["Python", "asyncio"]},
    {"name": "沟通表达", "type": "soft", "weight": 0.2, "keywords": ["协作"]},
]


def make_sequence(actions, next_qs):
    """按调用顺序返回固定 action / 下一问的 fake judge。"""
    calls = []

    def judge(system, user):
        calls.append({"system": system, "user": user})
        i = len(calls) - 1
        return {
            "thinking": "t",
            "assess": {"answered": True, "quality": 7, "issue": "i", "evidence": "e"},
            "next_question": next_qs[min(i, len(next_qs) - 1)],
            "action": actions[min(i, len(actions) - 1)],
        }

    return judge, calls


@pytest.fixture
def test_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestSession
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def _seed(test_session) -> dict:
    with test_session() as s:
        job = Job(title="Python 后端", jd_text="需要 Python 经验", dimensions=json.dumps(DIMS, ensure_ascii=False))
        cand = Candidate(name="张三", access_token_hash=hash_candidate_token(ACCESS_TOKEN))
        s.add_all([job, cand])
        s.commit()
        return {"job_id": job.id, "candidate_id": cand.id}


def test_full_interview_loop(test_db, monkeypatch):
    ids = _seed(test_db)
    # 开场 → 硬技能追问 → 行为维度 → 候选人提问 → 收尾。
    judge, calls = make_sequence(
        actions=[
            ACTION_CONTINUE_DIMENSION,
            ACTION_CONTINUE_DIMENSION,
            ACTION_NEXT_DIMENSION,
            ACTION_GO_CANDIDATE_QA,
            ACTION_CLOSING,
        ],
        next_qs=[
            "请先自我介绍",
            "追问:说细节",
            "模型给出的推进问题",
            "你有什么想了解的吗?",
            "这个问题我简要回答如下。",
        ],
    )
    graph = build_graph(judge)
    monkeypatch.setattr(interviews_api, "_get_graph", lambda: graph)
    # 收尾自动评估:mock evaluator 的 chat_json
    monkeypatch.setattr(evaluator, "chat_json", lambda system, user, **kw: FAKE_REPORT)

    client = TestClient(app, headers=CANDIDATE_HEADERS)

    # 创建面试
    r = client.post("/api/interviews", json=ids)
    assert r.status_code == 200, r.text
    iv_id = r.json()["id"]
    assert r.json()["status"] == "created"

    # 1) 开场白(空 reply)
    r = client.post(
        f"/api/interviews/{iv_id}/message", json={"request_id": "opening-0001"}
    )
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["agent_question"] == "请先自我介绍"
    assert turn["finished"] is False
    assert turn["progress"]["total_questions"] == 0

    # 2) 正常回答 → 追问
    first_payload = {"reply": "我是张三,3 年 Python 经验", "request_id": "answer-0001"}
    r = client.post(f"/api/interviews/{iv_id}/message", json=first_payload)
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["agent_question"] == "追问:说细节"
    assert turn["action"] == ACTION_CONTINUE_DIMENSION
    assert turn["progress"]["total_questions"] == 1
    # 响应丢失后的同 ID 重试直接回放，不再次调用状态机。
    replay = client.post(f"/api/interviews/{iv_id}/message", json=first_payload)
    assert replay.status_code == 200
    assert replay.json() == turn

    # 3) 回答 → 下一维度为软素质,服务端同步切到行为面试
    r = client.post(
        f"/api/interviews/{iv_id}/message",
        json={"reply": "用 asyncio 优化过接口", "request_id": "answer-0002"},
    )
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["action"] == ACTION_GO_BEHAVIORAL
    assert "沟通表达" in turn["agent_question"]

    # 4) 回答最后一个维度 → 固定进入候选人反向提问
    r = client.post(
        f"/api/interviews/{iv_id}/message",
        json={
            "reply": "曾经跨部门协作过一个项目",
            "request_id": "answer-0003",
        },
    )
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["action"] == ACTION_GO_CANDIDATE_QA
    assert turn["finished"] is False
    assert turn["dimension"] is None

    # 5) 候选人提问环节回答后收尾
    final_payload = {
        "reply": "暂时没有其他问题",
        "request_id": "answer-0004",
    }
    r = client.post(f"/api/interviews/{iv_id}/message", json=final_payload)
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["finished"] is True
    assert "这个问题我简要回答如下" in turn["agent_question"]
    assert "本轮模拟面试到这里就结束了" in turn["agent_question"]
    closing_text = turn["agent_question"]

    # 6) 即使已经 finished，同一逻辑请求仍可安全重试并拿到相同响应。
    replay = client.post(f"/api/interviews/{iv_id}/message", json=final_payload)
    assert replay.status_code == 200
    assert replay.json()["agent_question"] == closing_text

    # 7) 面试已结束,新的回答被拒绝
    r = client.post(
        f"/api/interviews/{iv_id}/message",
        json={"reply": "再补充一句", "request_id": "answer-0005"},
    )
    assert r.status_code == 409

    # 8) 消息留痕:开场 agent + 4 轮 × (candidate + agent) = 9 条
    r = client.get(f"/api/interviews/{iv_id}/messages")
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 9
    roles = [m["role"] for m in msgs]
    assert roles == [
        "agent",
        "candidate",
        "agent",
        "candidate",
        "agent",
        "candidate",
        "agent",
        "candidate",
        "agent",
    ]
    assert msgs[0]["text"] == "请先自我介绍"
    # assess 属于被评估的候选人回答，不再错误挂在下一道题上。
    assert msgs[-2]["assess"]["evidence"] == "e"
    assert msgs[-1]["assess"] is None
    # 回答归属调用前的问题维度；反向提问和收尾不归属能力维度。
    assert msgs[3]["dimension"] == "Python 编程"
    assert msgs[4]["dimension"] == "沟通表达"
    assert msgs[5]["dimension"] == "沟通表达"
    assert msgs[6]["dimension"] is None
    assert msgs[7]["dimension"] is None
    # 客户端与数据库看到的是同一条正式收尾语。
    assert msgs[-1]["text"] == closing_text
    assert msgs[-1]["dimension"] is None

    # 9) state 接口返回进度
    r = client.get(f"/api/interviews/{iv_id}/state")
    assert r.status_code == 200
    state = r.json()
    assert state["status"] == "finished"
    assert state["progress"]["total_questions"] == 4

    # 10) 收尾自动触发评估,报告已生成
    r = client.get(f"/api/interviews/{iv_id}/report")
    assert r.status_code == 200, r.text
    report = r.json()["report"]
    assert report["summary_score"] == 76
    assert report["suggestion"] == "建议进入二面"


def test_style_flows_into_prompts(test_db, monkeypatch):
    """创建时指定风格 → 持久化 → 注入首轮 system prompt(人格在语言层)。"""
    ids = _seed(test_db)
    judge, calls = make_sequence(
        actions=[ACTION_CONTINUE_DIMENSION], next_qs=["请介绍一个压力场景"]
    )
    monkeypatch.setattr(interviews_api, "_get_graph", lambda: build_graph(judge))

    client = TestClient(app, headers=CANDIDATE_HEADERS)
    r = client.post("/api/interviews", json={**ids, "style": "pressure"})
    assert r.status_code == 200
    iv_id = r.json()["id"]
    assert r.json()["style"] == "pressure"

    r = client.post(
        f"/api/interviews/{iv_id}/message", json={"request_id": "opening-style"}
    )
    assert r.status_code == 200
    assert "高老师" in calls[0]["system"]
    assert "压力面试官" in calls[0]["system"]


def test_invalid_style_rejected(test_db):
    ids = _seed(test_db)
    client = TestClient(app, headers=CANDIDATE_HEADERS)
    r = client.post("/api/interviews", json={**ids, "style": "robot"})
    assert r.status_code == 422


def test_private_interview_requires_candidate_token(test_db):
    ids = _seed(test_db)
    anonymous = TestClient(app)
    assert anonymous.post("/api/interviews", json=ids).status_code == 401

    authorized = TestClient(app, headers=CANDIDATE_HEADERS)
    created = authorized.post("/api/interviews", json=ids)
    assert created.status_code == 200
    interview_id = created.json()["id"]
    assert anonymous.get(f"/api/interviews/{interview_id}").status_code == 401
    assert (
        anonymous.get(
            f"/api/interviews/{interview_id}",
            headers={"X-Candidate-Token": "wrong-token"},
        ).status_code
        == 401
    )


def test_interview_snapshot_uses_optimistic_lock(test_db):
    ids = _seed(test_db)
    client = TestClient(app, headers=CANDIDATE_HEADERS)
    interview_id = client.post("/api/interviews", json=ids).json()["id"]

    first = test_db()
    second = test_db()
    try:
        row_a = first.get(Interview, interview_id)
        row_b = second.get(Interview, interview_id)
        row_a.state = '{"writer": "a"}'
        first.commit()
        row_b.state = '{"writer": "b"}'
        with pytest.raises(StaleDataError):
            second.commit()
    finally:
        second.rollback()
        first.close()
        second.close()


def test_candidate_match_endpoint(test_db, monkeypatch):
    """GET /api/candidates/{id}/match/{job_id}:mock 匹配 agent,返回分数结构。"""
    from app.api import candidates as candidates_api
    from app.models import Candidate

    ids = _seed(test_db)
    fake = {
        "overall": 68,
        "summary": "基本匹配",
        "dimension_scores": [{"name": "Python 编程", "resume_evidence": "e", "score": 7}],
        "highlights": ["h"],
        "gaps": ["g"],
    }
    monkeypatch.setattr(candidates_api, "match_resume_to_job", lambda **kw: fake)

    with test_db() as s:
        cand = Candidate(
            name="李四",
            parsed_resume=json.dumps({"basic": {"name": "李四"}}),
            access_token_hash=hash_candidate_token(ACCESS_TOKEN),
        )
        s.add(cand)
        s.commit()
        cand_id = cand.id

    client = TestClient(app, headers=CANDIDATE_HEADERS)
    assert (
        TestClient(app).get(
            f"/api/candidates/{cand_id}/match/{ids['job_id']}"
        ).status_code
        == 401
    )
    r = client.get(f"/api/candidates/{cand_id}/match/{ids['job_id']}")
    assert r.status_code == 200, r.text
    assert r.json()["overall"] == 68
    # 无维度的岗位应 422
    with test_db() as s:
        bare = Job(title="裸岗位", jd_text="无分析")
        s.add(bare)
        s.commit()
        bare_id = bare.id
    r = client.get(f"/api/candidates/{cand_id}/match/{bare_id}")
    assert r.status_code == 422
