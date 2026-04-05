"""Tests for Anthropic response content block parsing in summarizer."""

from anthropic.types import RedactedThinkingBlock, TextBlock, ThinkingBlock

from tg_tldr.summarizer import Summarizer


def test_extract_summary_text_skips_thinking_blocks():
    summarizer = Summarizer.__new__(Summarizer)

    content_blocks = [
        ThinkingBlock(type="thinking", thinking="analysis", signature="sig"),
        TextBlock(type="text", text="最终总结", citations=None),
    ]

    result = summarizer._extract_summary_text(content_blocks)

    assert result == "最终总结"


def test_extract_summary_text_returns_none_without_text_block():
    summarizer = Summarizer.__new__(Summarizer)

    content_blocks = [
        ThinkingBlock(type="thinking", thinking="analysis", signature="sig"),
        RedactedThinkingBlock(type="redacted_thinking", data="hidden"),
    ]

    result = summarizer._extract_summary_text(content_blocks)

    assert result is None
