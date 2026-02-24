"""Database layer for storing messages and summaries."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import aiosqlite


@dataclass
class Message:
    """A chat message."""

    id: int
    group_id: int
    group_name: str
    sender_id: int
    sender_name: str
    text: str
    reply_to_msg_id: int | None
    timestamp: datetime


@dataclass
class Summary:
    """A daily summary."""

    id: int
    group_id: int
    group_name: str
    date: date
    summary: str
    created_at: datetime


class Database:
    """Async SQLite database for messages and summaries."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize database connection and create tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        await self._create_tables()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        assert self._conn is not None
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                sender_id INTEGER NOT NULL,
                sender_name TEXT NOT NULL,
                text TEXT NOT NULL,
                reply_to_msg_id INTEGER,
                timestamp DATETIME NOT NULL,
                PRIMARY KEY (id, group_id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_group_date
                ON messages(group_id, timestamp);

            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                date DATE NOT NULL,
                summary TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                UNIQUE(group_id, date)
            );

            CREATE INDEX IF NOT EXISTS idx_summaries_group_date
                ON summaries(group_id, date);

            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                msg_id UNINDEXED,
                group_id UNINDEXED,
                text,
                tokenize='unicode61'
            );
            """
        )
        await self._conn.commit()

    async def _index_message(self, msg_id: int, group_id: int, text: str) -> None:
        """为消息建立 FTS 索引。"""
        from .search import tokenize

        assert self._conn is not None
        tokenized = tokenize(text)
        if not tokenized:
            return
        # 先删除旧条目，避免 INSERT OR REPLACE 导致重复
        await self._conn.execute(
            "DELETE FROM messages_fts WHERE msg_id = ? AND group_id = ?",
            (msg_id, group_id),
        )
        await self._conn.execute(
            "INSERT INTO messages_fts(msg_id, group_id, text) VALUES (?, ?, ?)",
            (msg_id, group_id, tokenized),
        )

    async def insert_message(self, msg: Message) -> None:
        """Insert a message into the database."""
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, group_id, group_name, sender_id, sender_name, text, reply_to_msg_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.id,
                msg.group_id,
                msg.group_name,
                msg.sender_id,
                msg.sender_name,
                msg.text,
                msg.reply_to_msg_id,
                msg.timestamp.isoformat(),
            ),
        )
        await self._index_message(msg.id, msg.group_id, msg.text)
        await self._conn.commit()

    async def get_messages_by_date_and_group(
        self, group_id: int, target_date: date
    ) -> list[Message]:
        """Get all messages for a group on a specific date."""
        assert self._conn is not None
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())

        cursor = await self._conn.execute(
            """
            SELECT id, group_id, group_name, sender_id, sender_name,
                   text, reply_to_msg_id, timestamp
            FROM messages
            WHERE group_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
            """,
            (group_id, start.isoformat(), end.isoformat()),
        )
        rows = await cursor.fetchall()
        return [
            Message(
                id=row[0],
                group_id=row[1],
                group_name=row[2],
                sender_id=row[3],
                sender_name=row[4],
                text=row[5],
                reply_to_msg_id=row[6],
                timestamp=datetime.fromisoformat(row[7]),
            )
            for row in rows
        ]

    async def get_message_by_id(self, group_id: int, msg_id: int) -> Message | None:
        """Get a specific message by ID."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            SELECT id, group_id, group_name, sender_id, sender_name,
                   text, reply_to_msg_id, timestamp
            FROM messages
            WHERE group_id = ? AND id = ?
            """,
            (group_id, msg_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return Message(
            id=row[0],
            group_id=row[1],
            group_name=row[2],
            sender_id=row[3],
            sender_name=row[4],
            text=row[5],
            reply_to_msg_id=row[6],
            timestamp=datetime.fromisoformat(row[7]),
        )

    async def insert_summary(
        self, group_id: int, group_name: str, target_date: date, summary_text: str
    ) -> None:
        """Insert a daily summary."""
        assert self._conn is not None
        await self._conn.execute(
            """
            INSERT OR REPLACE INTO summaries
            (group_id, group_name, date, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                group_id,
                group_name,
                target_date.isoformat(),
                summary_text,
                datetime.now().isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_summary(self, group_id: int, target_date: date) -> Summary | None:
        """Get a summary for a group on a specific date."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            SELECT id, group_id, group_name, date, summary, created_at
            FROM summaries
            WHERE group_id = ? AND date = ?
            """,
            (group_id, target_date.isoformat()),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return Summary(
            id=row[0],
            group_id=row[1],
            group_name=row[2],
            date=date.fromisoformat(row[3]),
            summary=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )

    async def purge_messages_before(self, before_date: date) -> int:
        """Delete messages older than the given date. Returns deleted count."""
        assert self._conn is not None
        cutoff = datetime.combine(before_date, datetime.min.time()).isoformat()
        # 先清理 FTS 索引中的对应条目
        await self._conn.execute(
            """DELETE FROM messages_fts WHERE (msg_id, group_id) IN (
                SELECT id, group_id FROM messages WHERE timestamp < ?
            )""",
            (cutoff,),
        )
        cursor = await self._conn.execute(
            "DELETE FROM messages WHERE timestamp < ?",
            (cutoff,),
        )
        await self._conn.commit()
        return cursor.rowcount

    async def search_messages(
        self,
        query: str,
        *,
        group_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
    ) -> tuple[list[Message], int]:
        """搜索消息，返回 (匹配消息列表, 总数)。"""
        from .search import tokenize_query

        assert self._conn is not None
        tokenized_query = tokenize_query(query)
        if not tokenized_query:
            return [], 0

        conditions = ["f.text MATCH ?"]
        params: list[str | int] = [tokenized_query]

        if group_id is not None:
            conditions.append("m.group_id = ?")
            params.append(group_id)
        if date_from is not None:
            conditions.append("m.timestamp >= ?")
            params.append(date_from.isoformat())
        if date_to is not None:
            conditions.append("m.timestamp <= ?")
            params.append(date_to.isoformat())

        where = " AND ".join(conditions)

        count_sql = f"""
            SELECT count(*)
            FROM messages_fts f
            JOIN messages m ON m.id = f.msg_id AND m.group_id = f.group_id
            WHERE {where}
        """
        cursor = await self._conn.execute(count_sql, params)
        row = await cursor.fetchone()
        total = row[0] if row else 0

        search_sql = f"""
            SELECT m.id, m.group_id, m.group_name, m.sender_id, m.sender_name,
                   m.text, m.reply_to_msg_id, m.timestamp
            FROM messages_fts f
            JOIN messages m ON m.id = f.msg_id AND m.group_id = f.group_id
            WHERE {where}
            ORDER BY m.timestamp DESC
            LIMIT ?
        """
        cursor = await self._conn.execute(search_sql, [*params, limit])
        rows = await cursor.fetchall()

        messages = [
            Message(
                id=r[0],
                group_id=r[1],
                group_name=r[2],
                sender_id=r[3],
                sender_name=r[4],
                text=r[5],
                reply_to_msg_id=r[6],
                timestamp=datetime.fromisoformat(r[7]),
            )
            for r in rows
        ]
        return messages, total

    async def reindex_all(self) -> int:
        """重建所有消息的 FTS 索引，返回索引数量。"""
        from .search import tokenize

        assert self._conn is not None
        await self._conn.execute("DELETE FROM messages_fts")

        cursor = await self._conn.execute("SELECT id, group_id, text FROM messages")
        rows = await cursor.fetchall()

        count = 0
        for row in rows:
            msg_id, group_id, text = row[0], row[1], row[2]
            tokenized = tokenize(text)
            if tokenized:
                await self._conn.execute(
                    "INSERT INTO messages_fts(msg_id, group_id, text) VALUES (?, ?, ?)",
                    (msg_id, group_id, tokenized),
                )
                count += 1
        await self._conn.commit()
        return count
