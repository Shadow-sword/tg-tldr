"""Tests for search module."""

from tg_tldr.search import tokenize, tokenize_query


class TestTokenize:
    def test_chinese_text(self):
        result = tokenize("今天发现了一个Python性能优化技巧")
        tokens = result.split()
        assert "性能" in tokens
        assert "优化" in tokens

    def test_english_text(self):
        result = tokenize("hello world python performance")
        tokens = result.split()
        assert "hello" in tokens
        assert "world" in tokens

    def test_mixed_text(self):
        result = tokenize("使用Python进行数据分析")
        tokens = result.split()
        assert "数据" in tokens
        assert "分析" in tokens

    def test_empty_text(self):
        result = tokenize("")
        assert result == ""


class TestTokenizeQuery:
    def test_chinese_query(self):
        result = tokenize_query("性能优化")
        assert len(result) > 0

    def test_english_query(self):
        result = tokenize_query("Python")
        assert "Python" in result

    def test_empty_query(self):
        result = tokenize_query("")
        assert result == ""
