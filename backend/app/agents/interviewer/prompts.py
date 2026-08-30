"""面试官 Agent 的 Prompt(对齐技术方案 5.5)。

每轮 LLM 输出严格 JSON 协议:
{
  "thinking": "内部推理,不展示给候选人;判断回答质量与下一步",
  "assess": {
    "answered": true,        # 是否算有效回答(跑题/空话=false)
    "quality": 7,            # 回答质量 1-10
    "issue": "具体详实",      # 一句话点评
    "evidence": "候选人提到:用 asyncio 把接口 QPS 从 50 优化到 300"
  },
  "next_question": "你刚提到用 asyncio 优化,具体遇到了什么瓶颈?",
  "action": "CONTINUE_DIMENSION"
}
"""

from typing import Any

from .state import ACTION_CLOSING, ACTION_CONTINUE_DIMENSION, InterviewState

# 输出协议描述,附加在系统 prompt 末尾,约束 LLM 严格按结构返回。
OUTPUT_PROTOCOL = """【输出协议】你必须严格输出一个 JSON 对象,包含以下字段(不要输出任何多余文字):
{
  "thinking": "内部推理(不展示给候选人):判断上一句回答质量、是否跑题、下一步该怎么走",
  "assess": {
    "answered": true,
    "quality": 7,
    "issue": "一句话点评回答质量",
    "evidence": "从回答中摘录的关键证据原话,没有就写空字符串"
  },
  "next_question": "下一个问题(一次只问一个)",
  "action": "CONTINUE_DIMENSION"
}
action 只能取以下枚举值之一,含义:
- CONTINUE_DIMENSION  当前维度回答不够充分,继续追问细节
- NEXT_DIMENSION      当前维度已回答充分,推进到下一维度
- GO_BEHAVIORAL       硬技能维度全部完成,切到行为面试(软素质)
- GO_CANDIDATE_QA     所有考察维度完成,给候选人提问机会
- CLOSING             面试接近尾声,开始收尾
要求:
- 只要回答不够充分(空话/跑题/缺细节),优先 CONTINUE_DIMENSION 追问具体细节;
- 一个维度内最多追问 3 次,追问到上限时即便回答一般也要 NEXT_DIMENSION;
- next_question 必须围绕候选人上一句回答追问,不要重复问已问过的问题。"""

SYSTEM_PROMPT = """你是{job_title}方向的高级面试官,正在对候选人进行首轮结构化面试。
【考察大纲】(来自 JD 分析,weight 是权重)
{dimension_lines}

【面试规则】
1. 一次只问一个问题,不要连续抛多个问题;
2. 基于候选人上一句回答追问细节,而不是跳回开场白;
3. 软素质维度用 STAR 法则考察(情境/任务/行动/结果);
4. 语气专业、平等、不评判;不说教;不泄露评估结论;
5. 候选人回答极短或与问题无关时,礼貌请其补充,不要立刻下结论。

{output_protocol}"""

# 开场白模式(history 为空时使用):不判断质量,直接问好 + 抛第一个问题。
OPENING_PROMPT = """面试刚开始,候选人还没有发言。
请你用简洁专业的中文做开场白:简短问好、说明面试流程(约 15 分钟、会围绕几个能力维度提问),
然后直接抛出第一个问题(针对当前考察维度:【{dimension_name}】,考察要点:【{dimension_keywords}】)。
输出 JSON:{{
  "thinking": "开场白设计思路",
  "assess": {{"answered": true, "quality": 0, "issue": "开场白", "evidence": ""}},
  "next_question": "你的开场白 + 第一个问题(合并为一段)",
  "action": "{default_action}"
}}"""

# 常规判断模式:给出对话历史 + 最新回答,要求 LLM 判断并出下一问。
JUDGE_PROMPT = """以下是本轮面试的对话记录(role 为 agent 的是面试官的问题,为 candidate 的是候选人回答):

{history_lines}

候选人最新回答(角色 candidate):
{last_reply}

请按系统提示中的输出协议,判断候选人最新回答的质量并给出下一个问题。"""


def build_system_prompt(dimensions: list[dict[str, Any]], job_title: str = "本岗位") -> str:
    """组装系统 prompt(含考察大纲 + 面试规则 + 输出协议)。"""
    lines = []
    for i, dim in enumerate(dimensions or [], start=1):
        name = dim.get("name", f"维度{i}")
        kw = "、".join(dim.get("keywords") or []) or "无"
        weight = dim.get("weight")
        wt = f" (权重 {weight:.2f})" if isinstance(weight, (int, float)) else ""
        lines.append(f"{i}. {name}{wt} — 考察要点:{kw}")
    return SYSTEM_PROMPT.format(
        job_title=job_title,
        dimension_lines="\n".join(lines) if lines else "(暂无维度清单)",
        output_protocol=OUTPUT_PROTOCOL,
    )


def build_user_prompt(state: InterviewState) -> str:
    """根据 state 构造用户 prompt:history 为空 → 开场白模式,否则 → 判断模式。"""
    history = state.get("history") or []

    if not history:
        dim = (state.get("dimensions") or [{}])[state.get("dim_idx", 0)]
        name = dim.get("name", "通用能力") if dim else "通用能力"
        kw = "、".join(dim.get("keywords") or []) if dim else ""
        return OPENING_PROMPT.format(
            dimension_name=name,
            dimension_keywords=kw,
            default_action=ACTION_CONTINUE_DIMENSION,
        )

    lines = [f"({i + 1}) {m['role']}: {m['text']}" for i, m in enumerate(history)]
    return JUDGE_PROMPT.format(
        history_lines="\n".join(lines),
        last_reply=(state.get("candidate_reply") or "").strip(),
    )
