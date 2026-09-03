"""JD 分析 Agent 测试(需真实 API Key,无 Key 跳过)。"""
import os
from pathlib import Path

import pytest

from app.agents import jd_analyzer
from app.agents.jd_analyzer import analyze_jd
from app.config import settings

FIXTURES = Path(__file__).parent / "fixtures"


def test_analyze_jd_normalizes_order_types_and_weights(monkeypatch):
    monkeypatch.setattr(
        jd_analyzer,
        "chat_json",
        lambda **kwargs: {
            "dimensions": [
                {"name": "沟通", "type": "soft", "weight": "2", "keywords": ["协作"]},
                {"name": "Python", "type": "unknown", "weight": 3, "keywords": "bad"},
                {"name": "Python", "type": "hard", "weight": 9, "keywords": []},
            ],
            "junior_level": 1,
        },
    )
    result = analyze_jd("一份足够长的岗位说明")
    assert [item["name"] for item in result["dimensions"]] == ["Python", "沟通"]
    assert [item["type"] for item in result["dimensions"]] == ["hard", "soft"]
    assert result["dimensions"][1]["probe"] == "STAR"
    assert sum(item["weight"] for item in result["dimensions"]) == pytest.approx(1)


@pytest.mark.llm_live
@pytest.mark.skipif(
    os.getenv("RUN_LLM_TESTS") != "1" or not settings.dashscope_api_key,
    reason="仅在 RUN_LLM_TESTS=1 且配置 Key 时运行真实 LLM 测试",
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
