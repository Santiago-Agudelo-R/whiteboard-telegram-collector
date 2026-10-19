import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config, DAY_NAMES
import downloader

logger = logging.getLogger(__name__)


async def scheduled_sync_job(bot):
    """Scheduled job executed at the configured daily sync time."""
    now = datetime.now()
    current_weekday = now.weekday()

    logger.info(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Evaluating scheduled synchronization task...")

    if Config.ALLOWED_DAY_NUMBERS and current_weekday not in Config.ALLOWED_DAY_NUMBERS:
        day_name = DAY_NAMES.get(current_weekday, "Unknown")
        logger.info(
            f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Today ({day_name}) is not in ALLOWED_DAYS. Skipping automatic sync."
        )
        return

    today_str = now.strftime("%Y-%m-%d")
    logger.info(
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Running scheduled sync for {today_str} ({DAY_NAMES.get(current_weekday)})..."
    )

    res = await downloader.sync_photos(bot, date_filter=today_str)

    if res["total"] > 0 and Config.AUTHORIZED_CHAT_IDS:
        notification_text = (
            f"**Scheduled Synchronization ({Config.SYNC_HOUR:02d}:{Config.SYNC_MINUTE:02d})**\n\n"
            f"- Photos found today: {res['total']}\n"
            f"- Downloaded: {res['downloaded']}\n"
            f"- Failed: {res['failed']}"
        )
        for chat_id in Config.AUTHORIZED_CHAT_IDS:
            try:
                await bot.send_message(chat_id=chat_id, text=notification_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send scheduled notification to chat_id {chat_id}: {e}")


def setup_scheduler(app) -> AsyncIOScheduler:
    """Configure and return the APScheduler instance."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        scheduled_sync_job,
        trigger=CronTrigger(hour=Config.SYNC_HOUR, minute=Config.SYNC_MINUTE),
        args=[app.bot],
        id="daily_tablero_sync",
        replace_existing=True
    )

    logger.info(f"Task scheduler initialized: daily trigger at {Config.SYNC_HOUR:02d}:{Config.SYNC_MINUTE:02d}.")
    return scheduler
