"""Pydantic 请求/响应模型。"""
import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator


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

    @field_validator("dimensions", mode="before")
    @classmethod
    def _parse_dimensions(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v


# ---------- Candidate ----------
class CandidateOut(BaseModel):
    id: int
    name: Optional[str] = None
    resume_text: Optional[str] = None
    parsed_resume: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("parsed_resume", mode="before")
    @classmethod
    def _parse_parsed_resume(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v


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

    @field_validator("assess", mode="before")
    @classmethod
    def _parse_assess(cls, v: Any) -> Any:
        # DB 里 assess 存的是 JSON 字符串,响应时解析为 dict
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v


class InterviewOut(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    status: str
    report: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewListItem(BaseModel):
    """演示后台面试列表项(含岗位/应聘者名称与报告总分)。"""
    id: int
    status: str
    job_title: str
    candidate_name: Optional[str] = None
    summary_score: Optional[float] = None
    created_at: datetime


# 候选人提交回答 / 面试官响应的统一结构
class InterviewTurn(BaseModel):
    """一轮完整交互:候选人回答 → 面试官响应(下一问 + 决策)。"""
    agent_question: str
    action: str
    dimension: Optional[str] = None
    assess: Optional[dict] = None
    progress: dict[str, Any] = {}  # 当前维度进度/剩余维度,供前端展示
    finished: bool = False


class InterviewMessage(BaseModel):
    """候选人提交回答(reply 为空表示开场,生成开场白)。"""
    reply: Optional[str] = None


class InterviewStateOut(BaseModel):
    """会话状态(进度),供前端轮询/展示。"""
    status: str
    progress: dict[str, Any]
