"""模型输出边界：区分可缺失字段、非法结构和非有限数值。"""
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def finite_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) else default


def text_value(value: Any, default: str = "", limit: int = 500) -> str:
    return value.strip()[:limit] if isinstance(value, str) else default


class OutputModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, coerce_numbers_to_str=True)


class ResumeBasic(OutputModel):
    name: str | None = None
    age: str | None = None
    school: str | None = None
    major: str | None = None


class Education(OutputModel):
    school: str | None = None
    degree: str | None = None
    major: str | None = None
    years: str | None = None


class Experience(OutputModel):
    company: str | None = None
    role: str | None = None
    duration: str | None = None
    summary: str | None = None


class Project(OutputModel):
    name: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    achievements: str | None = None

    @field_validator("tech_stack", mode="before")
    @classmethod
    def empty_stack(cls, value):
        return [] if value is None else value


class Skills(OutputModel):
    programming: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)

    @field_validator("programming", "tools", "soft", mode="before")
    @classmethod
    def empty_skills(cls, value):
        return [] if value is None else value


class ParsedResume(OutputModel):
    basic: ResumeBasic = Field(default_factory=ResumeBasic)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)

    @field_validator("basic", "skills", mode="before")
    @classmethod
    def empty_section(cls, value):
        return {} if value is None else value

    @field_validator("education", "experience", "projects", mode="before")
    @classmethod
    def empty_list(cls, value):
        return [] if value is None else value


def normalize_resume(value: Any) -> dict[str, Any]:
    return ParsedResume.model_validate(value).model_dump()


class InterviewDecision(OutputModel):
    next_question: str = Field(min_length=1, max_length=4000, strict=True)
    action: Any = "CONTINUE_DIMENSION"
    assess: dict[str, Any] = Field(default_factory=dict)

    @field_validator("assess", mode="before")
    @classmethod
    def empty_assess(cls, value):
        return {} if value is None else value


def normalize_decision(value: Any) -> dict[str, Any]:
    return InterviewDecision.model_validate(value).model_dump()
