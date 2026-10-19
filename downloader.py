import re
import logging
from pathlib import Path
from datetime import datetime
from config import Config, DAY_NAMES
import database

logger = logging.getLogger(__name__)


def get_next_tablero_index(folder_path: Path) -> int:
    """
    Scan the target directory and return the next sequential index for tablero_XX.jpg.
    """
    if not folder_path.exists():
        return 1

    max_index = 0
    pattern = re.compile(r"^(?:tablero|board)_(\d+)\.[a-zA-Z0-9]+$")
    for file_item in folder_path.iterdir():
        if file_item.is_file():
            match = pattern.match(file_item.name)
            if match:
                idx = int(match.group(1))
                if idx > max_index:
                    max_index = idx
    return max_index + 1


async def sync_photos(bot, date_filter: str = None) -> dict:
    """
    Synchronize and download pending photos from Telegram.

    :param bot: Telegram Bot instance (telegram.Bot)
    :param date_filter: Optional 'YYYY-MM-DD' date filter. If None, downloads all pending photos.
    :return: Dictionary with total, downloaded, and failed counts.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{now_str}] Starting photo synchronization...")

    pending_photos = database.get_pending_photos(date_filter=date_filter)
    total_count = len(pending_photos)

    if total_count == 0:
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No pending photos to download.")
        return {"total": 0, "downloaded": 0, "failed": 0}

    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Pending photos found: {total_count}")

    downloaded_count = 0
    failed_count = 0

    for idx, photo in enumerate(pending_photos, start=1):
        photo_id = photo["id"]
        file_id = photo["file_id"]
        msg_date_str = photo["message_date"]

        try:
            msg_dt = datetime.strptime(msg_date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            msg_dt = datetime.now()

        day_num = msg_dt.weekday()
        day_name = DAY_NAMES.get(day_num, "Day")
        folder_name = f"{msg_dt.strftime('%Y-%m-%d')}_{day_name}"

        target_dir = Config.DOWNLOAD_ROOT / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        next_idx = get_next_tablero_index(target_dir)
        filename = f"tablero_{next_idx:02d}.jpg"
        local_file_path = target_dir / filename

        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Downloading photo {idx}/{total_count}")

        try:
            tg_file = await bot.get_file(file_id)
            await tg_file.download_to_drive(custom_path=str(local_file_path))

            database.mark_as_downloaded(photo_id, local_file_path)
            downloaded_count += 1
            logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Saved: {filename} in {folder_name}")
        except Exception as e:
            failed_count += 1
            database.mark_as_failed(photo_id)
            logger.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Failed to download photo {photo_id}: {e}")

    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Synchronization completed: {downloaded_count} downloaded, {failed_count} failed.")

    try:
        import pdf_generator
        pdf_generator.generate_weekly_pdfs()
    except Exception as e:
        logger.error(f"Error generating weekly PDFs after synchronization: {e}")

    return {
        "total": total_count,
        "downloaded": downloaded_count,
        "failed": failed_count
    }
