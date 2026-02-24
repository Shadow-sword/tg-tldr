"""Entry point for tg-tldr."""

import argparse
import asyncio
import logging
import signal
import sys
from datetime import date, datetime

from .collector import MessageCollector
from .config import load_config
from .db import Database
from .scheduler import SummaryScheduler
from .summarizer import Summarizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_daemon(config_path: str) -> None:
    """Run the daemon: collect messages and schedule summaries."""
    config = load_config(config_path)

    if not config.telegram.api_id or not config.telegram.api_hash:
        logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        sys.exit(1)

    if not config.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY must be set in .env")
        sys.exit(1)

    db = Database(config.data_dir / "messages.db")
    await db.connect()

    collector = MessageCollector(config, db)
    await collector.start()

    summarizer = Summarizer(config, db)
    scheduler = SummaryScheduler(config, summarizer, collector)
    scheduler.start()

    stop_event = asyncio.Event()

    def handle_signal() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    logger.info("tg-tldr is running. Press Ctrl+C to stop.")

    try:
        await stop_event.wait()
    finally:
        scheduler.stop()
        await collector.stop()
        await db.close()
        logger.info("Shutdown complete")


async def run_summary(config_path: str, target_date: date) -> None:
    """Run a one-off summary for a specific date."""
    config = load_config(config_path)

    if not config.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY must be set in .env")
        sys.exit(1)

    db = Database(config.data_dir / "messages.db")
    await db.connect()

    collector = MessageCollector(config, db)
    await collector.start()

    summarizer = Summarizer(config, db)
    scheduler = SummaryScheduler(config, summarizer, collector)

    try:
        await scheduler.run_manual_summary(target_date)
    finally:
        await collector.stop()
        await db.close()


async def run_purge(config_path: str, before_date: date) -> None:
    """Purge messages older than the given date."""
    config = load_config(config_path)

    db = Database(config.data_dir / "messages.db")
    await db.connect()

    try:
        deleted = await db.purge_messages_before(before_date)
        logger.info(f"Purged {deleted} messages older than {before_date}")
    finally:
        await db.close()


async def run_search(
    config_path: str,
    keyword: str,
    group: str | None,
    search_date: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    json_output: bool,
) -> None:
    """搜索消息。"""
    config = load_config(config_path)
    db = Database(config.data_dir / "messages.db")
    await db.connect()

    try:
        # 解析群组参数
        group_id: int | None = None
        if group:
            try:
                group_id = int(group)
            except ValueError:
                gc = next((g for g in config.groups if g.name == group), None)
                if gc:
                    group_id = gc.id
                else:
                    logger.error(f"未找到群组: {group}")
                    sys.exit(1)

        # 解析日期参数
        dt_from: datetime | None = None
        dt_to: datetime | None = None
        if search_date:
            d = datetime.strptime(search_date, "%Y-%m-%d").date()
            dt_from = datetime.combine(d, datetime.min.time())
            dt_to = datetime.combine(d, datetime.max.time())
        else:
            if date_from:
                dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            if date_to:
                d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
                dt_to = datetime.combine(d_to, datetime.max.time())

        results, total = await db.search_messages(
            keyword,
            group_id=group_id,
            date_from=dt_from,
            date_to=dt_to,
            limit=limit,
        )

        if json_output:
            from .search import format_results_json

            print(format_results_json(results, total))
        else:
            from .search import format_results

            print(format_results(results, total))
    finally:
        await db.close()


async def run_reindex(config_path: str) -> None:
    """重建 FTS 索引。"""
    config = load_config(config_path)
    db = Database(config.data_dir / "messages.db")
    await db.connect()

    try:
        count = await db.reindex_all()
        logger.info(f"已重建 {count} 条消息的 FTS 索引")
    finally:
        await db.close()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="tg-tldr",
        description="Telegram group chat recorder with daily AI-powered summaries",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    subparsers.add_parser("run", help="Run the daemon (default)")

    summary_parser = subparsers.add_parser("summary", help="Generate summary for a date")
    summary_parser.add_argument(
        "-d",
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Date to summarize (YYYY-MM-DD, default: yesterday)",
    )

    purge_parser = subparsers.add_parser("purge", help="Delete messages older than a date")
    purge_parser.add_argument(
        "before_date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        help="Delete messages before this date (YYYY-MM-DD)",
    )

    search_parser = subparsers.add_parser("search", help="搜索消息")
    search_parser.add_argument("keyword", help="搜索关键词")
    search_parser.add_argument("-g", "--group", default=None, help="群组名称或 ID")
    search_parser.add_argument(
        "-d",
        "--date",
        default=None,
        dest="search_date",
        help="搜索指定日期 (YYYY-MM-DD)",
    )
    search_parser.add_argument(
        "--from", default=None, dest="date_from", help="起始日期 (YYYY-MM-DD)"
    )
    search_parser.add_argument("--to", default=None, dest="date_to", help="截止日期 (YYYY-MM-DD)")
    search_parser.add_argument(
        "-n", "--limit", type=int, default=50, help="最多返回条数 (默认: 50)"
    )
    search_parser.add_argument("--json", action="store_true", help="JSON 格式输出")

    subparsers.add_parser("reindex", help="重建 FTS 全文搜索索引")

    args = parser.parse_args()

    if args.command == "summary":
        target_date = args.date or (date.today() - __import__("datetime").timedelta(days=1))
        asyncio.run(run_summary(args.config, target_date))
    elif args.command == "purge":
        asyncio.run(run_purge(args.config, args.before_date))
    elif args.command == "search":
        asyncio.run(
            run_search(
                args.config,
                args.keyword,
                args.group,
                args.search_date,
                args.date_from,
                args.date_to,
                args.limit,
                args.json,
            )
        )
    elif args.command == "reindex":
        asyncio.run(run_reindex(args.config))
    else:
        asyncio.run(run_daemon(args.config))


if __name__ == "__main__":
    main()
