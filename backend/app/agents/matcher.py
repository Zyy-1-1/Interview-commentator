"""简历 × 岗位匹配 Agent:输出各考察维度的匹配证据与分数,供「开始面试前」决策页展示。

注意:这是**面试前的预估**,与面试后的评估报告(agents/evaluator)相互独立、
互不影响 —— 答辩口径:同一套维度大纲,两个时点(简历证据 vs 回答证据)。
"""
from __future__ import annotations

import json
from typing import Any

from ..llm import chat_json

SYSTEM_PROMPT = """你是资深招聘专家。给定「岗位考察维度清单」与「候选人结构化简历」,逐维度判断简历与岗位的匹配度。
要求:
1. 只依据简历中真实存在的信息打分,禁止脑补;
2. 每个维度给出 resume_evidence(简历中的支撑原文要点,没有依据就写「简历未提及」);
3. score 为 0-10 整数:8-10 强匹配 / 5-7 部分匹配 / 1-4 弱 / 0 无证据;
4. overall 为 0-100 的整体匹配分,应与各维度分及权重趋势一致;
5. highlights 写 2-4 条最亮眼的匹配点,gaps 写 2-4 条最可能挂掉的短板;
6. 严格输出 JSON,不要任何多余文字。

输出 JSON 结构(严格遵循):
{
  "overall": 72,
  "summary": "两三句话的整体判断,直接给候选人看",
  "dimension_scores": [
    {"name": "维度名", "resume_evidence": "简历中的依据", "score": 8}
  ],
  "highlights": ["Python 项目经验扎实"],
  "gaps": ["无高并发实战"]
}"""


def _flatten_resume(parsed: dict[str, Any] | None, fallback_text: str | None) -> str:
    if parsed:
        data = {k: v for k, v in parsed.items() if not k.startswith("_")}
        return json.dumps(data, ensure_ascii=False)[:8000]
    return (fallback_text or "")[:8000]


def match_resume_to_job(
    *,
    parsed_resume: dict[str, Any] | None,
    resume_text: str | None,
    job_title: str,
    jd_text: str,
    dimensions: list[dict[str, Any]],
) -> dict[str, Any]:
    """简历 × JD → 匹配分析 JSON(供前端分析页渲染)。"""
    dim_lines = [
        f"- {d.get('name', '')}({'硬技能' if d.get('type') == 'hard' else '软素质'},权重 {d.get('weight', '')})"
        f" 要点:{'、'.join(d.get('keywords') or []) or '无'}"
        for d in dimensions or []
    ]
    result = chat_json(
        system=SYSTEM_PROMPT,
        user=(
            f"【岗位】{job_title}\n【JD】\n{(jd_text or '')[:3000]}\n\n"
            f"【考察维度清单】\n{chr(10).join(dim_lines) or '(无)'}\n\n"
            f"【候选人简历(结构化)】\n{_flatten_resume(parsed_resume, resume_text)}"
        ),
        temperature=0.2,
    )
    if not isinstance(result.get("dimension_scores"), list):
        raise ValueError("匹配分析缺少 dimension_scores")
    return _normalize_match(result, dimensions)


def _normalize_match(
    result: dict[str, Any], dimensions: list[dict[str, Any]]
) -> dict[str, Any]:
    """按岗位维度补齐结果、限制分数，并由服务端复算总分。"""
    if not dimensions:
        raise ValueError("岗位没有可匹配维度")
    raw_by_name = {
        str(item.get("name", "")).strip(): item
        for item in result["dimension_scores"]
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    }
    scores = []
    weighted = 0.0
    weight_total = 0.0
    for expected in dimensions:
        name = str(expected.get("name", "")).strip()
        if not name:
            continue
        raw = raw_by_name.get(name, {})
        try:
            score = max(0.0, min(10.0, float(raw.get("score", 0))))
        except (TypeError, ValueError):
            score = 0.0
        score = round(score, 1)
        evidence = str(raw.get("resume_evidence") or "简历未提及").strip()[:500]
        scores.append({"name": name, "resume_evidence": evidence, "score": score})
        try:
            weight = max(0.0, float(expected.get("weight", 0)))
        except (TypeError, ValueError):
            weight = 0.0
        weighted += score * weight
        weight_total += weight
    if not scores:
        raise ValueError("岗位没有命名有效的匹配维度")
    overall = (
        weighted / weight_total * 10
        if weight_total > 0
        else sum(item["score"] for item in scores) / len(scores) * 10
    )
    overall = round(overall, 1)
    if float(overall).is_integer():
        overall = int(overall)
    return {
        "overall": overall,
        "summary": str(result.get("summary") or "暂无整体分析")[:500],
        "dimension_scores": scores,
        "highlights": _string_list(result.get("highlights")),
        "gaps": _string_list(result.get("gaps")),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:500] for item in value if str(item).strip()][:6]
