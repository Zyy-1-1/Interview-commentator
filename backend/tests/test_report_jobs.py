"""报告任务：独立数据库、后台领取、重试及迟到结果的隔离回归。"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import db as database
from app import report_jobs
from app.agents.interviewer.state import initial_state
from app.db import Base, get_db
from app.main import app
from app.models import Candidate, Interview, Job
from app.security import hash_candidate_token

TOKEN = "synthetic-report-token"
HEADERS = {"X-Candidate-Token": TOKEN}


@pytest.fixture
def report_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'report-jobs.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        job = Job(title="Synthetic", jd_text="Synthetic JD", dimensions='[{"name":"Python","weight":1}]')
        candidate = Candidate(access_token_hash=hash_candidate_token(TOKEN))
        db.add_all([job, candidate])
        db.flush()
        interview = Interview(job_id=job.id, candidate_id=candidate.id, status="finished")
        db.add(interview)
        db.flush()
        interview.state = json.dumps(initial_state(interview_id=interview.id, dimensions=[{"name": "Python", "weight": 1}]))
        db.commit()
        interview_id = interview.id
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    yield factory, interview_id
    app.dependency_overrides.clear()
    engine.dispose()


def test_concurrent_requests_only_schedule_one_task(report_db, monkeypatch):
    factory, interview_id = report_db
    calls = []
    monkeypatch.setattr(report_jobs, "evaluate", lambda **kwargs: calls.append(kwargs) or {"summary_score": 70})
    barrier = Barrier(2)
    def request():
        background = BackgroundTasks()
        with factory() as db:
            interview = db.get(Interview, interview_id)
            barrier.wait(timeout=5)
            payload = report_jobs.queue_evaluation(interview, db, background)
        return payload, background
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request(), range(2)))
    assert all(payload["status"] == "pending" for payload, _ in results)
    assert sum(len(background.tasks) for _, background in results) == 1
    assert calls == []  # 返回任务状态时还未调用模型。
    for _, background in results:
        asyncio.run(background())
    assert len(calls) == 1
    with factory() as db:
        payload = report_jobs.report_payload(db.get(Interview, interview_id))
        assert payload["status"] == "ready"
        assert payload["report"]["summary_score"] == 70
        assert payload["can_retry"] is False


def test_failure_is_visible_and_retry_reuses_completed_report(report_db, monkeypatch):
    factory, interview_id = report_db
    def fail(**kwargs):
        raise ValueError("private model output must not escape")
    monkeypatch.setattr(report_jobs, "evaluate", fail)
    client = TestClient(app, headers=HEADERS)
    assert TestClient(app).get(f"/api/interviews/{interview_id}/report").status_code == 401
    accepted = client.post(f"/api/interviews/{interview_id}/evaluate")
    assert accepted.status_code == 202
    status = client.get(f"/api/interviews/{interview_id}/report").json()
    assert status["status"] == "failed"
    assert status["can_retry"] is True
    assert "private" not in status["error"]
    calls = []
    monkeypatch.setattr(report_jobs, "evaluate", lambda **kwargs: calls.append(1) or {"summary_score": 60})
    assert client.post(f"/api/interviews/{interview_id}/evaluate").status_code == 202
    cached = client.post(f"/api/interviews/{interview_id}/evaluate")
    assert cached.status_code == 200
    assert cached.json()["status"] == "ready"
    assert len(calls) == 1


def test_expired_attempt_cannot_overwrite_a_retry(report_db, monkeypatch):
    factory, interview_id = report_db
    old_background = BackgroundTasks()
    with factory() as db:
        interview = db.get(Interview, interview_id)
        report_jobs.queue_evaluation(interview, db, old_background)
        old_id = interview.report_task_id
        interview.report_status = "running"
        interview.report_requested_at = datetime.now() - timedelta(minutes=10)
        db.commit()
        assert report_jobs.report_payload(interview)["status"] == "failed"
        retry_background = BackgroundTasks()
        report_jobs.queue_evaluation(interview, db, retry_background)
        new_id = interview.report_task_id
    assert new_id != old_id
    report_jobs._finish(factory, interview_id, old_id, report={"summary_score": 99}, error=None)
    calls = []
    monkeypatch.setattr(report_jobs, "evaluate", lambda **kwargs: calls.append(1) or {"summary_score": 50})
    asyncio.run(old_background())
    asyncio.run(retry_background())
    with factory() as db:
        interview = db.get(Interview, interview_id)
        assert interview.report_task_id == new_id
        assert json.loads(interview.report)["summary_score"] == 50
    assert len(calls) == 1


def test_unfinished_interview_has_no_retry_action(report_db):
    factory, interview_id = report_db
    with factory() as db:
        interview = db.get(Interview, interview_id)
        interview.status = "probing"
        db.commit()
    client = TestClient(app, headers=HEADERS)
    assert client.get(f"/api/interviews/{interview_id}/report").json()["can_retry"] is False
    assert client.post(f"/api/interviews/{interview_id}/evaluate").status_code == 409


def test_report_columns_are_added_idempotently_without_rewriting_legacy_report(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE interviews (id INTEGER PRIMARY KEY, report TEXT)"))
        connection.execute(text("INSERT INTO interviews (id, report) VALUES (1, :report)"), {"report": '{"summary_score":80}'})
    monkeypatch.setattr(database, "engine", engine)
    database._migrate_added_columns()
    database._migrate_added_columns()
    assert {"report_status", "report_task_id", "report_requested_at", "report_error"} <= {
        column["name"] for column in inspect(engine).get_columns("interviews")
    }
    with engine.connect() as connection:
        row = connection.execute(text("SELECT report, report_status FROM interviews")).one()
        assert row == ('{"summary_score":80}', "not_started")
    engine.dispose()
