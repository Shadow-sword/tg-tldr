"""LLM-powered summary generation using Claude."""

import logging
import string
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import anthropic
from anthropic.types import TextBlock

from .config import Config, GroupConfig
from .db import Database, Message

logger = logging.getLogger(__name__)


class SafeFormatter(string.Formatter):
    """A string formatter that preserves unknown placeholders as-is."""

    def get_value(
        self, key: int | str, args: tuple[object, ...], kwargs: dict[str, object]
    ) -> object:
        if isinstance(key, str):
            return kwargs.get(key, "{" + key + "}")
        return super().get_value(key, args, kwargs)


DEFAULT_PROMPT = """你是一个群聊总结助手。请根据以下群聊记录生成一份简洁的每日总结。

要求：
1. 按话题/讨论线程组织内容
2. 提取关键信息和结论
3. 保留重要的决定和待办事项
4. 使用中文输出
5. 总结要简洁明了，突出重点

群聊名称：{group_name}
日期：{date}

聊天记录：
{messages}

请生成总结："""


@dataclass
class Thread:
    """A conversation thread."""

    root: Message
    replies: list["Thread"]


class Summarizer:
    """Generates daily summaries using Claude."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.client = anthropic.Anthropic(
            api_key=config.anthropic_api_key,
            base_url=config.anthropic_base_url,
        )

    def _resolve_prompt(self, group: GroupConfig) -> str:
        """Resolve the prompt template for a group.

        Priority: group.prompt > config.summary.prompt > DEFAULT_PROMPT.
        Supports file: prefix for external prompt files (paths relative to CWD).
        """
        raw = group.prompt or self.config.summary.prompt or DEFAULT_PROMPT
        if raw.startswith("file:"):
            path = Path(raw[5:])
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError as e:
                logger.error(f"Failed to read prompt file '{path}' for group '{group.name}': {e}")
                raise
        return raw

    async def summarize_group(self, group: GroupConfig, target_date: date) -> str | None:
        """Generate a summary for a group on a specific date."""
        messages = await self.db.get_messages_by_date_and_group(group.id, target_date)

        if not messages:
            logger.info(f"No messages for {group.name} on {target_date}")
            return None

        formatted = self._format_messages_with_threads(messages)

        prompt_template = self._resolve_prompt(group)
        formatter = SafeFormatter()
        prompt = formatter.format(
            prompt_template,
            group_name=group.name,
            date=target_date.isoformat(),
            messages=formatted,
            message_count=str(len(messages)),
        )

        logger.info(f"Generating summary for {group.name} ({len(messages)} messages)")

        response = self.client.messages.create(
            model=self.config.summary.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        content_block = response.content[0]
        if not isinstance(content_block, TextBlock):
            logger.error(f"Unexpected content block type: {type(content_block)}")
            return None
        summary = content_block.text

        await self.db.insert_summary(group.id, group.name, target_date, summary)
        logger.info(f"Summary saved for {group.name} on {target_date}")

        return summary

    def _format_messages_with_threads(self, messages: list[Message]) -> str:
        """Format messages with thread structure for LLM context."""
        msg_map: dict[int, Message] = {m.id: m for m in messages}
        children: dict[int, list[Message]] = {}
        roots: list[Message] = []

        for msg in messages:
            if msg.reply_to_msg_id and msg.reply_to_msg_id in msg_map:
                parent_id = msg.reply_to_msg_id
                if parent_id not in children:
                    children[parent_id] = []
                children[parent_id].append(msg)
            else:
                roots.append(msg)

        def build_thread(msg: Message) -> Thread:
            replies = []
            if msg.id in children:
                for child in sorted(children[msg.id], key=lambda m: m.timestamp):
                    replies.append(build_thread(child))
            return Thread(root=msg, replies=replies)

        threads = [build_thread(r) for r in roots]

        lines: list[str] = []
        for thread in threads:
            self._format_thread(thread, lines, indent=0)
            lines.append("")

        return "\n".join(lines)

    def _format_thread(self, thread: Thread, lines: list[str], indent: int) -> None:
        """Recursively format a thread with indentation."""
        prefix = "  " * indent
        if indent > 0:
            prefix += "└ "

        msg = thread.root
        time_str = msg.timestamp.strftime("%H:%M")
        lines.append(f"{prefix}[{time_str}] {msg.sender_name}: {msg.text}")

        for reply in thread.replies:
            self._format_thread(reply, lines, indent + 1)

    async def summarize_all_groups(self, target_date: date) -> dict[int, str | None]:
        """Generate summaries for all configured groups."""
        results: dict[int, str | None] = {}
        for group in self.config.groups:
            results[group.id] = await self.summarize_group(group, target_date)
        return results
