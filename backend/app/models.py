"""数据模型(SQLite 版,对齐技术方案 6.1)。

七张表:
- jobs                 岗位(JD)
- candidates           候选人(简历)
- interviews           面试(含状态快照 state + 评估报告 report)
- interview_messages   逐轮消息(审计 / 回放 / 评估证据来源)
- posts                交流区帖子(匿名,牛客式)
- comments             交流区评论
- post_likes           帖子点赞(按匿名身份令牌去重)
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    jd_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 招聘公司(自助提交时填写)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # pending(待审核) | approved(已上架) | rejected(已驳回)
    status: Mapped[str] = mapped_column(String(16), default="approved")
    # 审核意见(驳回原因等)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # JD 分析 Agent 输出的维度清单(JSON 字符串,见 jd_analyzer)
    dimensions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ---- 分类筛选字段(任务4:按专业/学历/薪资/校招社招/岗位类别筛选)----
    # 岗位职能类别,如 技术研发 / 算法AI / 金融 / 制造 / 医药 / 土木建筑 等
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 最低学历要求:不限 / 大专 / 本科 / 硕士 / 博士
    education: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 薪资区间(单位:千元/月);salary_months 为年薪月数(如 15 薪)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 招聘类型:校招 / 社招 / 实习
    recruit_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 专业要求(自由文本,如「计算机 / 软件工程」「不限」)
    majors: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 工作城市
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 是否为官方精选岗位(演示预置数据标记,前端可加「官方」角标)
    is_official: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    interviews: Mapped[list["Interview"]] = relationship(back_populates="job")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 简历解析 Agent 输出的结构化 JSON(见 resume_parser)
    parsed_resume: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 匿名访问令牌只保存 SHA-256，不保存可直接使用的明文。
    access_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    interviews: Mapped[list["Interview"]] = relationship(back_populates="candidate")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # SQLAlchemy 乐观锁版本号，避免两个并发回答覆盖同一份状态快照。
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    # created | opening | probing | behavioral | candidate_qa | closing | finished | timeout
    status: Mapped[str] = mapped_column(String(32), default="created")
    # InterviewState 快照(JSON,恢复会话用,见 interviewer/state.py)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 面试官风格:pro(严谨技术官) | friendly(亲和 HR) | pressure(压力面)
    style: Mapped[str] = mapped_column(String(16), default="pro")
    # 评估 Agent 输出的报告(JSON)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_status: Mapped[str] = mapped_column(String(16), default="not_started")
    report_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    report_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    report_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    job: Mapped[Job] = relationship(back_populates="interviews")
    candidate: Mapped[Candidate] = relationship(back_populates="interviews")
    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewMessage.id",
    )

    __mapper_args__ = {"version_id_col": version}


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"))
    # agent | candidate
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # 属于哪个考察维度
    dimension: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 面试官该轮的 assess 输出(质量分/证据,JSON)
    assess: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    interview: Mapped[Interview] = relationship(back_populates="messages")


# ============================================================ 交流区(任务5:牛客式板块)
class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 匿名昵称(发帖时按身份令牌哈希生成,如「面评家用户_3f8a」)
    author_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 身份令牌 SHA-256,不存明文(用于「我赞过」判定与后续治理)
    author_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="Comment.id",
    )
    likes: Mapped[list["PostLike"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str] = mapped_column(String(64), nullable=False)
    author_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    post: Mapped[Post] = relationship(back_populates="comments")


class PostLike(Base):
    """同一匿名令牌对同一帖子只允许一条点赞记录(点赞 = 幂等 toggle)。"""

    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("post_id", "token_hash", name="uq_post_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    post: Mapped[Post] = relationship(back_populates="likes")
