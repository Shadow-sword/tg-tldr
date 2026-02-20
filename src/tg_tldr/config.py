"""Configuration management for tg-tldr."""

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class FilterConfig:
    """Message filtering rules."""

    ignore_users: list[int] = field(default_factory=list)
    only_users: list[int] = field(default_factory=list)
    ignore_keywords: list[str] = field(default_factory=list)
    only_keywords: list[str] = field(default_factory=list)

    def _match_keyword(self, text: str, pattern: str) -> bool:
        """Match text against a keyword pattern with * wildcard support."""
        if "*" in pattern:
            return fnmatch.fnmatch(text, pattern)
        return pattern in text

    def should_record(self, sender_id: int, text: str) -> bool:
        """Check if a message should be recorded based on filters."""
        if self.only_users and sender_id not in self.only_users:
            return False
        if self.ignore_users and sender_id in self.ignore_users:
            return False
        if self.only_keywords:
            if not any(self._match_keyword(text, kw) for kw in self.only_keywords):
                return False
        if self.ignore_keywords:
            if any(self._match_keyword(text, kw) for kw in self.ignore_keywords):
                return False
        return True


@dataclass
class GroupConfig:
    """Configuration for a monitored group."""

    name: str
    id: int
    summary_to: int | None = None
    filters: FilterConfig = field(default_factory=FilterConfig)
    prompt: str | None = None


@dataclass
class SummaryConfig:
    """Configuration for summary generation."""

    schedule: str = "09:00"
    timezone: str = "Asia/Shanghai"
    default_send_to: int | None = None
    model: str = "claude-sonnet-4-20250514"
    prompt: str | None = None


@dataclass
class TelegramConfig:
    """Telegram client configuration."""

    session_name: str = "tg-tldr"
    api_id: int = 0
    api_hash: str = ""


@dataclass
class Config:
    """Main application configuration."""

    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    groups: list[GroupConfig] = field(default_factory=list)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    anthropic_api_key: str = ""
    anthropic_base_url: str | None = None
    data_dir: Path = field(default_factory=lambda: Path("data"))

    def get_summary_target(self, group: GroupConfig) -> int | None:
        """Get the summary target for a group, falling back to default."""
        return group.summary_to or self.summary.default_send_to

    def get_group_ids(self) -> list[int]:
        """Get list of all monitored group IDs."""
        return [g.id for g in self.groups]

    def get_group_by_id(self, group_id: int) -> GroupConfig | None:
        """Find a group config by its ID."""
        for g in self.groups:
            if g.id == group_id:
                return g
        return None


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file and environment variables."""
    load_dotenv()

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Copy config.example.yaml to config.yaml and fill in your settings."
        )

    with open(config_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    telegram_data = data.get("telegram", {})
    telegram_config = TelegramConfig(
        session_name=telegram_data.get("session_name", "tg-tldr"),
        api_id=int(os.getenv("TELEGRAM_API_ID", 0)),
        api_hash=os.getenv("TELEGRAM_API_HASH", ""),
    )

    groups = []
    for g in data.get("groups", []):
        filters_data = g.get("filters", {})
        filters = FilterConfig(
            ignore_users=filters_data.get("ignore_users", []),
            only_users=filters_data.get("only_users", []),
            ignore_keywords=filters_data.get("ignore_keywords", []),
            only_keywords=filters_data.get("only_keywords", []),
        )
        groups.append(
            GroupConfig(
                name=g["name"],
                id=g["id"],
                summary_to=g.get("summary_to"),
                filters=filters,
                prompt=g.get("prompt"),
            )
        )

    summary_data = data.get("summary", {})
    summary_config = SummaryConfig(
        schedule=summary_data.get("schedule", "09:00"),
        timezone=summary_data.get("timezone", "Asia/Shanghai"),
        default_send_to=summary_data.get("default_send_to"),
        model=summary_data.get("model", "claude-sonnet-4-20250514"),
        prompt=summary_data.get("prompt"),
    )

    return Config(
        telegram=telegram_config,
        groups=groups,
        summary=summary_config,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
        data_dir=Path(data.get("data_dir", "data")),
    )
