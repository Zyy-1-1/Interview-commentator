"""答题闭环 API 集成测试(临时 SQLite + mock LLM,可离线运行)。

验证:创建面试 → 开场白 → 多轮回答(追问/推进/收尾)→ state 持久化 → 消息留痕 → 结束后拒绝继续。
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.interviewer.graph import build_graph
from app.agents.interviewer.state import ACTION_CLOSING, ACTION_CONTINUE_DIMENSION, ACTION_NEXT_DIMENSION
from app.api import interviews as interviews_api
from app.db import Base, get_db
from app.main import app
from app.models import Candidate, Job

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
        cand = Candidate(name="张三")
        s.add_all([job, cand])
        s.commit()
        return {"job_id": job.id, "candidate_id": cand.id}


def test_full_interview_loop(test_db, monkeypatch):
    ids = _seed(test_db)
    # 第 1 次调用是开场白轮(占位),其后依次为 回答1→追问 / 回答2→推进 / 回答3→收尾
    judge, calls = make_sequence(
        actions=[
            ACTION_CONTINUE_DIMENSION,
            ACTION_CONTINUE_DIMENSION,
            ACTION_NEXT_DIMENSION,
            ACTION_CLOSING,
        ],
        next_qs=["请先自我介绍", "追问:说细节", "推进:讲沟通案例", "收尾问题"],
    )
    graph = build_graph(judge)
    monkeypatch.setattr(interviews_api, "_get_graph", lambda: graph)

    client = TestClient(app)

    # 创建面试
    r = client.post("/api/interviews", json=ids)
    assert r.status_code == 200, r.text
    iv_id = r.json()["id"]
    assert r.json()["status"] == "created"

    # 1) 开场白(空 reply)
    r = client.post(f"/api/interviews/{iv_id}/message", json={})
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["agent_question"] == "请先自我介绍"
    assert turn["finished"] is False
    assert turn["progress"]["total_questions"] == 0

    # 2) 正常回答 → 追问
    r = client.post(f"/api/interviews/{iv_id}/message", json={"reply": "我是张三,3 年 Python 经验"})
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["agent_question"] == "追问:说细节"
    assert turn["action"] == ACTION_CONTINUE_DIMENSION
    assert turn["progress"]["total_questions"] == 1

    # 3) 回答 → 推进维度
    r = client.post(f"/api/interviews/{iv_id}/message", json={"reply": "用 asyncio 优化过接口"})
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["action"] == ACTION_NEXT_DIMENSION
    assert turn["agent_question"] == "推进:讲沟通案例"

    # 4) 回答 → 收尾
    r = client.post(f"/api/interviews/{iv_id}/message", json={"reply": "曾经跨部门协作过一个项目"})
    assert r.status_code == 200, r.text
    turn = r.json()
    assert turn["finished"] is True
    assert turn["agent_question"]

    # 5) 面试已结束,继续回答被拒绝
    r = client.post(f"/api/interviews/{iv_id}/message", json={"reply": "再补充一句"})
    assert r.status_code == 409

    # 6) 消息留痕:开场 agent + 3 轮 × (candidate + agent) = 7 条
    r = client.get(f"/api/interviews/{iv_id}/messages")
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 7
    roles = [m["role"] for m in msgs]
    assert roles == ["agent", "candidate", "agent", "candidate", "agent", "candidate", "agent"]
    assert msgs[0]["text"] == "请先自我介绍"
    # 最后一轮 agent 消息带 assess(证据引用)
    assert msgs[-1]["assess"]["evidence"] == "e"

    # 7) state 接口返回进度
    r = client.get(f"/api/interviews/{iv_id}/state")
    assert r.status_code == 200
    state = r.json()
    assert state["status"] == "finished"
    assert state["progress"]["total_questions"] == 3
