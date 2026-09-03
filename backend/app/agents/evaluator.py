"""模块⑤ 评估 Agent(技术方案 4.5)。

输入:岗位维度 + 应聘者简历摘要 + 完整面试消息流;
处理:一次 LLM 调用,分维度总结证据(引用应聘者原话)+ 打分;
输出:标准化评估报告 JSON(供报告页 echarts 雷达图 + 应聘者自我提升)。

报告结构:
{
  "summary_score": 78,                       # 0-100 总分(按维度权重综合)
  "suggestion": "与目标岗位匹配度较高,可重点准备系统设计相关问题",
  "dimensions": [
    {"name": "Python 编程", "score": 8.0, "evidence": ["应聘者原话:...", "..."]}
  ],
  "strengths": ["..."],
  "risks": ["回答深度不足:...", "简历与回答有出入:..."],
  "next_step_questions": ["针对性练习:..."]
}
"""
import json
from typing import Any

from ..llm import chat_json

# 面试记录按角色标签拼接,供评估员阅读
ROLE_LABEL = {"agent": "面试官", "candidate": "应聘者"}

SYSTEM_PROMPT = """你是资深面试评估专家,负责为一名求职者(应聘者)的模拟面试输出个人竞争力评估报告。
打分口径:每个考察维度按「简历基础 + 回答深度 + STAR 完整度 + 沟通质量」综合打分,满分 10。

要求:
1. dimensions 必须覆盖岗位的全部考察维度,每个维度:
   - score:0-10,一位小数;
   - evidence:摘录应聘者**原话片段**(必须是对话里真实出现的原话,不要编造),至少 1 条;
2. strengths:2-4 条应聘者的亮点(强项),便于其保持;
3. risks:列出待改进短板,包括"回答深度不足/简历与回答不一致/有维度未考察到"等(对话中没有体现的维度要如实标注);
4. summary_score:0-100 总分,按各维度 weight 加权计算,硬素质权重优先,可解释为该应聘者与目标岗位的匹配度;
5. suggestion:给出竞争力评价与提升方向(如"与目标岗位匹配度较高,重点补强系统设计"),不要用"录用/淘汰"这类 HR 决策口径;
6. next_step_questions:针对性练习建议(具体可执行的学习/准备动作),2-3 条;
7. 严格输出 JSON,不要多余文字。

输出 JSON 结构(严格遵循):
{
  "summary_score": 78,
  "suggestion": "与目标岗位匹配度较高,可重点准备系统设计相关问题",
  "dimensions": [
    {"name": "Python 编程", "score": 8.0, "evidence": ["应聘者提到用 asyncio 优化了接口 QPS"]}
  ],
  "strengths": ["技术基础扎实", "表达结构清晰"],
  "risks": ["行为类维度考察不充分", "简历项目经历未深挖"],
  "next_step_questions": ["针对性练习:补充系统设计小模块实战"]
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
        f"【应聘者简历摘要】{(parsed_resume or '(未解析到简历)')[:max_resume_chars]}",
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
    """评估 Agent 主入口:一次 LLM 调用后由服务端规范化和复算。"""
    user = build_user_prompt(
        job_title=job_title,
        dimensions=dimensions,
        parsed_resume=parsed_resume,
        messages=messages,
    )
    result = chat_json(SYSTEM_PROMPT, user, temperature=0.2)
    return _normalize_report(result, dimensions=dimensions, messages=messages)


def _normalize_report(
    result: dict[str, Any],
    *,
    dimensions: list[dict[str, Any]],
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """强制覆盖岗位维度、限制分数并删除无法在候选人原话中定位的证据。"""
    if not isinstance(result, dict) or not isinstance(result.get("dimensions"), list):
        raise ValueError("评估未产出有效维度打分")
    if not dimensions:
        raise ValueError("岗位没有可评估维度")

    raw_by_name = {
        str(item.get("name", "")).strip(): item
        for item in result["dimensions"]
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }
    candidate_corpus = "\n".join(
        str(message.get("text", ""))
        for message in messages
        if message.get("role") == "candidate"
    )
    normalized_dimensions: list[dict[str, Any]] = []
    validation_risks: list[str] = []
    weighted_score = 0.0
    weight_total = 0.0

    for expected in dimensions:
        name = str(expected.get("name", "")).strip()
        if not name:
            continue
        raw = raw_by_name.get(name)
        if raw is None:
            raw = {}
            validation_risks.append(f"维度「{name}」未产出有效评分,已按 0 分处理")
        try:
            score = float(raw.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
            validation_risks.append(f"维度「{name}」评分格式无效,已按 0 分处理")
        score = round(max(0.0, min(10.0, score)), 1)

        evidence = []
        raw_evidence = raw.get("evidence")
        if isinstance(raw_evidence, list):
            for item in raw_evidence:
                quote = _clean_evidence(item)
                if quote and quote in candidate_corpus and quote not in evidence:
                    evidence.append(quote)
        if raw_evidence and not evidence:
            validation_risks.append(f"维度「{name}」的证据无法在候选人原话中核验,已移除")

        normalized_dimensions.append(
            {"name": name, "score": score, "evidence": evidence}
        )
        try:
            weight = max(0.0, float(expected.get("weight", 0)))
        except (TypeError, ValueError):
            weight = 0.0
        weighted_score += score * weight
        weight_total += weight

    if not normalized_dimensions:
        raise ValueError("岗位没有命名有效的评估维度")
    if weight_total > 0:
        summary_score = round(weighted_score / weight_total * 10, 1)
    else:
        summary_score = round(
            sum(item["score"] for item in normalized_dimensions)
            / len(normalized_dimensions)
            * 10,
            1,
        )
    if float(summary_score).is_integer():
        summary_score = int(summary_score)

    risks = _string_list(result.get("risks"), limit=8)
    for risk in validation_risks:
        if risk not in risks:
            risks.append(risk)
    return {
        "summary_score": summary_score,
        "suggestion": str(result.get("suggestion") or "待评估")[:500],
        "dimensions": normalized_dimensions,
        "strengths": _string_list(result.get("strengths"), limit=6),
        "risks": risks[:10],
        "next_step_questions": _string_list(
            result.get("next_step_questions"), limit=6
        ),
    }


def _clean_evidence(value: Any) -> str:
    quote = str(value or "").strip()
    for prefix in ("候选人原话:", "候选人原话：", "应聘者原话:", "应聘者原话："):
        if quote.startswith(prefix):
            quote = quote[len(prefix) :].strip()
    return quote.strip(" \t\r\n\"'“”‘’「」")[:500]


def _string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:500] for item in value if str(item).strip()][:limit]
