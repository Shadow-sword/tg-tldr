"""Tests for per-group prompt resolution and placeholder substitution."""

from pathlib import Path

import yaml

from tg_tldr.config import load_config


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
