"""模块② JD 分析 Agent。

输入:JD 文本;输出:能力维度清单(硬技能/软素质/行为要求),含权重与关键词。
同一岗位的考察大纲可缓存复用(标准化基础)。
"""
from typing import Any

from ..llm import chat_json
from .output_validation import finite_number, text_value

SYSTEM_PROMPT = """你是岗位需求分析师。把一份岗位 JD 拆解为可考察的能力维度清单。
要求:
1. 硬技能(技术栈/工具)与软素质(沟通/协作/抗压等)分开;
2. 每个维度给出 keywords(用于出题)和 weight(权重,全部维度权重之和≈1);
3. 软素质类维度 probe 填 "STAR";
4. junior_level 表示是否初级岗(初级岗可适当多考察软素质);
5. 严格输出 JSON,不要多余文字。

输出 JSON 结构(严格遵循):
{
  "dimensions": [
    {"name": "Python 编程", "type": "hard", "weight": 0.3,
     "keywords": ["Python", "Flask", "asyncio"], "probe": null},
    {"name": "沟通表达", "type": "soft", "weight": 0.15,
     "keywords": ["协作", "汇报"], "probe": "STAR"}
  ],
  "junior_level": true
}"""


def analyze_jd(jd_text: str, max_chars: int = 6000) -> dict[str, Any]:
    """JD → 能力维度清单(JSON)。"""
    result = chat_json(
        system=SYSTEM_PROMPT,
        user=f"以下是岗位 JD:\n\n{jd_text[:max_chars]}",
        temperature=0.2,
    )
    if not isinstance(result, dict):
        raise ValueError("JD 分析必须返回 JSON 对象")
    dimensions = _normalize_dimensions(result.get("dimensions"))
    return {
        "dimensions": dimensions,
        "junior_level": result.get("junior_level") is True,
    }


def _normalize_dimensions(value: Any) -> list[dict[str, Any]]:
    """清洗模型输出并保证硬技能在前、软素质在后、权重和为 1。"""
    if not isinstance(value, list) or not value:
        raise ValueError("JD 分析未产出有效维度清单")
    dimensions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value[:10]:
        if not isinstance(item, dict):
            continue
        name = text_value(item.get("name"), limit=100)
        if not name or name in seen:
            continue
        seen.add(name)
        dim_type = "soft" if item.get("type") == "soft" else "hard"
        weight = max(0.0, min(1_000_000.0, finite_number(item.get("weight"))))
        keywords = item.get("keywords")
        if not isinstance(keywords, list):
            keywords = []
        dimensions.append(
            {
                "name": name,
                "type": dim_type,
                "weight": weight,
                "keywords": [
                    text_value(keyword, limit=50)
                    for keyword in keywords[:10]
                    if text_value(keyword)
                ],
                "probe": "STAR" if dim_type == "soft" else None,
            }
        )
    if not dimensions:
        raise ValueError("JD 分析未产出有效维度清单")

    dimensions.sort(key=lambda item: item["type"] == "soft")
    total = sum(item["weight"] for item in dimensions)
    if total <= 0:
        normalized_weights = [1 / len(dimensions)] * len(dimensions)
    else:
        normalized_weights = [item["weight"] / total for item in dimensions]
    for item, weight in zip(dimensions, normalized_weights, strict=True):
        item["weight"] = round(weight, 4)
    # 抵消四舍五入误差，确保下游加权结果稳定。
    dimensions[-1]["weight"] = round(
        dimensions[-1]["weight"] + 1 - sum(item["weight"] for item in dimensions),
        4,
    )
    return dimensions
