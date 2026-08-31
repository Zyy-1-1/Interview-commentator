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
    "interviews": [
        ("style", "VARCHAR(16) DEFAULT 'pro'"),
    ],
}


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


def init_db() -> None:
    """建表(幂等)+ 补列迁移。"""
    from . import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(bind=engine)
    _migrate_added_columns()


def get_db():
    """FastAPI 依赖:请求级 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
