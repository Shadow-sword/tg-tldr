"""Telegram message collector using Telethon."""

import datetime
import logging

from telethon import TelegramClient, events
from telethon.tl.types import User

from .config import Config
from .db import Database, Message

logger = logging.getLogger(__name__)


class MessageCollector:
    """Collects messages from monitored Telegram groups."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.client: TelegramClient | None = None
        self._group_names: dict[int, str] = {}

    async def start(self) -> TelegramClient:
        """Start the Telegram client and register message handler."""
        self.client = TelegramClient(
            self.config.telegram.session_name,
            self.config.telegram.api_id,
            self.config.telegram.api_hash,
        )

        await self.client.start()  # type: ignore[misc]
        logger.info("Telegram client started")

        for group in self.config.groups:
            self._group_names[group.id] = group.name

        group_ids = self.config.get_group_ids()
        if group_ids:
            self.client.add_event_handler(
                self._handle_message,
                events.NewMessage(chats=group_ids),
            )
            logger.info(f"Monitoring {len(group_ids)} groups: {list(self._group_names.values())}")

        return self.client

    async def stop(self) -> None:
        """Stop the Telegram client."""
        if self.client:
            await self.client.disconnect()  # type: ignore[misc]
            logger.info("Telegram client disconnected")

    async def _handle_message(self, event: events.NewMessage.Event) -> None:
        """Handle incoming messages from monitored groups."""
        msg = event.message

        if not msg.text:
            return

        chat_id = event.chat_id
        if chat_id is None:
            return
        group_config = self.config.get_group_by_id(chat_id)
        group_name = group_config.name if group_config else str(chat_id)

        sender = await event.get_sender()
        sender_id = sender.id if sender else 0
        sender_name = self._get_sender_name(sender)

        if group_config and not group_config.filters.should_record(sender_id, msg.text):
            logger.debug(f"Filtered message {msg.id} from {sender_name} in {group_name}")
            return

        reply_to_msg_id = None
        if msg.reply_to:
            reply_to_msg_id = msg.reply_to.reply_to_msg_id

        timestamp = msg.date
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=datetime.UTC)

        message = Message(
            id=msg.id,
            group_id=chat_id,
            group_name=group_name,
            sender_id=sender_id,
            sender_name=sender_name,
            text=msg.text,
            reply_to_msg_id=reply_to_msg_id,
            timestamp=timestamp,
        )

        await self.db.insert_message(message)
        logger.debug(f"Saved message {msg.id} from {sender_name} in {group_name}")

    def _get_sender_name(self, sender: User | None) -> str:
        """Extract display name from sender."""
        if not sender:
            return "Unknown"
        if sender.first_name:
            name = sender.first_name
            if sender.last_name:
                name += f" {sender.last_name}"
            return name
        if sender.username:
            return f"@{sender.username}"
        return str(sender.id)

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a message to a chat."""
        if not self.client:
            raise RuntimeError("Client not started")
        await self.client.send_message(chat_id, text)
        logger.info(f"Sent message to {chat_id}")
