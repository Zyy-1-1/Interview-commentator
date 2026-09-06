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
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.exc import StaleDataError

from ..agents.evaluator import evaluate
from ..agents.interviewer.graph import build_llm_graph, compute_progress
from ..agents.interviewer.state import PHASE_CANDIDATE_QA, PHASE_CLOSING, initial_state
from ..db import get_db
from ..config import settings
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
from ..security import (
    CANDIDATE_HEADER,
    REVIEW_HEADER,
    require_admin,
    verify_candidate_access,
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
            max_q_per_dim=settings.max_q_per_dim,
            max_total_q=settings.max_total_q,
        )
    return state


def _persist(
    interview: Interview,
    result: dict,
    turn: InterviewTurn,
    *,
    request_id: str | None,
    request_reply: str,
) -> None:
    """把状态机输出写回快照；事务由调用方统一提交。"""
    snap = dict(result)
    snap.pop("candidate_reply", None)  # 注入字段不入库
    # 不持久化模型的自由推理文本，只保留决策协议所需字段。
    if isinstance(snap.get("last_output"), dict):
        last_output = dict(snap["last_output"])
        last_output.pop("thinking", None)
        snap["last_output"] = last_output
    if request_id:
        snap["last_request_id"] = request_id
        snap["last_request_reply"] = request_reply
        snap["last_turn"] = turn.model_dump(mode="json")
    interview.state = json.dumps(snap, ensure_ascii=False)
    phase = result.get("phase", "")
    interview.status = "finished" if result.get("finished") else phase.lower()
    if interview.started_at is None:
        interview.started_at = datetime.now()
    if result.get("finished"):
        interview.ended_at = datetime.now()


def _current_dim_name(result: dict) -> str | None:
    progress = compute_progress(result)
    return progress.get("current_dimension") or None


def _run_evaluation(interview: Interview, db: Session) -> None:
    """调用评估 Agent,报告写入 Interview.report。失败不抛(留空可手动重试)。"""
    try:
        job = interview.job
        cand = interview.candidate
        session_state = _load_state(interview)
        dims = session_state["dimensions"]
        parsed = json.loads(cand.parsed_resume) if cand.parsed_resume else None
        messages = [
            {"id": m.id, "role": m.role, "text": m.text, "dimension": m.dimension}
            for m in interview.messages
        ]
        report = evaluate(
            job_title=session_state.get("job_title") or job.title,
            dimensions=dims,
            parsed_resume=json.dumps(parsed, ensure_ascii=False) if parsed else None,
            messages=messages,
        )
        interview.report = json.dumps(report, ensure_ascii=False)
        db.commit()
        logger.info("面试 %s 评估完成:总分 %s", interview.id, report.get("summary_score"))
    except Exception as e:  # noqa: BLE001  评估失败不中断面试流程,报告留空可重试
        db.rollback()
        logger.warning("面试 %s 评估失败: %s", interview.id, type(e).__name__)


def _to_turn(result: dict) -> InterviewTurn:
    if result.get("finished"):
        agent_question = result.get("closing_message") or "面试已结束。"
    else:
        history = result.get("history") or []
        agent_question = history[-1]["text"] if history else ""
    return InterviewTurn(
        agent_question=agent_question,
        action=result.get("action", ""),
        dimension=(
            None
            if result.get("finished")
            or result.get("phase") in {PHASE_CANDIDATE_QA, PHASE_CLOSING}
            else _current_dim_name(result)
        ),
        assess=result.get("assess"),
        progress=compute_progress(result),
        finished=bool(result.get("finished")),
    )


VALID_STYLES = {"pro", "friendly", "pressure"}


def _authorize_interview(
    interview: Interview,
    candidate_token: str | None,
    admin_passphrase: str | None,
) -> None:
    verify_candidate_access(
        interview.candidate.access_token_hash,
        candidate_token,
        admin_passphrase,
    )


