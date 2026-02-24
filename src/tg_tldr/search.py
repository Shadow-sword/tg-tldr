"""搜索功能：分词和结果格式化。"""

import json

import jieba

from .db import Message


def tokenize(text: str) -> str:
    """对文本进行 jieba 分词，返回空格分隔的 token 字符串。"""
    if not text:
        return ""
    tokens = jieba.cut_for_search(text)
    return " ".join(t for t in tokens if t.strip())


def tokenize_query(query: str) -> str:
    """对搜索关键词进行分词，返回 FTS5 MATCH 查询字符串。"""
    if not query:
        return ""
    tokens = jieba.cut_for_search(query)
    return " ".join(t for t in tokens if t.strip())


def format_results(messages: list[Message], total: int) -> str:
    """格式化搜索结果为可读文本。"""
    if not messages:
        return "未找到匹配的消息。"
    lines = []
    for msg in messages:
        ts = msg.timestamp.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{ts}] {msg.group_name} | {msg.sender_name}: {msg.text}")
    lines.append(f"(共 {total} 条结果)")
    return "\n".join(lines)


def format_results_json(messages: list[Message]) -> str:
    """格式化搜索结果为 JSON。"""
    results = [
        {
            "id": msg.id,
            "group_id": msg.group_id,
            "group_name": msg.group_name,
            "sender_name": msg.sender_name,
            "text": msg.text,
            "timestamp": msg.timestamp.isoformat(),
        }
        for msg in messages
    ]
    return json.dumps(results, ensure_ascii=False, indent=2)
