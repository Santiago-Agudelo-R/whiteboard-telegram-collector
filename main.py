import argparse
import asyncio
import logging
from config import Config
import database
import downloader
import bot
import scheduler

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def run_manual_sync():
    """Run an immediate manual synchronization from the command line."""
    database.init_db()
    app = bot.create_application()
    async with app:
        await app.initialize()
        await app.start()
        res = await downloader.sync_photos(app.bot)
        await app.stop()
        await app.shutdown()
        logger.info(f"Manual synchronization finished: {res['downloaded']} downloaded.")


async def post_init_callback(application):
    """Application startup callback to initialize and start APScheduler."""
    sched = scheduler.setup_scheduler(application)
    sched.start()
    application.scheduler_instance = sched
    logger.info("Telegram Bot and background scheduler are active.")


def main():
    parser = argparse.ArgumentParser(description="Whiteboard Telegram Photo Collector")
    parser.add_argument("--sync", action="store_true", help="Force an immediate manual synchronization of pending photos")
    parser.add_argument("--pdf", action="store_true", help="Generate weekly PDF decks from downloaded photos")
    args = parser.parse_args()

    Config.validate()
    database.init_db()

    if args.sync:
        logger.info("Manual synchronization requested via CLI (--sync).")
        asyncio.run(run_manual_sync())
        return

    if args.pdf:
        logger.info("Weekly PDF generation requested via CLI (--pdf).")
        import pdf_generator
        pdfs = pdf_generator.generate_weekly_pdfs()
        logger.info(f"Generated {len(pdfs)} weekly PDF file(s).")
        return

    logger.info("Starting service in continuous polling mode...")
    app = bot.create_application()
    app.post_init = post_init_callback

    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error during bot execution: {e}")


if __name__ == "__main__":
    main()
