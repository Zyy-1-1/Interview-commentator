"""面试状态定义(对齐技术方案 5.2 / 5.5)。

面试是异步交互:每轮 = 候选人提交一条回答 → 状态机推进一个回合 → 下一问。
中间状态由 Interview.state(JSON 快照)持久化,每次从数据库恢复后注入新回答再 invoke。
"""
from typing import Any, NotRequired, TypedDict

# ---------- phase 枚举(方案 5.3 状态转换图) ----------
PHASE_OPENING = "OPENING"                # 开场白 + 暖场
PHASE_PROBING = "PROBING"                # 逐维度考察(硬技能)
PHASE_BEHAVIORAL = "BEHAVIORAL"          # STAR 行为面试(软素质)
PHASE_CANDIDATE_QA = "CANDIDATE_QA"      # 候选人提问环节
PHASE_CLOSING = "CLOSING"                # 收尾 → 触发评估

# ---------- action 枚举(方案 5.5) ----------
ACTION_CONTINUE_DIMENSION = "CONTINUE_DIMENSION"  # 当前维度继续追问
ACTION_NEXT_DIMENSION = "NEXT_DIMENSION"          # 进入下一维度
ACTION_GO_BEHAVIORAL = "GO_BEHAVIORAL"            # 切到行为面试(软素质)
ACTION_GO_CANDIDATE_QA = "GO_CANDIDATE_QA"        # 候选人提问环节
ACTION_CLOSING = "CLOSING"                        # 收尾

VALID_ACTIONS = frozenset(
    {
        ACTION_CONTINUE_DIMENSION,
        ACTION_NEXT_DIMENSION,
        ACTION_GO_BEHAVIORAL,
        ACTION_GO_CANDIDATE_QA,
        ACTION_CLOSING,
    }
)

# 兜底:LLM 未给合法 action 或未给问题时使用
DEFAULT_ACTION = ACTION_CONTINUE_DIMENSION
DEFAULT_QUESTION = "请你结合刚才的内容再多说说,举一个具体的例子。"


class InterviewState(TypedDict, total=False):
    """单场面试的全部可持久化状态。

    除注入/输出字段外,其余字段在 initial_state() 中初始化,可直接 JSON 化存库。
    """

    # ---------- 业务状态(持久化) ----------
    interview_id: NotRequired[int]
    job_title: NotRequired[str]                    # 岗位名(注入面试官人格 prompt)
    style: NotRequired[str]                        # 面试官人格 pro|friendly|pressure
    phase: NotRequired[str]                        # PHASE_*
    dim_idx: NotRequired[int]                      # 当前考察维度下标
    resume_facts: NotRequired[list[dict[str, Any]]]  # 简历原文片段与字符位置，仅作出题背景
    dimensions: NotRequired[list[dict[str, Any]]]  # JD 分析输出的维度清单(见 jd_analyzer)
    dim_question_count: NotRequired[dict[str, int]]  # {维度名: 已问次数}
    total_questions: NotRequired[int]              # 全场已问次数(开场白不计)
    history: NotRequired[list[dict[str, str]]]     # [{"role": "agent"/"candidate", "text": ...}]
    max_q_per_dim: NotRequired[int]                # 每维度最多追问次数
    max_total_q: NotRequired[int]                  # 全场最多提问次数
    pending_verification: NotRequired[list[dict[str, Any]]]  # 待核验点(评估时标红)

    # ---------- 注入(每轮由调用方写入,不入库) ----------
    candidate_reply: NotRequired[str]              # 本轮候选人回答

    # ---------- 输出(本轮结果,由状态机写出) ----------
    last_output: NotRequired[dict[str, Any]]       # LLM 完整协议 {thinking, assess, next_question, action}
    action: NotRequired[str]                       # 服务端校验后的 action
    assess: NotRequired[dict[str, Any] | None]            # 本轮质量判断(归一化后),供消息留痕/评估
    finished: NotRequired[bool]                    # 本轮是否收尾
    closing_message: NotRequired[str]              # 收尾语
    last_request_id: NotRequired[str]              # 最近一次已提交客户端请求 ID
    last_request_reply: NotRequired[str]           # 防止同一请求 ID 被不同内容复用
    last_turn: NotRequired[dict[str, Any]]          # 幂等重试时直接回放的响应


def initial_state(
    *,
    interview_id: int,
    dimensions: list[dict[str, Any]],
    job_title: str = "本岗位",
    style: str = "pro",
    max_q_per_dim: int = 3,
    max_total_q: int = 15,
    resume_facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """创建一份全新的面试状态(默认值对齐 config.py 面试规则)。"""
    return {
        "interview_id": interview_id,
        "job_title": job_title,
        "style": style,
        "phase": PHASE_OPENING,
        "dim_idx": 0,
        "dimensions": dimensions,
        "resume_facts": resume_facts or [],
        "dim_question_count": {},
        "total_questions": 0,
        "history": [],
        "max_q_per_dim": max_q_per_dim,
        "max_total_q": max_total_q,
        "pending_verification": [],
        "finished": False,
    }


def current_dimension(state: InterviewState) -> dict[str, Any] | None:
    """当前正在考察的维度;越界或无维度时返回 None。"""
    dims = state.get("dimensions") or []
    idx = state.get("dim_idx", 0)
    if not dims or idx < 0 or idx >= len(dims):
        return None
    return dims[idx]
