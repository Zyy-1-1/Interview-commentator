"""岗位(JD)接口:自助提交(待审核)+ 官方口令审核 + 大厅查询。

流程:
- POST /api/jobs           自助提交,一律 status=pending，不触发付费分析
- POST /api/jobs/review    官方审核:请求头口令校验 → 分析 → approved / rejected
- GET  /api/jobs           默认只返回 approved；非公开状态需后台口令
"""
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..agents.jd_analyzer import analyze_jd
from ..db import get_db
from ..models import Job
from ..schemas import JobCreate, JobOut, JobReviewIn
from ..security import REVIEW_HEADER, require_admin, verify_review_passphrase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: str = "approved",
    db: Session = Depends(get_db),
    passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    """大厅默认只看已上架岗位;审核页传 status=pending / all。"""
    if status not in {"approved", "pending", "rejected", "all"}:
        raise HTTPException(422, "status 仅支持 approved/pending/rejected/all")
    if status != "approved":
        verify_review_passphrase(passphrase)
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
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def _dims_of(result: Any) -> list:
    """兼容 analyzer 返回 {dimensions: [...]} 或直接返回列表两种形态。"""
    if isinstance(result, dict):
        return result.get("dimensions") or []
    return result or []


@router.post("/review", response_model=JobOut)
def review_job(
    body: JobReviewIn,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """官方审核:口令通过后 approve/reject 一个岗位。"""
    job = db.get(Job, body.job_id)
    if not job:
        raise HTTPException(404, "岗位不存在")
    # 只在审核通过时触发付费 JD 分析，公开提交接口不会被用来刷调用量。
    if body.approve and not job.dimensions:
        try:
            dims = _dims_of(analyze_jd(job.jd_text))
            if not dims:
                raise ValueError("未生成考察维度")
            job.dimensions = json.dumps(dims, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.exception("JD 分析失败(job=%s): %s", job.id, e)
            raise HTTPException(502, "JD 分析失败,岗位尚未上架,请稍后重试") from e
    job.status = "approved" if body.approve else "rejected"
    job.review_note = body.note
    db.commit()
    db.refresh(job)
    return job


@router.post("/review/auth")
def authenticate_review_console(_admin: str = Depends(require_admin)):
    """审核页进入前做一次真实服务端校验。"""
    return {"authenticated": True}


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "岗位不存在")
    if job.status != "approved":
        verify_review_passphrase(passphrase)
    return job


@router.post("/{job_id}/analyze", response_model=JobOut)
def reanalyze_job(
    job_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
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
        db.rollback()
        logger.exception("JD 重新分析失败(job=%s): %s", job_id, e)
        raise HTTPException(502, "JD 分析失败,请稍后重试") from e
    return job