@router.post("", response_model=InterviewOut)
def create_interview(
    body: InterviewCreate,
    db: Session = Depends(get_db),
    candidate_token: Annotated[str | None, Header(alias=CANDIDATE_HEADER)] = None,
    admin_passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    job = db.get(Job, body.job_id)
    cand = db.get(Candidate, body.candidate_id)
    if not job:
        raise HTTPException(404, "岗位不存在")
    if not cand:
        raise HTTPException(404, "候选人不存在")
    verify_candidate_access(cand.access_token_hash, candidate_token, admin_passphrase)
    if job.status != "approved":
        raise HTTPException(422, "该岗位尚未审核上架")
    if not job.dimensions:
        raise HTTPException(422, "该岗位尚未完成 JD 分析(维度缺失),请先重试 JD 分析")
    if body.style not in VALID_STYLES:
        raise HTTPException(422, f"未知面试官风格 {body.style!r},可选 {sorted(VALID_STYLES)}")

    interview = Interview(
        job_id=job.id, candidate_id=cand.id, status="created", style=body.style
    )
    db.add(interview)
    db.flush()
    interview.state = json.dumps(_load_state(interview), ensure_ascii=False)
    db.commit()
    db.refresh(interview)
    return interview


@router.get("", response_model=list[InterviewListItem])
def list_interviews(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    rows = (
        db.query(Interview)
        .options(joinedload(Interview.job), joinedload(Interview.candidate))
        .order_by(Interview.created_at.desc())
        .all()
    )
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
def comparison(
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """多候选人横向对比(按岗位分组):同一岗位已完成面试的维度得分 + 总分。

    放在 /{interview_id} 之前注册,避免路径被当作 interview_id 匹配。
    """
    rows = (
        db.query(Interview)
        .options(joinedload(Interview.job), joinedload(Interview.candidate))
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
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    candidate_token: Annotated[str | None, Header(alias=CANDIDATE_HEADER)] = None,
    admin_passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    _authorize_interview(interview, candidate_token, admin_passphrase)
    return interview


@router.post("/{interview_id}/message", response_model=InterviewTurn)
def send_message(
    interview_id: int,
    body: InterviewMessageIn,
    db: Session = Depends(get_db),
    candidate_token: Annotated[str | None, Header(alias=CANDIDATE_HEADER)] = None,
    admin_passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    _authorize_interview(interview, candidate_token, admin_passphrase)

    state = _load_state(interview)
    request_id = body.request_id
    request_reply = (body.reply or "").strip()
    cached = _cached_turn(state, request_id, request_reply)
    if cached is not None:
        return cached
    if interview.status == "finished":
        raise HTTPException(409, "面试已结束,无法继续回答")

    # 开场白轮:history 为空,生成开场问题(忽略 reply)
    if not state.get("history"):
        result = _get_graph().invoke(state)
        turn = _to_turn(result)
        _persist(
            interview,
            result,
            turn,
            request_id=request_id,
            request_reply="",
        )
        db.add(
            InterviewMessage(
                interview_id=interview.id,
                role="agent",
                text=turn.agent_question,
                dimension=None,
                assess=None,
            )
        )
        return _commit_turn(db, interview, turn, request_id, "")

    # 正常轮:必须先有回答
    reply = request_reply
    if not reply:
        raise HTTPException(422, "请先回答问题再提交")
    # 回答对应的是调用状态机前屏幕上已经展示的问题维度。
    previous_question = next(
        (message for message in reversed(interview.messages) if message.role == "agent"),
        None,
    )
    answered_dimension = previous_question.dimension if previous_question else None
    state["candidate_reply"] = reply
    result = _get_graph().invoke(state)
    turn = _to_turn(result)

    db.add_all(
        [
            InterviewMessage(
                interview_id=interview.id,
                role="candidate",
                text=reply,
                dimension=answered_dimension,
                assess=(
                    json.dumps(result.get("assess"), ensure_ascii=False)
                    if result.get("assess")
                    else None
                ),
            ),
            InterviewMessage(
                interview_id=interview.id,
                role="agent",
                text=turn.agent_question,
                dimension=turn.dimension,
                assess=None,
            ),
        ]
    )
    _persist(
        interview,
        result,
        turn,
        request_id=request_id,
        request_reply=reply,
    )
    committed_turn = _commit_turn(db, interview, turn, request_id, reply)
    # 收尾后自动生成评估报告
    if result.get("finished"):
        _run_evaluation(interview, db)
    return committed_turn


def _cached_turn(
    state: dict,
    request_id: str | None,
    request_reply: str,
) -> InterviewTurn | None:
    if not request_id or state.get("last_request_id") != request_id:
        return None
    if state.get("last_request_reply", "") != request_reply:
        raise HTTPException(409, "同一 request_id 不能用于不同内容")
    payload = state.get("last_turn")
    if not isinstance(payload, dict):
        raise HTTPException(409, "该请求已处理,请刷新面试状态")
    return InterviewTurn.model_validate(payload)


def _commit_turn(
    db: Session,
    interview: Interview,
    turn: InterviewTurn,
    request_id: str | None,
    request_reply: str,
) -> InterviewTurn:
    """原子提交状态与两侧消息；并发重复请求优先回放已提交结果。"""
    try:
        db.commit()
        return turn
    except StaleDataError as e:
        db.rollback()
        db.expire_all()
        current = db.get(Interview, interview.id)
        if current is not None:
            cached = _cached_turn(_load_state(current), request_id, request_reply)
            if cached is not None:
                return cached
        raise HTTPException(409, "面试状态已被另一请求更新,请刷新后重试") from e


@router.get("/{interview_id}/messages", response_model=list[MessageOut])
def get_messages(
    interview_id: int,
    db: Session = Depends(get_db),
    candidate_token: Annotated[str | None, Header(alias=CANDIDATE_HEADER)] = None,
    admin_passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    _authorize_interview(interview, candidate_token, admin_passphrase)
    return interview.messages


@router.get("/{interview_id}/state", response_model=InterviewStateOut)
def get_state(
    interview_id: int,
    db: Session = Depends(get_db),
    candidate_token: Annotated[str | None, Header(alias=CANDIDATE_HEADER)] = None,
    admin_passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    _authorize_interview(interview, candidate_token, admin_passphrase)
    state = _load_state(interview)
    return InterviewStateOut(status=interview.status, progress=compute_progress(state))


@router.post("/{interview_id}/evaluate")
def trigger_evaluate(
    interview_id: int,
    db: Session = Depends(get_db),
    candidate_token: Annotated[str | None, Header(alias=CANDIDATE_HEADER)] = None,
    admin_passphrase: Annotated[str | None, Header(alias=REVIEW_HEADER)] = None,
):
    """仅在已收尾且报告缺失时补做评估；已有报告直接返回缓存。"""
    interview = db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(404, "面试不存在")
    _authorize_interview(interview, candidate_token, admin_passphrase)
    if interview.status != "finished":
        raise HTTPException(409, "面试尚未结束,不能生成最终报告")
    if interview.report:
        return {"interview_id": interview_id, "report": json.loads(interview.report)}
    _run_evaluation(interview, db)
    if not interview.report:
        raise HTTPException(500, "评估失败,请稍后重试")
    return {"interview_id": interview_id, "report": json.loads(interview.report)}
