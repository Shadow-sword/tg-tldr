# Per-Group Prompt Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow each Telegram group to use a different summary prompt, with fallback from group-level to global to built-in default, supporting `{placeholder}` variable substitution and `file:` references.

**Architecture:** Three-layer prompt resolution (built-in default → `summary.prompt` → `groups[].prompt`). A `SafeFormatter` handles placeholder substitution, preserving unknown `{keys}` as-is. Prompts can be inline strings or `file:path` references to external files.

**Tech Stack:** Python dataclasses, `string.Formatter`, `pathlib.Path`

---

### Task 1: Set up test infrastructure

**Files:**
- Modify: `pyproject.toml:16-20` (add pytest to dev deps)
- Create: `tests/__init__.py`
- Create: `tests/test_prompt.py`

**Step 1: Add pytest dependency**

In `pyproject.toml`, add pytest to the dev dependency group:

```toml
[project.optional-dependencies]
dev = [
    "ruff>=0.8.0",
    "pyright>=1.1.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]
```

And in:

```toml
[dependency-groups]
dev = [
    "pyright>=1.1.408",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]
```

**Step 2: Install dependencies**

Run: `uv sync`
Expected: Dependencies installed successfully including pytest

**Step 3: Create empty test files**

Create `tests/__init__.py` (empty) and `tests/test_prompt.py` with:

```python
"""Tests for per-group prompt resolution and placeholder substitution."""
```

**Step 4: Run pytest to verify setup**

Run: `uv run pytest tests/ -v`
Expected: "no tests ran" or similar (0 collected, no errors)

**Step 5: Commit**

```bash
git add pyproject.toml tests/
git commit -m "chore: add pytest infrastructure for prompt tests"
```

---

### Task 2: Add prompt field to config dataclasses

**Files:**
- Modify: `src/tg_tldr/config.py:43-49` (GroupConfig)
- Modify: `src/tg_tldr/config.py:52-59` (SummaryConfig)
- Modify: `src/tg_tldr/config.py:119-135` (load_config groups parsing)
- Modify: `src/tg_tldr/config.py:137-143` (load_config summary parsing)
- Test: `tests/test_prompt.py`

**Step 1: Write failing tests for config parsing**

In `tests/test_prompt.py`:

```python
"""Tests for per-group prompt resolution and placeholder substitution."""

import tempfile
from pathlib import Path

import yaml

from tg_tldr.config import load_config


def _write_config(tmp_path: Path, data: dict) -> str:
    """Write a config dict to a temp YAML file and return its path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(data, allow_unicode=True))
    # load_config needs env vars; set minimal ones
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_prompt.py -v`
Expected: FAIL — `GroupConfig` and `SummaryConfig` don't have `prompt` field yet

**Step 3: Add prompt field to dataclasses**

In `src/tg_tldr/config.py`, modify `GroupConfig` (line 43-49):

```python
@dataclass
class GroupConfig:
    """Configuration for a monitored group."""

    name: str
    id: int
    summary_to: int | None = None
    filters: FilterConfig = field(default_factory=FilterConfig)
    prompt: str | None = None
```

Modify `SummaryConfig` (line 52-59):

```python
@dataclass
class SummaryConfig:
    """Configuration for summary generation."""

    schedule: str = "09:00"
    timezone: str = "Asia/Shanghai"
    default_send_to: int | None = None
    model: str = "claude-sonnet-4-20250514"
    prompt: str | None = None
```

**Step 4: Update load_config to parse prompt fields**

In `load_config()`, update the group parsing (around line 128-134) to include prompt:

```python
        groups.append(
            GroupConfig(
                name=g["name"],
                id=g["id"],
                summary_to=g.get("summary_to"),
                filters=filters,
                prompt=g.get("prompt"),
            )
        )
```

Update summary parsing (around line 138-143) to include prompt:

```python
    summary_config = SummaryConfig(
        schedule=summary_data.get("schedule", "09:00"),
        timezone=summary_data.get("timezone", "Asia/Shanghai"),
        default_send_to=summary_data.get("default_send_to"),
        model=summary_data.get("model", "claude-sonnet-4-20250514"),
        prompt=summary_data.get("prompt"),
    )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_prompt.py -v`
Expected: All 4 tests PASS

**Step 6: Run type checker**

Run: `uv run pyright src/tg_tldr/config.py`
Expected: No errors

**Step 7: Commit**

```bash
git add src/tg_tldr/config.py tests/test_prompt.py
git commit -m "feat: add prompt field to GroupConfig and SummaryConfig"
```

---

### Task 3: Implement SafeFormatter and prompt resolution

**Files:**
- Modify: `src/tg_tldr/summarizer.py:1-30` (imports, rename constant, add SafeFormatter)
- Modify: `src/tg_tldr/summarizer.py:41-85` (Summarizer class — add _resolve_prompt, update summarize_group)
- Test: `tests/test_prompt.py`

**Step 1: Write failing tests for SafeFormatter**

Append to `tests/test_prompt.py`:

```python
from tg_tldr.summarizer import SafeFormatter


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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_prompt.py::test_safe_formatter_known_keys -v`
Expected: FAIL — `SafeFormatter` doesn't exist yet

**Step 3: Implement SafeFormatter**

In `src/tg_tldr/summarizer.py`, add after the imports (before `DEFAULT_PROMPT`):

```python
import string


class SafeFormatter(string.Formatter):
    """A string formatter that preserves unknown placeholders as-is."""

    def get_value(
        self, key: int | str, args: tuple[object, ...], kwargs: dict[str, object]
    ) -> object:
        if isinstance(key, str):
            return kwargs.get(key, "{" + key + "}")
        return super().get_value(key, args, kwargs)
```

Also rename `SUMMARY_PROMPT` to `DEFAULT_PROMPT` (same content).

