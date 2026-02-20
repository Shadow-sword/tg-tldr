"""Tests for per-group prompt resolution and placeholder substitution."""

from pathlib import Path

import yaml

from tg_tldr.config import Config, GroupConfig, SummaryConfig, load_config
from tg_tldr.summarizer import DEFAULT_PROMPT, SafeFormatter, Summarizer


def _write_config(tmp_path: Path, data: dict) -> str:
    """Write a config dict to a temp YAML file and return its path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(data, allow_unicode=True))
    env_file = tmp_path / ".env"
    env_file.write_text("TELEGRAM_API_ID=123\nTELEGRAM_API_HASH=abc\nANTHROPIC_API_KEY=sk-test\n")
    return str(config_file)


def test_group_prompt_parsed(tmp_path: Path):
    data = {
        "groups": [{"name": "test", "id": -100, "prompt": "custom {group_name}"}],
    }
    config = load_config(_write_config(tmp_path, data))
    assert config.groups[0].prompt == "custom {group_name}"


def test_group_prompt_defaults_to_none(tmp_path: Path):
    data = {
        "groups": [{"name": "test", "id": -100}],
    }
    config = load_config(_write_config(tmp_path, data))
    assert config.groups[0].prompt is None


def test_summary_prompt_parsed(tmp_path: Path):
    data = {
        "groups": [],
        "summary": {"prompt": "global prompt {date}"},
    }
    config = load_config(_write_config(tmp_path, data))
    assert config.summary.prompt == "global prompt {date}"


def test_summary_prompt_defaults_to_none(tmp_path: Path):
    data = {"groups": []}
    config = load_config(_write_config(tmp_path, data))
    assert config.summary.prompt is None


def test_safe_formatter_known_keys():
    fmt = SafeFormatter()
    result = fmt.format("{group_name} on {date}", group_name="Test", date="2026-01-01")
    assert result == "Test on 2026-01-01"


def test_safe_formatter_unknown_keys_preserved():
    fmt = SafeFormatter()
    result = fmt.format("{group_name} has {unknown}", group_name="Test")
    assert result == "Test has {unknown}"


def test_safe_formatter_literal_braces():
    fmt = SafeFormatter()
    result = fmt.format("{{literal}} and {group_name}", group_name="Test")
    assert result == "{literal} and Test"


def test_resolve_prompt_uses_default():
    """No prompt configured anywhere -> use DEFAULT_PROMPT."""
    config = Config()
    group = GroupConfig(name="test", id=-100)
    summarizer = Summarizer.__new__(Summarizer)
    summarizer.config = config
    result = summarizer._resolve_prompt(group)
    assert result == DEFAULT_PROMPT


def test_resolve_prompt_global_overrides_default():
    """summary.prompt configured -> use it instead of default."""
    config = Config(summary=SummaryConfig(prompt="global {group_name}"))
    group = GroupConfig(name="test", id=-100)
    summarizer = Summarizer.__new__(Summarizer)
    summarizer.config = config
    result = summarizer._resolve_prompt(group)
    assert result == "global {group_name}"


def test_resolve_prompt_group_overrides_global():
    """group.prompt configured -> use it, ignore global."""
    config = Config(summary=SummaryConfig(prompt="global"))
    group = GroupConfig(name="test", id=-100, prompt="per-group {date}")
    summarizer = Summarizer.__new__(Summarizer)
    summarizer.config = config
    result = summarizer._resolve_prompt(group)
    assert result == "per-group {date}"


def test_resolve_prompt_file_reference(tmp_path: Path):
    """file: prefix -> read prompt from file."""
    prompt_file = tmp_path / "custom.txt"
    prompt_file.write_text("from file {group_name}")
    group = GroupConfig(name="test", id=-100, prompt=f"file:{prompt_file}")
    config = Config()
    summarizer = Summarizer.__new__(Summarizer)
    summarizer.config = config
    result = summarizer._resolve_prompt(group)
    assert result == "from file {group_name}"
