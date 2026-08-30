"""JD 分析 Agent 测试(需真实 API Key,无 Key 跳过)。"""
from pathlib import Path

import pytest

from app.agents.jd_analyzer import analyze_jd
from app.config import settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.skipif(
    not settings.deepseek_api_key,
    reason="未配置 DEEPSEEK_API_KEY,跳过 LLM 相关测试",
)
def test_analyze_jd_dimensions():
    jd = (FIXTURES / "sample_jd.md").read_text(encoding="utf-8")
    result = analyze_jd(jd)
    dims = result["dimensions"]
    assert len(dims) >= 3
    # 至少含一个硬技能
    assert any(d["type"] == "hard" for d in dims)
    # 权重和 ≈ 1
    total = sum(d.get("weight", 0) for d in dims)
    assert 0.9 <= total <= 1.1
