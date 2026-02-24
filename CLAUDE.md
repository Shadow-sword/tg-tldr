# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

tg-tldr 是一个 Telegram 群聊记录器，使用 Telethon 以用户身份监听群聊消息，存储到 SQLite，每日定时调用 Claude API 生成群聊摘要。

## 常用命令

```bash
# 安装依赖
make install        # 或 uv sync

# 运行
make run            # 启动守护进程（监听消息 + 定时总结）
make summary        # 生成昨日总结
make summary-date DATE=2026-01-30  # 生成指定日期总结

# 代码检查
make lint           # ruff check
make format         # ruff format + fix
make typecheck      # pyright
make ci             # 完整 CI 检查（lint + format check + typecheck）

# 数据库
make db-shell       # 打开 SQLite (data/messages.db)
make purge BEFORE=2026-01-01  # 清理旧消息

# 搜索
make search KEYWORD="Python"          # 搜索关键词
make search KEYWORD="优化" GROUP="技术群"  # 按群组搜索
make reindex                          # 重建 FTS 全文搜索索引

# 测试
make test           # 运行测试

# Docker
make docker-build   # 构建镜像
make docker-run     # 首次交互式运行（登录 Telegram）
make docker-up      # 后台启动
make docker-restart # 重启容器
```

## 代码架构

```
src/tg_tldr/
├── __main__.py   # CLI 入口，处理 run/summary/search/reindex/purge 命令
├── config.py     # 配置加载，合并 config.yaml + .env
├── collector.py  # Telethon 消息监听，应用过滤规则
├── db.py         # SQLite 异步操作（messages/summaries/FTS5 表）
├── search.py     # jieba 分词、搜索结果格式化
├── summarizer.py # Claude API 调用，构建回复线程结构
└── scheduler.py  # APScheduler 定时任务
```

**数据流**: Telegram → collector (过滤) → db (存储) → summarizer (生成摘要) → scheduler (发送)

## 配置

- `.env` - API 凭证 (TELEGRAM_API_ID, TELEGRAM_API_HASH, ANTHROPIC_API_KEY)
- `config.yaml` - 群聊配置、过滤规则、定时任务设置
- 数据存储在 `data/` 目录 (messages.db, session 文件)

## 开发规范

- 使用 ruff 进行代码检查和格式化，pyright 进行类型检查
- 代码行宽 100 字符
- Python 3.11+，使用现代类型注解语法（如 `list[int]` 而非 `List[int]`）
