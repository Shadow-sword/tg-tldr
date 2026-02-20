# Per-Group Prompt Design

## Overview

Support different summary prompts per group, with a three-layer priority system and placeholder variable substitution.

## Configuration

### Priority Layers

1. **Built-in default** — hardcoded in code as `DEFAULT_PROMPT`
2. **Global override** — `summary.prompt` in config.yaml
3. **Group override** — `groups[].prompt` in config.yaml

Higher layer completely replaces lower layers (no merging/appending).

### Prompt Sources

The `prompt` field supports two formats:

- **Inline string**: directly written in YAML
- **File reference**: prefixed with `file:`, path relative to config.yaml directory

```yaml
summary:
  prompt: |
    Custom global prompt with {group_name}...
    {messages}

groups:
  - name: "Tech Group"
    id: -1001234567890
    prompt: |
      Inline per-group prompt...
      {messages}
  - name: "Casual Group"
    id: -1009876543210
    prompt: "file:prompts/casual.txt"
```

### Placeholders

Simple `str.format_map()` variable substitution:

| Placeholder | Description |
|---|---|
| `{group_name}` | Group name from config |
| `{date}` | Target date (YYYY-MM-DD) |
| `{messages}` | Formatted chat messages with thread structure |
| `{message_count}` | Number of messages |

Unknown placeholders are preserved as-is (not an error) via a safe formatter.

## Code Changes

### config.py

- `SummaryConfig`: add `prompt: str | None = None`
- `GroupConfig`: add `prompt: str | None = None`
- `load_config()`: parse prompt fields from YAML

### summarizer.py

- Rename `SUMMARY_PROMPT` to `DEFAULT_PROMPT`
- Add `_resolve_prompt(group)` method:
  1. Select prompt: group.prompt > config.summary.prompt > DEFAULT_PROMPT
  2. If starts with `file:`, read file content
  3. Apply placeholder substitution with SafeFormatter
- Update `summarize_group()` to use `_resolve_prompt()`

### config.example.yaml

- Add commented prompt examples in both `summary` and `groups` sections
