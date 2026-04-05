"""Integration test for AI connectivity using project config.yaml."""

import os
from pathlib import Path

import anthropic
import pytest
from anthropic.types import TextBlock

from tg_tldr.config import load_config

RUN_CONNECTIVITY_TEST_ENV = "TG_TLDR_RUN_AI_CONNECTIVITY_TEST"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def test_ai_connectivity_from_config_yaml():
    if os.getenv(RUN_CONNECTIVITY_TEST_ENV) != "1":
        pytest.skip(f"未设置 {RUN_CONNECTIVITY_TEST_ENV}=1，跳过 AI 连通性集成测试")

    assert CONFIG_PATH.exists(), "缺少 config.yaml，无法执行 AI 连通性集成测试"
    config = load_config(str(CONFIG_PATH))
    assert config.anthropic_api_key, "ANTHROPIC_API_KEY 未配置，无法执行 AI 连通性集成测试"
    assert config.summary.model, "summary.model 未配置，无法执行 AI 连通性集成测试"

    client = anthropic.Anthropic(
        api_key=config.anthropic_api_key,
        base_url=config.anthropic_base_url,
    )
    response = client.messages.create(
        model=config.summary.model,
        max_tokens=32,
        messages=[{"role": "user", "content": "ping"}],
    )

    assert response.content, "AI 响应为空，连通性校验失败"
    text_blocks = [b for b in response.content if isinstance(b, TextBlock) and b.text.strip()]
    assert text_blocks, "AI 响应中未找到可用文本内容，连通性校验失败"
