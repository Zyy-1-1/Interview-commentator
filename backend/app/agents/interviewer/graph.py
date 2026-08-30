"""面试官 Agent 状态机(LangGraph StateGraph,技术方案 5.3/5.4/5.5)。

设计原则:**LLM 负责"聪明的判断",状态机负责"流程的可靠性"**。
- 每个节点/条件边由服务端二次校验 action 枚举与轮次上限,LLM 出错时兜底修正;
- 一次 invoke = 推进一个回合(生成开场白 / 判断并出下一问 / 收尾);
- 面试是异步交互,多轮 = 多次 invoke,状态由调用方在数据库持久化(Interview.state 快照)。

拓扑:
    START → interviewer ──(route)──→ closing → END
                              └─────→ END
"""
import logging
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from ...llm import chat_json

from .prompts import build_system_prompt, build_user_prompt
from .state import (
    ACTION_CLOSING,
    ACTION_CONTINUE_DIMENSION,
    ACTION_GO_BEHAVIORAL,
    ACTION_GO_CANDIDATE_QA,
    ACTION_NEXT_DIMENSION,
    DEFAULT_QUESTION,
    PHASE_BEHAVIORAL,
    PHASE_CANDIDATE_QA,
    PHASE_CLOSING,
    PHASE_PROBING,
    VALID_ACTIONS,
    InterviewState,
    current_dimension,
)

logger = logging.getLogger(__name__)

# LLM 判断器签名:输入 system prompt + user prompt,返回严格 JSON 协议 dict(见 prompts.py)。
Judge = Callable[[str, str], dict[str, Any]]

DEFAULT_CLOSING = (
    "本轮面试到这里就结束了。感谢你的时间与坦诚,我们会尽快整理反馈,祝你一切顺利。"
)


# ---------- 兜底 ----------
def _fallback_assess() -> dict[str, Any]:
    return {"answered": True, "quality": 5, "issue": "LLM 调用失败,按一般回答兜底", "evidence": ""}


def _normalize_assess(output: dict[str, Any]) -> dict[str, Any]:
    assess = output.get("assess")
    if not isinstance(assess, dict):
        return _fallback_assess()
    return {
        "answered": bool(assess.get("answered", True)),
        "quality": int(assess.get("quality", 5) or 0),
        "issue": str(assess.get("issue", "") or ""),
        "evidence": str(assess.get("evidence", "") or ""),
    }


def _normalize_action(action: Any) -> str:
    """服务端兜底:action 不在枚举内 → 修正为默认继续追问。"""
    if isinstance(action, str) and action in VALID_ACTIONS:
        return action
    logger.warning("面试官返回非法 action: %r,回退为 %s", action, ACTION_CONTINUE_DIMENSION)
    return ACTION_CONTINUE_DIMENSION


def _fallback_output(state: InterviewState) -> dict[str, Any]:
    """LLM 调用失败时的兜底输出(不中断面试流程)。"""
    if not state.get("history"):
        return {
            "thinking": "LLM 失败兜底开场",
            "assess": _fallback_assess(),
            "next_question": "你好,我是本次面试的面试官。面试大约 15 分钟,我们先从你的自我介绍开始吧。",
            "action": ACTION_CONTINUE_DIMENSION,
        }
    return {
        "thinking": "LLM 失败兜底追问",
        "assess": _fallback_assess(),
        "next_question": DEFAULT_QUESTION,
        "action": ACTION_CONTINUE_DIMENSION,
    }


# ---------- 应用 action:推进 phase / dim_idx / 计数 ----------
def _apply_action(state: InterviewState, action: str) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    dims = state.get("dimensions") or []
    dim = current_dimension(state)
    dim_name = dim.get("name", "") if dim else ""
    counts = dict(state.get("dim_question_count") or {})

    if action == ACTION_NEXT_DIMENSION:
        # 推进到下一维度,重置当前维度计数
        counts.pop(dim_name, None)
        updates["dim_idx"] = state.get("dim_idx", 0) + 1
    elif action == ACTION_GO_BEHAVIORAL:
        # 跳到第一个软素质维度
        soft_idx = next((i for i, d in enumerate(dims) if d.get("type") == "soft"), len(dims))
        updates["phase"] = PHASE_BEHAVIORAL
        updates["dim_idx"] = soft_idx
        counts.pop(dim_name, None)
    elif action == ACTION_GO_CANDIDATE_QA:
        updates["phase"] = PHASE_CANDIDATE_QA
    elif action == ACTION_CLOSING:
        updates["phase"] = PHASE_CLOSING
        updates["finished"] = True

    # CONTINUE_DIMENSION 与 NEXT_DIMENSION 后都只记录"本轮这一问"的计数,交给主流程统一 +1
    updates["dim_question_count"] = counts
    return updates


