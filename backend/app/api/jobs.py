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


@router.get("/facets")
def job_facets(db: Session = Depends(get_db)):
    """大厅筛选栏可选值:从已上架岗位里聚合出真实存在的类别/学历/招聘类型。"""
    rows = db.query(Job).filter(Job.status == "approved").all()

    def _distinct(key):
        seen, out = set(), []
        for r in rows:
            v = getattr(r, key)
            if v and v not in seen:
                seen.add(v)
                out.append(v)
        return out

    sal = [
        (r.salary_min, r.salary_max)
        for r in rows
        if r.salary_min is not None or r.salary_max is not None
    ]
    return {
        "categories": _distinct("category"),
        "educations": _distinct("education"),
        "recruit_types": _distinct("recruit_type"),
        "salary_floor": min([s[0] for s in sal if s[0] is not None], default=0),
        "salary_ceiling": max([s[1] for s in sal if s[1] is not None], default=0),
    }


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: str = "approved",
    category: str | None = None,
    education: str | None = None,
    recruit_type: str | None = None,
    major: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    """大厅默认只看已上架岗位;审核页传 status=pending / all。

    任务4:支持按岗位类别、学历、校招/社招/实习、专业、薪资区间、关键词筛选。
    """
    if status not in {"approved", "pending", "rejected", "all"}:
        raise HTTPException(422, "status 仅支持 approved/pending/rejected/all")
    if status != "approved":
        verify_review_passphrase(passphrase)
    query = db.query(Job).order_by(Job.created_at.desc())
    if status != "all":
        query = query.filter(Job.status == status)
    if category:
        query = query.filter(Job.category == category)
    if education:
        query = query.filter(Job.education == education)
    if recruit_type:
        query = query.filter(Job.recruit_type == recruit_type)
    if major:
        # majors 为自由文本(如「计算机 / 软件工程」),做包含匹配;「不限」视为通用
        kw = major.strip()
        query = query.filter(Job.majors.like(f"%{kw}%"))
    if salary_min is not None:
        # 岗位薪资上限需 ≥ 用户期望下限
        query = query.filter(Job.salary_max >= salary_min)
    if salary_max is not None:
        query = query.filter(Job.salary_min <= salary_max)
    if q:
        kw = f"%{q.strip()}%"
        query = query.filter(
            Job.title.like(kw) | Job.company.like(kw) | Job.jd_text.like(kw)
        )
    return query.all()


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
