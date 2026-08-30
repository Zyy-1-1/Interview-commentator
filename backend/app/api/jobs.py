"""岗位(JD)接口:创建岗位并触发 JD 分析。"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.jd_analyzer import analyze_jd
from ..db import get_db
from ..models import Job
from ..schemas import JobCreate, JobOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db)):
    return db.query(Job).order_by(Job.created_at.desc()).all()


@router.post("", response_model=JobOut)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    job = Job(title=body.title, jd_text=body.jd_text)
    db.add(job)
    db.commit()
    db.refresh(job)

    # 触发 JD 分析(失败不回滚创建,维度留空,允许重试)
    try:
        dims = analyze_jd(body.jd_text)
        job.dimensions = json.dumps(dims, ensure_ascii=False)
        db.commit()
        db.refresh(job)
    except Exception as e:  # noqa: BLE001
        logger.warning("JD 分析失败(job=%s): %s", job.id, e)

    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "岗位不存在")
    return job


@router.post("/{job_id}/analyze", response_model=JobOut)
def reanalyze_job(job_id: int, db: Session = Depends(get_db)):
    """JD 分析失败后的重试入口。"""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "岗位不存在")
    try:
        dims = analyze_jd(job.jd_text)
        job.dimensions = json.dumps(dims, ensure_ascii=False)
        db.commit()
        db.refresh(job)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"JD 分析失败: {e}") from e
    return job
