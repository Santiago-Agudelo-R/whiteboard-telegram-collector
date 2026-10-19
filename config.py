import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

DAY_MAP = {
    "monday": 0, "lunes": 0, "mon": 0, "lun": 0,
    "tuesday": 1, "martes": 1, "tue": 1, "mar": 1,
    "wednesday": 2, "miercoles": 2, "miércoles": 2, "wed": 2, "mie": 2,
    "thursday": 3, "jueves": 3, "thu": 3, "jue": 3,
    "friday": 4, "viernes": 4, "fri": 4, "vie": 4,
    "saturday": 5, "sabado": 5, "sábado": 5, "sat": 5, "sab": 5,
    "sunday": 6, "domingo": 6, "sun": 6, "dom": 6,
}

DAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday"
}

# Kept for backward compatibility
SPANISH_DAY_NAMES = DAY_NAMES


class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

    # Parse comma-separated list of authorized Telegram chat IDs
    raw_chat_ids = os.getenv("AUTHORIZED_CHAT_ID", "").strip()
    AUTHORIZED_CHAT_IDS = set()
    if raw_chat_ids:
        for cid in raw_chat_ids.split(","):
            cid_clean = cid.strip()
            if cid_clean:
                try:
                    AUTHORIZED_CHAT_IDS.add(int(cid_clean))
                except ValueError:
                    logger.warning(f"Invalid Chat ID in .env: {cid_clean}")

    DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_ROOT", str(Path(__file__).parent / "Whiteboard_Photos"))).resolve()

    try:
        SYNC_HOUR = int(os.getenv("SYNC_HOUR", "21").strip())
    except ValueError:
        SYNC_HOUR = 21

    try:
        SYNC_MINUTE = int(os.getenv("SYNC_MINUTE", "0").strip())
    except ValueError:
        SYNC_MINUTE = 0

    raw_allowed_days = os.getenv("ALLOWED_DAYS", "tuesday,thursday").strip()
    ALLOWED_DAY_NUMBERS = set()
    for day in raw_allowed_days.split(","):
        day_clean = day.strip().lower()
        if day_clean in DAY_MAP:
            ALLOWED_DAY_NUMBERS.add(DAY_MAP[day_clean])
        elif day_clean:
            logger.warning(f"Unrecognized day in ALLOWED_DAYS: {day_clean}")

    @classmethod
    def schedule_description(cls) -> str:
        """Return a human-readable summary of the configured sync schedule."""
        days = [DAY_NAMES[d] for d in sorted(cls.ALLOWED_DAY_NUMBERS)]
        if not days:
            days_text = "Every day"
        elif len(days) == 1:
            days_text = days[0]
        else:
            days_text = ", ".join(days[:-1]) + " and " + days[-1]
        return f"{days_text} at {cls.SYNC_HOUR:02d}:{cls.SYNC_MINUTE:02d}"

    @classmethod
    def validate(cls):
        """Validate that required configuration settings are present."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is not defined in the .env file")

        cls.DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
