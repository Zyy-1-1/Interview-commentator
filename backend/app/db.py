"""数据库引擎与会话。"""
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

# SQLite 需要 check_same_thread=False 供多线程(uvicorn)访问
connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# 轻量列迁移:表已存在时 create_all 不会加列,这里幂等补齐
# (表名 -> [(列, 定义 SQL)];生产切 Alembic)
_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "jobs": [
        ("company", "VARCHAR(255)"),
        ("status", "VARCHAR(16) DEFAULT 'approved'"),
        ("review_note", "VARCHAR(500)"),
    ],
    "candidates": [
        ("access_token_hash", "VARCHAR(64)"),
    ],
    "interviews": [
        ("style", "VARCHAR(16) DEFAULT 'pro'"),
        ("version", "INTEGER DEFAULT 1 NOT NULL"),
        ("report_status", "VARCHAR(16) DEFAULT 'not_started' NOT NULL"),
        ("report_task_id", "VARCHAR(32)"),
        ("report_requested_at", "DATETIME"),
        ("report_error", "VARCHAR(255)"),
    ],
}

_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("jobs", "ix_jobs_status_created", "status, created_at"),
    ("candidates", "ix_candidates_created", "created_at"),
    ("interviews", "ix_interviews_job_status_created", "job_id, status, created_at"),
    ("interviews", "ix_interviews_candidate_created", "candidate_id, created_at"),
    ("interview_messages", "ix_messages_interview_id", "interview_id, id"),
)


def _migrate_added_columns() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                    )
                    logger.info("迁移: 表 %s 加列 %s", table, name)


def _ensure_indexes() -> None:
    """为大厅、后台列表和消息回放的高频过滤建立幂等索引。"""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, name, columns in _INDEXES:
            if insp.has_table(table):
                conn.execute(
                    text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
                )


def init_db() -> None:
    """建表(幂等)+ 补列迁移。"""
    from . import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(bind=engine)
    _migrate_added_columns()
    _ensure_indexes()


def get_db():
    """FastAPI 依赖:请求级 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
