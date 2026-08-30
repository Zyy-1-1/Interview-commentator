"""面试接口(MVP 阶段)。

W1 提供:发起面试(创建记录,status=created)。
W3 补齐:候选人答题闭环 POST /api/interviews/{id}/message。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Candidate, Interview, Job
from ..schemas import InterviewCreate, InterviewOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interviews", tags=["interviews"])


@router.post("", response_model=InterviewOut)
def create_interview(body: InterviewCreate, db: Session = Depends(get_db)):
    job = db.get(Job, body.job_id)
    cand = db.get(Candidate, body.candidate_id)
    if not job:
        raise HTTPException(404, "岗位不存在")
    if not cand:
        raise HTTPException(404, "候选人不存在")
    if not job.dimensions:
        raise HTTPException(422, "该岗位尚未完成 JD 分析(维度缺失),请先重试 JD 分析")

    interview = Interview(job_id=job.id, candidate_id=cand.id, status="created")
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.get("/{interview_id}", response_model=InterviewOut)
def get_interview(interview_id: int, db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    return interview
