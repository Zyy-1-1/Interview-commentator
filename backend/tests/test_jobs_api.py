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


def _submit(client, title="前端工程师", company="某大厂", skip_review=False):
    return client.post(
        "/api/jobs",
        json={
            "title": title,
            "jd_text": "负责 Vue3 前端开发",
            "company": company,
            "skip_review": skip_review,
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
    # 审核队列能查到
    r = client.get("/api/jobs", params={"status": "pending"})
    assert any(j["id"] == job["id"] for j in r.json())


def test_skip_review_directly_approved(client):
    r = _submit(client, title="演示岗位", skip_review=True)
    assert r.json()["status"] == "approved"
    r = client.get("/api/jobs")
    assert any(j["title"] == "演示岗位" for j in r.json())


def test_review_rejects_wrong_passphrase(client):
    job_id = _submit(client).json()["id"]
    r = client.post(
        "/api/jobs/review",
        json={"passphrase": "wrong", "job_id": job_id, "approve": True},
    )
    assert r.status_code == 401
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "pending"


def test_review_approve_then_visible(client):
    job_id = _submit(client).json()["id"]
    r = client.post(
        "/api/jobs/review",
        json={"passphrase": "mianpingjia-admin", "job_id": job_id, "approve": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    r = client.get("/api/jobs")
    assert any(j["id"] == job_id for j in r.json())


def test_review_reject_records_note(client):
    job_id = _submit(client).json()["id"]
    r = client.post(
        "/api/jobs/review",
        json={
            "passphrase": "mianpingjia-admin",
            "job_id": job_id,
            "approve": False,
            "note": "JD 信息不完整",
        },
    )
    assert r.json()["status"] == "rejected"
    assert r.json()["review_note"] == "JD 信息不完整"
