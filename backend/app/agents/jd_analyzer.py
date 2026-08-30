"""模块② JD 分析 Agent。

输入:JD 文本;输出:能力维度清单(硬技能/软素质/行为要求),含权重与关键词。
同一岗位的考察大纲可缓存复用(标准化基础)。
"""
from typing import Any

from ..llm import chat_json

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
    # 兜底:确保 dimensions 存在
    if not isinstance(result.get("dimensions"), list) or not result["dimensions"]:
        raise ValueError("JD 分析未产出有效维度清单")
    return result
