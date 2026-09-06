"""面试状态机冒烟测试。

用 mock LLM(注入 fake judge)保证确定性、可离线运行、无 API Key 依赖。
覆盖:开场白 / 追问 / 推进 / 非法 action 兜底 / 单维度追问上限 / 全场上限强制收尾 / 收尾。
"""
from app.agents.interviewer.graph import build_graph
from app.agents.interviewer.state import (
    ACTION_CLOSING,
    ACTION_CONTINUE_DIMENSION,
    ACTION_GO_BEHAVIORAL,
    ACTION_NEXT_DIMENSION,
    PHASE_BEHAVIORAL,
    PHASE_CANDIDATE_QA,
    PHASE_CLOSING,
    PHASE_PROBING,
    initial_state,
)

DIMS = [
    {"name": "Python 编程", "type": "hard", "weight": 0.3, "keywords": ["Python", "asyncio"]},
    {"name": "沟通表达", "type": "soft", "weight": 0.2, "keywords": ["协作"]},
]


def make_judge(action=ACTION_CONTINUE_DIMENSION, next_q="下一个问题", answered=True, quality=7):
    """构造 fake LLM:记录调用,返回固定协议。"""
    calls = []

    def judge(system, user):
        calls.append({"system": system, "user": user})
        return {
            "thinking": "内部推理",
            "assess": {"answered": answered, "quality": quality, "issue": "点评", "evidence": "证据"},
            "next_question": next_q,
            "action": action,
        }

    return judge, calls


def new_state(**kw):
    return initial_state(interview_id=1, dimensions=DIMS, **kw)


def test_opening_no_history():
    """无历史 → 开场白轮:只出问题,不计数,进入 PROBING。"""
    judge, calls = make_judge(next_q="请先做自我介绍")
    app = build_graph(judge)
    result = app.invoke(new_state())

    assert len(result["history"]) == 1
    assert result["history"][0] == {"role": "agent", "text": "请先做自我介绍"}
    assert result["total_questions"] == 0
    assert result["finished"] is False
    assert result["phase"] == PHASE_PROBING
    assert result["dim_question_count"] == {}
    # 开场白模式应走"开场"prompt
    assert "开场白" in calls[0]["user"]


def test_continue_dimension():
    """正常轮:LLM 选择继续追问 → 计数 +1,phase 不变。"""
    judge, _ = make_judge()
    app = build_graph(judge)
    state = new_state()
    state["history"] = [{"role": "agent", "text": "自我介绍?"}]
    state["phase"] = PHASE_PROBING  # 开场白轮已把 phase 推进到 PROBING
    state["candidate_reply"] = "我是张三,3 年 Python 后端经验"
    result = app.invoke(state)

    assert result["total_questions"] == 1
    assert result["action"] == ACTION_CONTINUE_DIMENSION
    assert result["phase"] == PHASE_PROBING
    assert result["dim_question_count"] == {"Python 编程": 1}
    assert result["finished"] is False
    # 历史追加:候选人回答 + 下一问
    assert result["history"][-2] == {"role": "candidate", "text": "我是张三,3 年 Python 后端经验"}
    assert result["history"][-1] == {"role": "agent", "text": "下一个问题"}


def test_next_dimension_enters_behavioral_phase():
    """下一维度是软素质时,服务端同步切换到行为面试阶段。"""
    judge, _ = make_judge(action=ACTION_NEXT_DIMENSION)
    app = build_graph(judge)
    state = new_state()
    state["history"] = [{"role": "agent", "text": "讲一个项目"}]
    state["candidate_reply"] = "这个维度我可以了"
    result = app.invoke(state)

    assert result["dim_idx"] == 1
    assert result["action"] == ACTION_GO_BEHAVIORAL
    assert result["phase"] == PHASE_BEHAVIORAL
    assert result["dim_question_count"] == {"沟通表达": 1}  # 推进后的新维度计入本轮这一问
    assert result["total_questions"] == 1


def test_illegal_action_fallback():
    """LLM 返回非法 action → 服务端修正为 CONTINUE_DIMENSION。"""
    judge, _ = make_judge(action="RUN_AWAY")
    app = build_graph(judge)
    state = new_state()
    state["history"] = [{"role": "agent", "text": "?"}]
    state["phase"] = PHASE_PROBING
    state["candidate_reply"] = "你好"
    result = app.invoke(state)

    assert result["action"] == ACTION_CONTINUE_DIMENSION
    assert result["phase"] == PHASE_PROBING


def test_dim_question_cap_force_next():
    """单维度已达上限(3 问)时 LLM 仍想继续追问 → 服务端强制推进。"""
    judge, _ = make_judge(action=ACTION_CONTINUE_DIMENSION)
    app = build_graph(judge)
    state = new_state(max_q_per_dim=3)
    state["history"] = [{"role": "agent", "text": "?"}]
    state["candidate_reply"] = "回答"
    state["dim_question_count"] = {"Python 编程": 3}  # 已问满 3 次
    result = app.invoke(state)

    assert result["action"] == ACTION_GO_BEHAVIORAL
    assert result["dim_idx"] == 1


def test_total_questions_cap_force_closing():
    """全场已达 15 问上限 → 直接收尾,不再调用 LLM。"""
    judge, calls = make_judge()
    app = build_graph(judge)
    state = new_state(max_total_q=15)
    state["history"] = [{"role": "agent", "text": "?"}, {"role": "candidate", "text": "答"}]
    state["total_questions"] = 15
    state["candidate_reply"] = "还有话说"
    result = app.invoke(state)

    assert result["phase"] == PHASE_CLOSING
    assert result["finished"] is True
    assert result["action"] == ACTION_CLOSING
    assert calls == []  # 上限兜底时 LLM 不再被调用
    assert result["history"][-2] == {"role": "candidate", "text": "还有话说"}
    assert result["assess"] is None  # 不复用上一轮的评分。


def test_closing():
    """LLM 主动选择收尾 → 生成收尾语,finished=True。"""
    judge, _ = make_judge(action=ACTION_CLOSING)
    app = build_graph(judge)
    state = new_state()
    state["history"] = [{"role": "agent", "text": "?"}]
    state["phase"] = PHASE_CANDIDATE_QA
    state["dim_idx"] = 1
    state["candidate_reply"] = "没有其他想补充的"
    result = app.invoke(state)

    assert result["phase"] == PHASE_CLOSING
    assert result["finished"] is True
    assert result["action"] == ACTION_CLOSING
    assert result["closing_message"]


def test_early_closing_is_rejected_by_server():
    judge, _ = make_judge(action=ACTION_CLOSING)
    app = build_graph(judge)
    state = new_state()
    state["history"] = [{"role": "agent", "text": "?"}]
    state["candidate_reply"] = "想提前结束"
    result = app.invoke(state)

    assert result["finished"] is False
    assert result["action"] == ACTION_GO_BEHAVIORAL
    assert result["phase"] == PHASE_BEHAVIORAL
    assert "沟通表达" in result["history"][-1]["text"]


def test_assess_quality_is_robust_and_clamped():
    judge, _ = make_judge(quality=99)
    app = build_graph(judge)
    state = new_state()
    state["history"] = [{"role": "agent", "text": "?"}]
    state["candidate_reply"] = "回答"
    assert app.invoke(state)["assess"]["quality"] == 10

    judge, _ = make_judge(quality="优秀")
    app = build_graph(judge)
    assert app.invoke(state)["assess"]["quality"] == 5
