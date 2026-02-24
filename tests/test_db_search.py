"""Tests for database FTS5 search operations."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import pytest_asyncio

from tg_tldr.db import Database, Message


@pytest_asyncio.fixture
async def db():
    with TemporaryDirectory() as tmpdir:
        database = Database(Path(tmpdir) / "test.db")
        await database.connect()
        yield database
        await database.close()


@pytest.mark.asyncio
async def test_fts_table_created(db: Database):
    """FTS5 虚拟表应该在 connect 时创建。"""
    assert db._conn is not None
    cursor = await db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='messages_fts'"
    )
    row = await cursor.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_insert_message_creates_fts_index(db: Database):
    """插入消息时应同时建立 FTS 索引。"""
    msg = Message(
        id=1,
        group_id=-100,
        group_name="测试群",
        sender_id=123,
        sender_name="张三",
        text="今天讨论Python性能优化技巧",
        reply_to_msg_id=None,
        timestamp=datetime(2026, 1, 30, 14, 23),
    )
    await db.insert_message(msg)

    assert db._conn is not None
    cursor = await db._conn.execute("SELECT count(*) FROM messages_fts")
    row = await cursor.fetchone()
    assert row is not None and row[0] == 1


@pytest.mark.asyncio
async def test_search_messages_chinese(db: Database):
    """搜索中文关键词应返回匹配的消息。"""
    msg = Message(
        id=1,
        group_id=-100,
        group_name="测试群",
        sender_id=123,
        sender_name="张三",
        text="今天讨论Python性能优化技巧",
        reply_to_msg_id=None,
        timestamp=datetime(2026, 1, 30, 14, 23),
    )
    await db.insert_message(msg)

    results, total = await db.search_messages("性能优化")
    assert total >= 1
    assert any(r.id == 1 for r in results)


@pytest.mark.asyncio
async def test_search_messages_english(db: Database):
    """搜索英文关键词应返回匹配的消息。"""
    msg = Message(
        id=1,
        group_id=-100,
        group_name="测试群",
        sender_id=123,
        sender_name="张三",
        text="Let's discuss Python performance tips",
        reply_to_msg_id=None,
        timestamp=datetime(2026, 1, 30, 14, 23),
    )
    await db.insert_message(msg)

    results, total = await db.search_messages("Python")
    assert total >= 1
    assert any(r.id == 1 for r in results)


@pytest.mark.asyncio
async def test_search_messages_no_results(db: Database):
    """搜索不存在的关键词应返回空结果。"""
    msg = Message(
        id=1,
        group_id=-100,
        group_name="测试群",
        sender_id=123,
        sender_name="张三",
        text="今天天气不错",
        reply_to_msg_id=None,
        timestamp=datetime(2026, 1, 30, 14, 23),
    )
    await db.insert_message(msg)

    results, total = await db.search_messages("区块链")
    assert total == 0
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_messages_with_group_filter(db: Database):
    """按群组过滤搜索结果。"""
    msg1 = Message(
        id=1,
        group_id=-100,
        group_name="群A",
        sender_id=1,
        sender_name="A",
        text="Python优化",
        reply_to_msg_id=None,
        timestamp=datetime(2026, 1, 30, 14, 0),
    )
    msg2 = Message(
        id=2,
        group_id=-200,
        group_name="群B",
        sender_id=2,
        sender_name="B",
        text="Python教程",
        reply_to_msg_id=None,
        timestamp=datetime(2026, 1, 30, 15, 0),
    )
    await db.insert_message(msg1)
    await db.insert_message(msg2)

    results, total = await db.search_messages("Python", group_id=-100)
    assert total == 1
    assert results[0].group_id == -100


@pytest.mark.asyncio
async def test_search_messages_with_date_range(db: Database):
    """按日期范围过滤搜索结果。"""
    msg1 = Message(
        id=1,
        group_id=-100,
        group_name="群A",
        sender_id=1,
        sender_name="A",
        text="Python话题",
        reply_to_msg_id=None,
        timestamp=datetime(2026, 1, 15, 10, 0),
    )
    msg2 = Message(
        id=2,
        group_id=-100,
        group_name="群A",
        sender_id=2,
        sender_name="B",
        text="Python讨论",
        reply_to_msg_id=None,
        timestamp=datetime(2026, 1, 30, 15, 0),
    )
    await db.insert_message(msg1)
    await db.insert_message(msg2)

    results, total = await db.search_messages(
        "Python",
        date_from=datetime(2026, 1, 20),
        date_to=datetime(2026, 1, 31),
    )
    assert total == 1
    assert results[0].id == 2


@pytest.mark.asyncio
async def test_search_messages_limit(db: Database):
    """搜索结果应遵循 limit 限制。"""
    for i in range(10):
        msg = Message(
            id=i,
            group_id=-100,
            group_name="群A",
            sender_id=1,
            sender_name="A",
            text=f"Python话题{i}",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 1, 30, 10 + i, 0),
        )
        await db.insert_message(msg)

    results, total = await db.search_messages("Python", limit=3)
    assert len(results) == 3
    assert total == 10


@pytest.mark.asyncio
async def test_reindex_all(db: Database):
    """reindex_all 应重建完整 FTS 索引。"""
    for i in range(3):
        msg = Message(
            id=i,
            group_id=-100,
            group_name="群A",
            sender_id=1,
            sender_name="A",
            text=f"消息{i}",
            reply_to_msg_id=None,
            timestamp=datetime(2026, 1, 30, 10 + i, 0),
        )
        await db.insert_message(msg)

    count = await db.reindex_all()
    assert count == 3

    results, total = await db.search_messages("消息")
    assert total == 3
