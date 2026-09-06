"""从简历原文定位有限的项目/经历片段，不把模型改写当作原始事实。"""
import json
from typing import Any

from ..output_validation import text_value

MAX_FACTS = 16
MAX_CONTEXT_CHARS = 3500


def build_resume_facts(parsed_resume: str | dict | None, resume_text: str | None) -> list[dict[str, Any]]:
    if not resume_text:
        return []
    try:
        parsed = json.loads(parsed_resume) if isinstance(parsed_resume, str) else parsed_resume
    except (ValueError, TypeError):
        return []
    if not isinstance(parsed, dict):
        return []
    facts = []
    chars = 0

    def add(value: Any, path: str, kind: str):
        nonlocal chars
        value = text_value(value, limit=1000)
        if not value or len(facts) >= MAX_FACTS:
            return
        start = resume_text.find(value)
        if start < 0:
            return  # 模型概括或编造的文本没有原文锚点，不注入出题上下文。
        quote = value[: min(400, MAX_CONTEXT_CHARS - chars)]
        if not quote:
            return
        facts.append({
            "id": f"R{len(facts) + 1}", "kind": kind, "path": path,
            "text": quote, "source_start": start, "source_end": start + len(quote),
        })
        chars += len(quote)

    # 不主动加入姓名、年龄、联系方式等基础身份字段。
    for section, fields in (("projects", ("name", "achievements")), ("experience", ("role", "summary"))):
        items = parsed.get(section)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items[:3]):
            if not isinstance(item, dict):
                continue
            for field in fields:
                add(item.get(field), f"{section}.{index}.{field}", section)
            if section == "projects" and isinstance(item.get("tech_stack"), list):
                for keyword in item["tech_stack"][:4]:
                    add(keyword, f"{section}.{index}.tech_stack", section)
    skills = parsed.get("skills")
    if isinstance(skills, dict):
        for category in ("programming", "tools", "soft"):
            values = skills.get(category)
            if isinstance(values, list):
                for value in values[:4]:
                    add(value, f"skills.{category}", "skills")
    return facts


def project_anchor(state: dict, dimension: dict | None = None) -> str:
    """按维度关键词选择有原文锚点的项目；无关联的硬技能不强行套用项目。"""
    facts = state.get("resume_facts") or []
    anchors = [f for f in facts if f.get("kind") == "projects" and str(f.get("path", "")).endswith(".name")]
    if not anchors:
        return ""
    dimension = dimension or {}
    terms = [text_value(term).lower() for term in (dimension.get("keywords") or [])]
    terms.append(text_value(dimension.get("name")).lower())
    def relevance(anchor):
        group = anchor["path"].rsplit(".", 1)[0] + "."
        corpus = " ".join(f.get("text", "") for f in facts if f.get("path", "").startswith(group)).lower()
        return sum(1 for term in terms if term and term in corpus)
    best = max(anchors, key=relevance)
    if dimension.get("type") == "hard" and not relevance(best):
        return ""
    return text_value(best["text"], limit=100)
