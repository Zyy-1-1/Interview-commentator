"""模块⑤ 评估 Agent(技术方案 4.5)。

输入:岗位维度 + 候选人简历摘要 + 完整面试消息流;
处理:一次 LLM 调用,分维度总结证据(引用候选人原话)+ 打分;
输出:标准化评估报告 JSON(供报告页 echarts 雷达图 + HR 决策)。

报告结构:
{
  "summary_score": 78,                       # 0-100 总分(按维度权重综合)
  "suggestion": "建议进入二面",
  "dimensions": [
    {"name": "Python 编程", "score": 8.0, "evidence": ["候选人原话:...", "..."]}
  ],
  "strengths": ["..."],
  "risks": ["简历与回答有出入:..."],
  "next_step_questions": ["二面建议重点考察:..."]
}
"""
import json
from typing import Any

from ..llm import chat_json

# 面试记录按角色标签拼接,供评估员阅读
ROLE_LABEL = {"agent": "面试官", "candidate": "候选人"}

SYSTEM_PROMPT = """你是资深招聘评估员,负责对一场结构化面试输出标准化评估报告。
打分口径:每个考察维度按「简历基础 + 回答深度 + STAR 完整度 + 沟通质量」综合打分,满分 10。

要求:
1. dimensions 必须覆盖岗位的全部考察维度,每个维度:
   - score:0-10,一位小数;
   - evidence:摘录候选人**原话片段**(必须是对话里真实出现的原话,不要编造),至少 1 条;
2. strengths:2-4 条候选人亮点;
3. risks:列出风险,包括"回答深度不足/简历与回答不一致/有维度未考察到"等(对话中没有体现的维度要如实标注);
4. summary_score:0-100 总分,按各维度 weight 加权计算,硬素质权重优先;
5. suggestion:给出录用建议(建议进入二面 / 待定观察 / 建议淘汰);
6. next_step_questions:二面建议重点考察的问题,2-3 条;
7. 严格输出 JSON,不要多余文字。

输出 JSON 结构(严格遵循):
{
  "summary_score": 78,
  "suggestion": "建议进入二面",
  "dimensions": [
    {"name": "Python 编程", "score": 8.0, "evidence": ["候选人提到用 asyncio 优化了接口 QPS"]}
  ],
  "strengths": ["技术基础扎实", "表达结构清晰"],
  "risks": ["行为类维度考察不充分", "简历项目经历未深挖"],
  "next_step_questions": ["二面重点考察:系统设计能力"]
}"""


def build_user_prompt(
    *,
    job_title: str,
    dimensions: list[dict[str, Any]],
    parsed_resume: str | None,
    messages: list[dict[str, str]],
    max_resume_chars: int = 1500,
    max_messages: int = 40,
) -> str:
    """拼装评估输入:岗位 / 维度 / 简历摘要 / 面试记录(截断防超长)。"""
    lines = [
        f"【岗位】{job_title}",
        f"【考察维度】{json.dumps(dimensions, ensure_ascii=False)}",
        f"【候选人简历摘要】{(parsed_resume or '(未解析到简历)')[:max_resume_chars]}",
        "【面试记录】",
    ]
    for m in messages[-max_messages:]:
        role = ROLE_LABEL.get(m.get("role", "agent"), m.get("role", ""))
        text = (m.get("text") or "")[:500]
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def evaluate(
    *,
    job_title: str,
    dimensions: list[dict[str, Any]],
    parsed_resume: str | None,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """评估 Agent 主入口:一次 LLM 调用产出报告 JSON。"""
    user = build_user_prompt(
        job_title=job_title,
        dimensions=dimensions,
        parsed_resume=parsed_resume,
        messages=messages,
    )
    result = chat_json(SYSTEM_PROMPT, user, temperature=0.2)
    # 兜底:确保关键字段存在,避免空报告
    if not isinstance(result.get("dimensions"), list):
        raise ValueError("评估未产出有效维度打分")
    result.setdefault("strengths", [])
    result.setdefault("risks", [])
    result.setdefault("next_step_questions", [])
    result.setdefault("suggestion", "待定")
    return result
