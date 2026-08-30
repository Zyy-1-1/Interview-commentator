"""FastAPI 应用入口。"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="面评家 API", version="0.1.0", description="AI 多轮结构化面试 Agent")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "alive"}


# 路由
from .api import candidates, interviews, jobs, reports  # noqa: E402

app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(interviews.router)
app.include_router(reports.router)
