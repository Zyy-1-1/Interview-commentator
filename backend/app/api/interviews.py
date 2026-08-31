"""面试接口:发起面试 + 候选人答题闭环。

核心闭环(W3):
    POST /api/interviews/{id}/message  候选人提交回答 → 状态机推进一个回合 → 下一问
流程(对齐开发计划 W3 设计):
    1. 从 Interview.state(JSON 快照)恢复会话状态,首次则用 initial_state 初始化;
    2. state.history 为空 → 开场白轮(忽略 reply,生成开场问题);
    3. 否则 → 注入 candidate_reply,invoke 状态机,得到下一问 + 决策;
    4. 把新状态写回快照,新消息写入 interview_messages(审计/回放/评估证据)。
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents.evaluator import evaluate
from ..agents.interviewer.graph import build_llm_graph, compute_progress
from ..agents.interviewer.state import initial_state
from ..db import get_db
from ..models import Candidate, Interview, InterviewMessage, Job
from ..schemas import (
    InterviewCreate,
    InterviewListItem,
    InterviewMessage as InterviewMessageIn,
    InterviewOut,
    InterviewStateOut,
    InterviewTurn,
    MessageOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interviews", tags=["interviews"])

_graph = None  # 状态机单例(生产接真实 LLM;测试 monkeypatch _get_graph)


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_llm_graph()
    return _graph


def _load_state(interview: Interview) -> dict:
    if interview.state:
        state = json.loads(interview.state)
    else:
        dims = json.loads(interview.job.dimensions or "[]")
        state = initial_state(
            interview_id=interview.id,
            dimensions=dims,
            job_title=interview.job.title or "本岗位",
            style=interview.style or "pro",
        )
    return state


def _persist(interview: Interview, result: dict, db: Session) -> None:
    """把状态机输出写回快照(剔除注入字段,保留审计字段)。"""
    snap = dict(result)
    snap.pop("candidate_reply", None)  # 注入字段不入库
    interview.state = json.dumps(snap, ensure_ascii=False)
    phase = result.get("phase", "")
    interview.status = "finished" if result.get("finished") else phase.lower()
    if result.get("finished"):
        interview.ended_at = datetime.now()
    db.commit()


def _current_dim_name(result: dict) -> str | None:
    progress = compute_progress(result)
    return progress.get("current_dimension") or None


def _run_evaluation(interview: Interview, db: Session) -> None:
    """调用评估 Agent,报告写入 Interview.report。失败不抛(留空可手动重试)。"""
    try:
        job = interview.job
        cand = interview.candidate
        dims = json.loads(job.dimensions or "[]")
        parsed = json.loads(cand.parsed_resume) if cand.parsed_resume else None
        messages = [
            {"role": m.role, "text": m.text} for m in interview.messages
        ]
        report = evaluate(
            job_title=job.title,
            dimensions=dims,
            parsed_resume=json.dumps(parsed, ensure_ascii=False) if parsed else None,
            messages=messages,
        )
        interview.report = json.dumps(report, ensure_ascii=False)
        db.commit()
        logger.info("面试 %s 评估完成:总分 %s", interview.id, report.get("summary_score"))
    except Exception as e:  # noqa: BLE001  评估失败不中断面试流程,报告留空可重试
        logger.exception("面试 %s 评估失败: %s", interview.id, e)


def _to_turn(result: dict) -> InterviewTurn:
    if result.get("finished"):
        agent_question = result.get("closing_message") or "面试已结束。"
    else:
        history = result.get("history") or []
        agent_question = history[-1]["text"] if history else ""
    return InterviewTurn(
        agent_question=agent_question,
        action=result.get("action", ""),
        dimension=_current_dim_name(result),
        assess=result.get("assess"),
        progress=compute_progress(result),
        finished=bool(result.get("finished")),
    )


VALID_STYLES = {"pro", "friendly", "pressure"}


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
    if body.style not in VALID_STYLES:
        raise HTTPException(422, f"未知面试官风格 {body.style!r},可选 {sorted(VALID_STYLES)}")

    interview = Interview(
        job_id=job.id, candidate_id=cand.id, status="created", style=body.style
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.get("", response_model=list[InterviewListItem])
def list_interviews(db: Session = Depends(get_db)):
    rows = db.query(Interview).order_by(Interview.created_at.desc()).all()
    items = []
    for iv in rows:
        report = json.loads(iv.report) if iv.report else None
        items.append(
            {
                "id": iv.id,
                "status": iv.status,
                "job_title": iv.job.title if iv.job else "",
                "candidate_name": iv.candidate.name if iv.candidate else None,
                "summary_score": report.get("summary_score") if report else None,
                "created_at": iv.created_at,
            }
        )
    return items


@router.get("/comparison")
def comparison(db: Session = Depends(get_db)):
    """多候选人横向对比(按岗位分组):同一岗位已完成面试的维度得分 + 总分。

    放在 /{interview_id} 之前注册,避免路径被当作 interview_id 匹配。
    """
    rows = (
        db.query(Interview)
        .filter(Interview.status == "finished", Interview.report.isnot(None))
        .order_by(Interview.job_id, Interview.created_at)
        .all()
    )
    groups: dict[int, dict] = {}
    for iv in rows:
        report = json.loads(iv.report)
        g = groups.setdefault(
            iv.job_id,
            {
                "job_id": iv.job_id,
                "job_title": iv.job.title if iv.job else "",
                "dimensions": [d["name"] for d in report.get("dimensions", [])],
                "candidates": [],
            },
        )
        g["candidates"].append(
            {
                "interview_id": iv.id,
                "candidate_name": iv.candidate.name if iv.candidate else None,
                "summary_score": report.get("summary_score"),
                "suggestion": report.get("suggestion", ""),
                "scores": [d.get("score") for d in report.get("dimensions", [])],
            }
        )
    for g in groups.values():
        g["candidates"].sort(key=lambda c: c["summary_score"] or 0, reverse=True)
    return {"groups": list(groups.values())}


@router.get("/{interview_id}", response_model=InterviewOut)
def get_interview(interview_id: int, db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    return interview


@router.post("/{interview_id}/message", response_model=InterviewTurn)
def send_message(
    interview_id: int,
    body: InterviewMessageIn,
    db: Session = Depends(get_db),
):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    if interview.status == "finished":
        raise HTTPException(409, "面试已结束,无法继续回答")

    state = _load_state(interview)

    # 开场白轮:history 为空,生成开场问题(忽略 reply)
    if not state.get("history"):
        result = _get_graph().invoke(state)
        _persist(interview, result, db)
        _record_messages(interview, result, role="agent", reply="", db=db)
        return _to_turn(result)

    # 正常轮:必须先有回答
    reply = (body.reply or "").strip()
    if not reply:
        raise HTTPException(422, "请先回答问题再提交")
    state["candidate_reply"] = reply
    result = _get_graph().invoke(state)

    _record_messages(interview, result, role="candidate", reply=reply, db=db)
    _persist(interview, result, db)
    _record_messages(interview, result, role="agent", reply="", db=db)
    # 收尾后自动生成评估报告
    if result.get("finished"):
        _run_evaluation(interview, db)
    return _to_turn(result)


def _record_messages(
    interview: Interview,
    result: dict,
    *,
    role: str,
    reply: str,
    db: Session,
) -> None:
    """把本轮消息写入 interview_messages(审计/回放/评估证据)。"""
    dim = _current_dim_name(result)
    if role == "candidate":
        msg = InterviewMessage(
            interview_id=interview.id,
            role="candidate",
            text=reply,
            dimension=dim,
            assess=None,
        )
    else:
        # agent 消息:开场白或下一问;assess 记录本轮质量判断(开场轮为 None)
        history = result.get("history") or []
        text = history[-1]["text"] if history else ""
        assess = result.get("assess")
        msg = InterviewMessage(
            interview_id=interview.id,
            role="agent",
            text=text,
            dimension=dim,
            assess=json.dumps(assess, ensure_ascii=False) if assess else None,
        )
    db.add(msg)
    db.commit()


@router.get("/{interview_id}/messages", response_model=list[MessageOut])
def get_messages(interview_id: int, db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    return interview.messages


@router.get("/{interview_id}/state", response_model=InterviewStateOut)
def get_state(interview_id: int, db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    state = _load_state(interview)
    return InterviewStateOut(status=interview.status, progress=compute_progress(state))


@router.post("/{interview_id}/evaluate")
def trigger_evaluate(interview_id: int, db: Session = Depends(get_db)):
    """手动触发评估(收尾后已自动触发;此处用于失败重试/中途查看)。"""
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    _run_evaluation(interview, db)
    if not interview.report:
        raise HTTPException(500, "评估失败,请稍后重试")
    return {"interview_id": interview_id, "report": json.loads(interview.report)}
