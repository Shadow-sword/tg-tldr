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

    args = parser.parse_args()

    if args.command == "summary":
        target_date = args.date or (date.today() - __import__("datetime").timedelta(days=1))
        asyncio.run(run_summary(args.config, target_date))
    elif args.command == "purge":
        asyncio.run(run_purge(args.config, args.before_date))
    else:
        asyncio.run(run_daemon(args.config))


if __name__ == "__main__":
    main()
