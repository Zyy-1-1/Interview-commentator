"""简历上传边界：大小、真实类型与临时文件清理。"""
from io import BytesIO

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import UploadFile

from app.api import candidates as candidates_api
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Candidate
from app.security import hash_candidate_token


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(content))


def test_rejects_legacy_doc_and_spoofed_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(candidates_api, "UPLOAD_DIR", tmp_path)
    with pytest.raises(HTTPException) as legacy:
        candidates_api._save_upload(_upload("resume.doc", b"legacy"))
    assert legacy.value.status_code == 400

    with pytest.raises(HTTPException) as spoofed:
        candidates_api._save_upload(_upload("resume.pdf", b"not a pdf"))
    assert spoofed.value.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_rejects_oversized_upload_without_residue(tmp_path, monkeypatch):
    monkeypatch.setattr(candidates_api, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(settings, "max_upload_bytes", 4, raising=False)
    with pytest.raises(HTTPException) as exc:
        candidates_api._save_upload(_upload("resume.txt", b"12345"))
    assert exc.value.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_upload_parses_in_threadpool_and_deletes_source(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'upload.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        with TestSession() as session:
            yield session

    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(candidates_api, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(
        candidates_api,
        "parse_resume_file",
        lambda path: {
            "basic": {"name": "张三"},
            "skills": {"programming": ["Python"]},
            "_source_text": "张三的简历原文",
        },
    )
    app.dependency_overrides[get_db] = override
    try:
        client = TestClient(app)
        response = client.post(
            "/api/candidates",
            files={"file": ("resume.txt", "张三的简历原文".encode(), "text/plain")},
        )
        assert response.status_code == 200, response.text
        assert "resume_text" not in response.json()
        access_token = response.json()["access_token"]
        assert len(access_token) >= 32
        assert list(upload_dir.iterdir()) == []
        with TestSession() as session:
            candidate = session.query(Candidate).one()
            assert candidate.resume_path is None
            assert candidate.resume_text == "张三的简历原文"
            assert candidate.access_token_hash == hash_candidate_token(access_token)
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
