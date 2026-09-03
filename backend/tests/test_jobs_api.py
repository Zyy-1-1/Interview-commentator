"""岗位自助提交 + 口令审核接口测试(临时 SQLite,mock JD 分析,离线可跑)。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import jobs as jobs_api
from app.config import settings
from app.db import Base, get_db
from app.main import app

FAKE_DIMS = [{"name": "Python", "type": "hard", "weight": 1.0, "keywords": []}]
ADMIN_HEADERS = {"X-Review-Passphrase": "mianpingjia-admin"}


@pytest.fixture
def test_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test_jobs.db'}",
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


@pytest.fixture
def client(test_db, monkeypatch):
    # mock JD 分析(避免真调 LLM)
    monkeypatch.setattr(jobs_api, "analyze_jd", lambda jd: {"dimensions": FAKE_DIMS})
    monkeypatch.setattr(settings, "review_passphrase", "mianpingjia-admin", raising=False)
    return TestClient(app)


def _submit(client, title="前端工程师", company="某大厂"):
    return client.post(
        "/api/jobs",
        json={
            "title": title,
            "jd_text": "负责 Vue3 前端开发",
            "company": company,
        },
    )


def test_submit_defaults_to_pending_and_hidden_from_hall(client):
    r = _submit(client)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "pending"
    assert job["company"] == "某大厂"
    # 大厅(默认 approved)看不到 pending
    r = client.get("/api/jobs")
    assert all(j["id"] != job["id"] for j in r.json())
    # 非公开审核队列必须带服务端校验过的口令
    r = client.get("/api/jobs", params={"status": "pending"})
    assert r.status_code == 401
    r = client.get("/api/jobs", params={"status": "pending"}, headers=ADMIN_HEADERS)
    assert any(j["id"] == job["id"] for j in r.json())


def test_public_cannot_skip_review(client):
    r = client.post(
        "/api/jobs",
        json={
            "title": "演示岗位",
            "jd_text": "这是一份足够长的岗位职责说明",
            "skip_review": True,
        },
    )
    assert r.status_code == 422


def test_review_console_auth_is_real_server_check(client):
    assert client.post("/api/jobs/review/auth").status_code == 401
    assert client.post("/api/jobs/review/auth", headers=ADMIN_HEADERS).json() == {
        "authenticated": True
    }


def test_review_rejects_wrong_passphrase(client):
    job_id = _submit(client).json()["id"]
    r = client.post(
        "/api/jobs/review",
        headers={"X-Review-Passphrase": "wrong"},
        json={"job_id": job_id, "approve": True},
    )
    assert r.status_code == 401
    assert client.get(f"/api/jobs/{job_id}").status_code == 401
    assert client.get(f"/api/jobs/{job_id}", headers=ADMIN_HEADERS).json()["status"] == "pending"


def test_review_approve_then_visible(client):
    job_id = _submit(client).json()["id"]
    r = client.post(
        "/api/jobs/review",
        headers=ADMIN_HEADERS,
        json={"job_id": job_id, "approve": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert r.json()["dimensions"] == FAKE_DIMS
    r = client.get("/api/jobs")
    assert any(j["id"] == job_id for j in r.json())


def test_review_reject_records_note(client):
    job_id = _submit(client).json()["id"]
    r = client.post(
        "/api/jobs/review",
        headers=ADMIN_HEADERS,
        json={
            "job_id": job_id,
            "approve": False,
            "note": "JD 信息不完整",
        },
    )
    assert r.json()["status"] == "rejected"
    assert r.json()["review_note"] == "JD 信息不完整"


def test_public_submit_does_not_trigger_paid_analysis(client, monkeypatch):
    monkeypatch.setattr(
        jobs_api,
        "analyze_jd",
        lambda jd: (_ for _ in ()).throw(AssertionError("不应调用")),
    )
    r = _submit(client, title="无需即时分析的岗位")
    assert r.status_code == 200
    assert r.json()["dimensions"] is None