**Step 4: Run SafeFormatter tests**

Run: `uv run pytest tests/test_prompt.py -k "safe_formatter" -v`
Expected: All 3 tests PASS

**Step 5: Write failing tests for prompt resolution**

Append to `tests/test_prompt.py`:

```python
from tg_tldr.summarizer import DEFAULT_PROMPT, Summarizer
from tg_tldr.config import Config, GroupConfig, SummaryConfig


def test_resolve_prompt_uses_default():
    """No prompt configured anywhere → use DEFAULT_PROMPT."""
    config = Config()
    group = GroupConfig(name="test", id=-100)
    summarizer = Summarizer.__new__(Summarizer)
    summarizer.config = config
    result = summarizer._resolve_prompt(group)
    assert result == DEFAULT_PROMPT


def test_resolve_prompt_global_overrides_default():
    """summary.prompt configured → use it instead of default."""
    config = Config(summary=SummaryConfig(prompt="global {group_name}"))
    group = GroupConfig(name="test", id=-100)
    summarizer = Summarizer.__new__(Summarizer)
    summarizer.config = config
    result = summarizer._resolve_prompt(group)
    assert result == "global {group_name}"


def test_resolve_prompt_group_overrides_global():
    """group.prompt configured → use it, ignore global."""
    config = Config(summary=SummaryConfig(prompt="global"))
    group = GroupConfig(name="test", id=-100, prompt="per-group {date}")
    summarizer = Summarizer.__new__(Summarizer)
    summarizer.config = config
    result = summarizer._resolve_prompt(group)
    assert result == "per-group {date}"


def test_resolve_prompt_file_reference(tmp_path: Path):
    """file: prefix → read prompt from file."""
    prompt_file = tmp_path / "custom.txt"
    prompt_file.write_text("from file {group_name}")
    group = GroupConfig(name="test", id=-100, prompt=f"file:{prompt_file}")
    config = Config()
    summarizer = Summarizer.__new__(Summarizer)
    summarizer.config = config
    result = summarizer._resolve_prompt(group)
    assert result == "from file {group_name}"
```

**Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_prompt.py -k "resolve_prompt" -v`
Expected: FAIL — `_resolve_prompt` doesn't exist yet

**Step 7: Implement _resolve_prompt and update summarize_group**

In `src/tg_tldr/summarizer.py`, add the `_resolve_prompt` method to `Summarizer` class and update `summarize_group`:

```python
    def _resolve_prompt(self, group: GroupConfig) -> str:
        """Resolve the prompt template for a group.

        Priority: group.prompt > config.summary.prompt > DEFAULT_PROMPT.
        Supports file: prefix for external prompt files.
        """
        raw = group.prompt or self.config.summary.prompt or DEFAULT_PROMPT
        if raw.startswith("file:"):
            path = Path(raw[5:])
            raw = path.read_text(encoding="utf-8")
        return raw
```

Update `summarize_group` (around lines 60-66) to replace the old `.format()` call:

```python
        prompt_template = self._resolve_prompt(group)
        formatter = SafeFormatter()
        prompt = formatter.format(
            prompt_template,
            group_name=group.name,
            date=target_date.isoformat(),
            messages=formatted,
            message_count=str(len(messages)),
        )
```

Remove the old lines:
```python
        prompt = SUMMARY_PROMPT.format(
            group_name=group.name,
            date=target_date.isoformat(),
            messages=formatted,
        )
```

**Step 8: Run all tests**

Run: `uv run pytest tests/test_prompt.py -v`
Expected: All tests PASS

**Step 9: Run type checker and linter**

Run: `uv run pyright src/tg_tldr/summarizer.py && uv run ruff check src/tg_tldr/summarizer.py`
Expected: No errors

**Step 10: Commit**

```bash
git add src/tg_tldr/summarizer.py tests/test_prompt.py
git commit -m "feat: implement per-group prompt resolution with SafeFormatter"
```

---

### Task 4: Update config.example.yaml with prompt examples

**Files:**
- Modify: `config.example.yaml`

**Step 1: Add prompt examples to config.example.yaml**

Add a `prompt` field (commented out) under `summary` and under the first group entry:

```yaml
telegram:
  session_name: tg-tldr

groups:
  - name: "技术群"
    id: -1001234567890
    summary_to: -1009999999999
    # 自定义总结提示词（覆盖全局提示词，可选）
    # 支持占位符：{group_name} {date} {messages} {message_count}
    # prompt: |
    #   请以技术视角总结 {group_name} 在 {date} 的讨论。
    #   共 {message_count} 条消息。
    #   {messages}
    # 也可以引用外部文件：
    # prompt: "file:prompts/tech.txt"
    filters:
      ignore_users: [123456789, 987654321]
      ignore_keywords: ["*广告*", "*推广*", "免费领取*"]
  - name: "闲聊群"
    id: -1009876543210
    summary_to: -1009876543210

summary:
  schedule: "09:00"
  timezone: "Asia/Shanghai"
  default_send_to: -1009999999999
  model: "claude-sonnet-4-20250514"
  # 全局总结提示词（覆盖内置默认提示词，可选）
  # 支持占位符：{group_name} {date} {messages} {message_count}
  # prompt: |
  #   你是一个群聊总结助手。请根据以下群聊记录生成总结。
  #   群聊名称：{group_name}
  #   日期：{date}
  #   消息数量：{message_count}
  #   聊天记录：
  #   {messages}
```

**Step 2: Run full CI checks**

Run: `uv run ruff check src/ && uv run ruff format --check src/ && uv run pyright src/ && uv run pytest tests/ -v`
Expected: All pass

**Step 3: Commit**

```bash
git add config.example.yaml
git commit -m "docs: add prompt configuration examples to config.example.yaml"
```
