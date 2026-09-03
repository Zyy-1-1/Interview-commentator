"""Pydantic 请求/响应模型。"""
import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------- Job ----------
class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=255)
    jd_text: str = Field(min_length=10, max_length=50_000)
    company: Optional[str] = Field(default=None, max_length=255)


class JobOut(BaseModel):
    id: int
    title: str
    jd_text: str
    company: Optional[str] = None
    status: str = "approved"
    review_note: Optional[str] = None
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


class JobReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: int = Field(gt=0)
    approve: bool
    note: Optional[str] = Field(default=None, max_length=500)


# ---------- Candidate ----------
class CandidateOut(BaseModel):
    id: int
    name: Optional[str] = None
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


class CandidateCreated(CandidateOut):
    """上传成功时仅返回一次的匿名访问令牌。"""

    access_token: str


# ---------- Interview ----------
class InterviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: int = Field(gt=0)
    candidate_id: int = Field(gt=0)
    # pro | friendly | pressure
    style: str = "pro"


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
    # 存量行迁移前可能为 NULL → 前端据此回退/弹风格选择器
    style: Optional[str] = None
    report: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("report", mode="before")
    @classmethod
    def _parse_report(cls, v: Any) -> Any:
        # DB 里 report 存 JSON 字符串
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v


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
    model_config = ConfigDict(extra="forbid")

    reply: Optional[str] = Field(default=None, max_length=20_000)
    # 客户端为一次逻辑发送生成并在重试时复用，防止响应丢失后重复推进状态机。
    request_id: Optional[str] = Field(default=None, min_length=8, max_length=64)


class InterviewStateOut(BaseModel):
    """会话状态(进度),供前端轮询/展示。"""
    status: str
    progress: dict[str, Any]
