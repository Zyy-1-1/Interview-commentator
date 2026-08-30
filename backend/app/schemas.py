"""Pydantic 请求/响应模型。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ---------- Job ----------
class JobCreate(BaseModel):
    title: str
    jd_text: str


class JobOut(BaseModel):
    id: int
    title: str
    jd_text: str
    dimensions: Optional[list] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Candidate ----------
class CandidateOut(BaseModel):
    id: int
    name: Optional[str] = None
    resume_text: Optional[str] = None
    parsed_resume: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Interview ----------
class InterviewCreate(BaseModel):
    job_id: int
    candidate_id: int


class MessageOut(BaseModel):
    id: int
    role: str
    text: str
    dimension: Optional[str] = None
    assess: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewOut(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    status: str
    report: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# 候选人提交回答 / 面试官响应的统一结构
class InterviewTurn(BaseModel):
    """一轮完整交互:候选人回答 → 面试官响应(下一问 + 决策)。"""
    agent_question: str
    action: str
    dimension: Optional[str] = None
    assess: Optional[dict] = None
    progress: dict[str, Any] = {}  # 当前维度进度/剩余维度,供前端展示
    finished: bool = False