# ---------- 节点 ----------
def _make_interviewer(judge: Judge) -> Callable[[InterviewState], dict[str, Any]]:
    def interviewer_node(state: InterviewState) -> dict[str, Any]:
        # 0) 服务端兜底(最高优先级):全场轮次上限 → 无论 LLM 说什么都强制收尾
        if state.get("total_questions", 0) >= state.get("max_total_q", 15):
            logger.info("全场已达 %s 问上限,强制收尾", state["total_questions"])
            return {"phase": PHASE_CLOSING, "finished": True, "action": ACTION_CLOSING}

        # 1) LLM 决策(开场白 / 判断)
        system = build_system_prompt(state.get("dimensions") or [])
        user = build_user_prompt(state)
        try:
            output = judge(system, user) or {}
        except Exception as e:  # noqa: BLE001  LLM 失败不影响状态机继续
            logger.exception("面试官 LLM 调用失败: %s", e)
            output = _fallback_output(state)

        # 2) 开场白轮(history 为空):只抛出问题,不判断质量、不计数,随后进入正式考察阶段
        if not state.get("history"):
            return {
                "history": [{"role": "agent", "text": output.get("next_question") or DEFAULT_QUESTION}],
                "last_output": output,
                "action": ACTION_CONTINUE_DIMENSION,
                "phase": PHASE_PROBING,
                "finished": False,
            }

        # 3) 正常轮:校验 action + 单维度追问上限
        action = _normalize_action(output.get("action"))
        dim = current_dimension(state)
        dim_name = dim.get("name", "") if dim else ""
        asked = state.get("dim_question_count", {}).get(dim_name, 0)
        if action == ACTION_CONTINUE_DIMENSION and asked >= state.get("max_q_per_dim", 3):
            logger.info("维度「%s」已达 %s 问上限,强制推进到下一维度", dim_name, asked)
            action = ACTION_NEXT_DIMENSION

        # 4) 应用 action,推进状态
        updates = _apply_action(state, action)
        next_question = output.get("next_question") or DEFAULT_QUESTION
        history = list(state.get("history") or [])
        reply = (state.get("candidate_reply") or "").strip()
        if reply:
            history.append({"role": "candidate", "text": reply})
        history.append({"role": "agent", "text": next_question})

        updates.update(
            {
                "history": history,
                "last_output": output,
                "action": action,
                "assess": _normalize_assess(output),
                "total_questions": state.get("total_questions", 0) + 1,
                "dim_question_count": updates.get("dim_question_count"),
                "finished": bool(updates.get("finished", False)),
            }
        )
        # 本轮这一问记入"当前(推进后)维度"的计数
        counts = dict(updates.get("dim_question_count") or state.get("dim_question_count") or {})
        new_dim = current_dimension({**state, **updates})
        new_name = new_dim.get("name", "") if new_dim else ""
        if new_name:
            counts[new_name] = counts.get(new_name, 0) + 1
        updates["dim_question_count"] = counts
        return updates

    return interviewer_node


def _closing_node(state: InterviewState) -> dict[str, Any]:
    return {
        "closing_message": DEFAULT_CLOSING,
        "phase": PHASE_CLOSING,
        "finished": True,
    }


def _route(state: InterviewState) -> str:
    if state.get("finished") or state.get("phase") == PHASE_CLOSING:
        return "closing"
    return END  # 本轮结束,等待候选人下一条回答


def build_graph(judge: Judge) -> Any:
    """构建并编译面试状态机。judge 可注入(测试用 fake,生产用真实 LLM 封装)。"""
    graph = StateGraph(InterviewState)
    graph.add_node("interviewer", _make_interviewer(judge))
    graph.add_node("closing", _closing_node)
    graph.add_edge(START, "interviewer")
    graph.add_conditional_edges(
        "interviewer",
        _route,
        {"closing": "closing", END: END},
    )
    graph.add_edge("closing", END)
    return graph.compile()


def llm_judge(system: str, user: str) -> dict[str, Any]:
    """生产环境默认判断器:走 DeepSeek(OpenAI 兼容,强制 JSON 输出)。"""
    return chat_json(system, user, temperature=0.4)


def build_llm_graph() -> Any:
    """编译一个接真实 LLM 的状态机实例(API 层使用)。"""
    return build_graph(llm_judge)


def compute_progress(state: InterviewState) -> dict[str, Any]:
    """供前端展示的进度信息(面试当前维度/已问次数/上限)。"""
    dim = current_dimension(state)
    name = dim.get("name", "") if dim else ""
    return {
        "phase": state.get("phase", ""),
        "current_dimension": name,
        "dim_question_count": dict(state.get("dim_question_count") or {}),
        "total_questions": state.get("total_questions", 0),
        "max_per_dim": state.get("max_q_per_dim", 3),
        "max_total_q": state.get("max_total_q", 15),
    }
