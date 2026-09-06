"""报告后台任务：数据库领取避免重复评估，失败或中断后可显式重试。"""
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import BackgroundTasks
from sqlalchemy import or_, update
from sqlalchemy.orm import Session, sessionmaker

from .agents.evaluator import evaluate
from .config import settings
from .models import Interview

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = ("pending", "running")


def _cutoff() -> datetime:
    return datetime.now() - timedelta(seconds=max(120, settings.llm_total_timeout_seconds + 30))


def report_payload(interview: Interview) -> dict:
    status = interview.report_status or "not_started"
    error = interview.report_error
    if interview.report:
        status, error = "ready", None
    elif status in ACTIVE_STATUSES and (
        interview.report_requested_at is None or interview.report_requested_at < _cutoff()
    ):
        status, error = "failed", "报告生成中断或超时，请重试。"
    return {
        "interview_id": interview.id,
        "status": status,
        "report": json.loads(interview.report) if interview.report else None,
        "error": error,
        "can_retry": interview.status == "finished" and status in {"not_started", "failed"},
    }


def queue_evaluation(interview: Interview, db: Session, background: BackgroundTasks) -> dict:
    """仅成功领取的请求安排任务；队列状态与会话状态分别保存。"""
    attempt_id = uuid4().hex
    claim = db.execute(
        update(Interview).where(
            Interview.id == interview.id,
            Interview.status == "finished",
            Interview.report.is_(None),
            or_(
                Interview.report_status.notin_(ACTIVE_STATUSES),
                Interview.report_status.is_(None),
                Interview.report_requested_at.is_(None),
                Interview.report_requested_at < _cutoff(),
            ),
        ).values(
            report_status="pending", report_task_id=attempt_id,
            report_requested_at=datetime.now(), report_error=None,
            version=Interview.version + 1,
        ).execution_options(synchronize_session=False)
    )
    db.commit()
    db.refresh(interview)
    if claim.rowcount == 1:
        # 不把请求 Session 传给后台线程；也便于测试用隔离数据库。
        factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
        background.add_task(run_evaluation, interview.id, attempt_id, factory)
    return report_payload(interview)


def _finish(factory, interview_id: int, attempt_id: str, *, report: dict | None, error: str | None):
    with factory() as db:
        db.execute(
            update(Interview).where(
                Interview.id == interview_id,
                Interview.report_task_id == attempt_id,
                Interview.report_status == "running",
                Interview.report_requested_at >= _cutoff(),
                Interview.report.is_(None),
            ).values(
                report=json.dumps(report, ensure_ascii=False, allow_nan=False) if report else None,
                report_status="ready" if report else "failed",
                report_error=error,
                version=Interview.version + 1,
            ).execution_options(synchronize_session=False)
        )
        db.commit()


def run_evaluation(interview_id: int, attempt_id: str, factory) -> None:
    try:
        with factory() as db:
            claim = db.execute(
                update(Interview).where(
                    Interview.id == interview_id,
                    Interview.report_task_id == attempt_id,
                    Interview.report_status == "pending",
                    Interview.report_requested_at >= _cutoff(),
                ).values(report_status="running", version=Interview.version + 1)
            )
            db.commit()
            if claim.rowcount != 1:
                return
            interview = db.get(Interview, interview_id)
            snapshot = json.loads(interview.state) if interview.state else {}
            arguments = {
                "job_title": snapshot.get("job_title") or interview.job.title,
                "dimensions": snapshot["dimensions"] if "dimensions" in snapshot else json.loads(interview.job.dimensions or "[]"),
                "parsed_resume": interview.candidate.parsed_resume,
                "messages": [
                    {"id": m.id, "role": m.role, "text": m.text, "dimension": m.dimension}
                    for m in interview.messages
                ],
            }
        # 模型调用在后台线程，且不占用数据库事务。
        report = evaluate(**arguments)
        _finish(factory, interview_id, attempt_id, report=report, error=None)
        logger.info("面试 %s 报告任务完成", interview_id)
    except Exception as error:  # 只记录异常类型，不记录简历、答题或模型正文。
        logger.warning("面试 %s 报告任务失败: %s", interview_id, type(error).__name__)
        try:
            _finish(factory, interview_id, attempt_id, report=None, error="评估暂时失败，请稍后重试。")
        except Exception as persistence_error:
            logger.warning("报告失败状态保存异常: %s", type(persistence_error).__name__)
