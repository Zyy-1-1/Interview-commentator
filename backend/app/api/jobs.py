"""岗位(JD)接口:自助提交(待审核)+ 官方口令审核 + 大厅查询。

流程:
- POST /api/jobs           自助提交,默认 status=pending(skip_review=True 直接上架)
- POST /api/jobs/review    官方审核:口令校验 → approved / rejected
- GET  /api/jobs           默认只返回 approved(大厅);status=all|pending|... 供审核页
"""
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.jd_analyzer import analyze_jd
from ..config import settings
from ..db import get_db
from ..models import Job
from ..schemas import JobCreate, JobOut, JobReviewIn

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _check_passphrase(given: str) -> None:
    if not settings.review_passphrase:
        raise HTTPException(500, "服务端未配置 REVIEW_PASSPHRASE,无法审核")
    if not hmac.compare_digest(given or "", settings.review_passphrase):
        raise HTTPException(401, "审核口令错误")


@router.get("", response_model=list[JobOut])
def list_jobs(status: str = "approved", db: Session = Depends(get_db)):
    """大厅默认只看已上架岗位;审核页传 status=pending / all。"""
    q = db.query(Job).order_by(Job.created_at.desc())
    if status != "all":
        q = q.filter(Job.status == status)
    return q.all()


@router.post("", response_model=JobOut)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    job = Job(
        title=body.title,
        jd_text=body.jd_text,
        company=body.company,
        status="approved" if body.skip_review else "pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 触发 JD 分析(失败不回滚创建,维度留空,允许重试)
    try:
        dims = _dims_of(analyze_jd(body.jd_text))
        job.dimensions = json.dumps(dims, ensure_ascii=False)
        db.commit()
        db.refresh(job)
    except Exception as e:  # noqa: BLE001
        logger.warning("JD 分析失败(job=%s): %s", job.id, e)

    return job


def _dims_of(result: Any) -> list:
    """兼容 analyzer 返回 {dimensions: [...]} 或直接返回列表两种形态。"""
    if isinstance(result, dict):
        return result.get("dimensions") or []
    return result or []


@router.post("/review", response_model=JobOut)
def review_job(body: JobReviewIn, db: Session = Depends(get_db)):
    """官方审核:口令通过后 approve/reject 一个岗位。"""
    _check_passphrase(body.passphrase)
    job = db.get(Job, body.job_id)
    if not job:
        raise HTTPException(404, "岗位不存在")
    job.status = "approved" if body.approve else "rejected"
    job.review_note = body.note
    db.commit()
    db.refresh(job)
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
        dims = _dims_of(analyze_jd(job.jd_text))
        job.dimensions = json.dumps(dims, ensure_ascii=False)
        db.commit()
        db.refresh(job)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"JD 分析失败: {e}") from e
    return job
