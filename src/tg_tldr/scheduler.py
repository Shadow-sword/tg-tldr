"""Scheduled task management using APScheduler."""

import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .collector import MessageCollector
from .config import Config
from .summarizer import Summarizer

logger = logging.getLogger(__name__)


class SummaryScheduler:
    """Schedules daily summary generation and delivery."""

    def __init__(
        self,
        config: Config,
        summarizer: Summarizer,
        collector: MessageCollector,
    ):
        self.config = config
        self.summarizer = summarizer
        self.collector = collector
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """Start the scheduler with configured schedule."""
        schedule_time = self.config.summary.schedule
        hour, minute = map(int, schedule_time.split(":"))

        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=self.config.summary.timezone,
        )

        self.scheduler.add_job(
            self._run_daily_summary,
            trigger=trigger,
            id="daily_summary",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(
            f"Scheduler started, daily summary at {schedule_time} ({self.config.summary.timezone})"
        )

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    async def _run_daily_summary(self) -> None:
        """Run the daily summary job for all groups."""
        yesterday = date.today() - timedelta(days=1)
        logger.info(f"Running daily summary for {yesterday}")

        for group in self.config.groups:
            try:
                summary = await self.summarizer.summarize_group(group, yesterday)

                if summary:
                    target = self.config.get_summary_target(group)
                    if target:
                        header = f"📋 【{group.name}】{yesterday} 群聊总结\n\n"
                        await self.collector.send_message(target, header + summary)
                        logger.info(f"Sent summary for {group.name} to {target}")
            except Exception as e:
                logger.exception(f"Failed to summarize {group.name}: {e}")

    async def run_manual_summary(self, target_date: date | None = None) -> None:
        """Manually trigger summary generation."""
        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        logger.info(f"Manual summary triggered for {target_date}")

        for group in self.config.groups:
            try:
                summary = await self.summarizer.summarize_group(group, target_date)

                if summary:
                    target = self.config.get_summary_target(group)
                    if target:
                        header = f"📋 【{group.name}】{target_date} 群聊总结\n\n"
                        await self.collector.send_message(target, header + summary)
                        logger.info(f"Sent summary for {group.name} to {target}")
                    else:
                        logger.info(f"Summary for {group.name}:\n{summary}")
            except Exception as e:
                logger.exception(f"Failed to summarize {group.name}: {e}")
