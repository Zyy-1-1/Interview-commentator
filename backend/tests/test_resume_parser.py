"""简历解析 Agent 测试。

- 文件→文本(markitdown):离线可测,必测;
- LLM 结构化抽取:需要真实 API Key,无 Key 自动跳过。
"""
import os
from pathlib import Path

import pytest

from app.agents.resume_parser import file_to_text, parse_resume_text
from app.config import settings

FIXTURES = Path(__file__).parent / "fixtures"


def test_file_to_text_md():
    """markitdown 解析 markdown 简历 → 文本包含关键信息。"""
    text = file_to_text(FIXTURES / "sample_resume.md")
    assert "张三" in text
    assert "Python" in text
    assert "FastAPI" in text


@pytest.mark.llm_live
@pytest.mark.skipif(
    os.getenv("RUN_LLM_TESTS") != "1" or not settings.dashscope_api_key,
    reason="仅在 RUN_LLM_TESTS=1 且配置 Key 时运行真实 LLM 测试",
)
def test_parse_resume_text_llm():
    """真实 Key 下:LLM 抽取结构化 JSON 含 basic/projects。"""
    text = file_to_text(FIXTURES / "sample_resume.md")
    parsed = parse_resume_text(text)
    assert parsed["basic"]["name"]
    assert isinstance(parsed["projects"], list)
    assert parsed["skills"]["programming"]
