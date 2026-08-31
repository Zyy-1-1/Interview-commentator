"""候选人接口:上传简历并触发解析 + 简历×岗位匹配分析。"""
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..agents.matcher import match_resume_to_job
from ..agents.resume_parser import parse_resume_file
from ..db import get_db
from ..models import Candidate, Job
from ..schemas import CandidateOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/candidates", tags=["candidates"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED_SUFFIXES = {".pdf", ".docx", ".doc", ".txt", ".md"}


def _save_upload(file: UploadFile) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"不支持的文件类型 {suffix or '(无后缀)'},支持 PDF/DOCX/DOC/TXT/MD")
    # 随机文件名,避免路径穿越/重名
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    path = UPLOAD_DIR / safe_name
    with path.open("wb") as f:
        f.write(file.file.read())
    return path


@router.get("", response_model=list[CandidateOut])
def list_candidates(db: Session = Depends(get_db)):
    return db.query(Candidate).order_by(Candidate.created_at.desc()).all()


@router.post("", response_model=CandidateOut)
async def upload_candidate(file: UploadFile, db: Session = Depends(get_db)):
    path = _save_upload(file)
    try:
        parsed = parse_resume_file(path)
    except Exception as e:  # noqa: BLE001
        logger.warning("简历解析失败 %s: %s", path.name, e)
        raise HTTPException(422, f"简历解析失败: {e}") from e

    text = parsed.pop("_source_text", None)
    cand = Candidate(
        name=parsed.get("basic", {}).get("name"),
        resume_path=str(path),
        resume_text=text,
        parsed_resume=json.dumps(parsed, ensure_ascii=False),
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand


@router.get("/{candidate_id}/match/{job_id}")
def match_to_job(candidate_id: int, job_id: int, db: Session = Depends(get_db)):
    """面试前的人岗匹配分析(简历 × 岗位维度)。"""
    cand = db.get(Candidate, candidate_id)
    job = db.get(Job, job_id)
    if not cand:
        raise HTTPException(404, "候选人不存在")
    if not job:
        raise HTTPException(404, "岗位不存在")
    dims = json.loads(job.dimensions or "[]")
    if not dims:
        raise HTTPException(422, "该岗位尚未完成 JD 分析,无法匹配")
    parsed = json.loads(cand.parsed_resume) if cand.parsed_resume else None
    try:
        result = match_resume_to_job(
            parsed_resume=parsed,
            resume_text=cand.resume_text,
            job_title=job.title,
            jd_text=job.jd_text,
            dimensions=dims,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"匹配分析失败: {e}") from e
    return result


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, "候选人不存在")
    return cand
