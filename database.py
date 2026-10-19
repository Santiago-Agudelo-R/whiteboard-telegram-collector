import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent / "database.db"


def get_connection():
    """Return a SQLite database connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite database tables if they do not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE NOT NULL,
                chat_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                file_unique_id TEXT NOT NULL,
                message_date TEXT NOT NULL,
                download_date TEXT,
                local_path TEXT,
                status TEXT DEFAULT 'pending'
            );
        """)
        conn.commit()
    logger.info("SQLite database initialized.")


def save_photo_metadata(message_id: int, chat_id: int, file_id: str, file_unique_id: str, message_date: datetime) -> bool:
    """
    Save metadata for a received photo.
    Returns True if inserted, or False if the message_id already exists.
    """
    date_str = message_date.strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO photos (message_id, chat_id, file_id, file_unique_id, message_date, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """, (message_id, chat_id, file_id, file_unique_id, date_str))
            conn.commit()
            logger.info(f"Photo registered [message_id={message_id}, file_unique_id={file_unique_id}]")
            return True
        except sqlite3.IntegrityError:
            logger.info(f"Photo already exists in database, skipping duplicate [message_id={message_id}]")
            return False


def get_pending_photos(date_filter: str = None):
    """
    Retrieve pending photos ordered chronologically.
    If date_filter is provided (YYYY-MM-DD), filters records for that date.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if date_filter:
            cursor.execute("""
                SELECT * FROM photos
                WHERE status = 'pending' AND message_date LIKE ?
                ORDER BY message_date ASC
            """, (f"{date_filter}%",))
        else:
            cursor.execute("""
                SELECT * FROM photos
                WHERE status = 'pending'
                ORDER BY message_date ASC
            """)
        return cursor.fetchall()


def get_pending_count(date_filter: str = None) -> int:
    """Return the count of photos with status='pending'."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if date_filter:
            cursor.execute("""
                SELECT COUNT(*) as count FROM photos
                WHERE status = 'pending' AND message_date LIKE ?
            """, (f"{date_filter}%",))
        else:
            cursor.execute("""
                SELECT COUNT(*) as count FROM photos
                WHERE status = 'pending'
            """)
        row = cursor.fetchone()
        return row["count"] if row else 0


def mark_as_downloaded(photo_id: int, local_path: str):
    """Mark a photo record as downloaded and record its local file path."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE photos
            SET status = 'downloaded', download_date = ?, local_path = ?
            WHERE id = ?
        """, (now_str, str(local_path), photo_id))
        conn.commit()


def mark_as_failed(photo_id: int):
    """Mark a photo record as failed."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE photos
            SET status = 'failed'
            WHERE id = ?
        """, (photo_id,))
        conn.commit()


def get_last_sync_time() -> str:
    """Return the timestamp of the most recent successful download, or 'Never'."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT download_date FROM photos
            WHERE status = 'downloaded'
            ORDER BY download_date DESC LIMIT 1
        """)
        row = cursor.fetchone()
        if row and row["download_date"]:
            return row["download_date"]
        return "Never"
