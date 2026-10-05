import sqlite3
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent / "database.db"

def get_connection():
    """Retorna una conexión a la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa las tablas de la base de datos si no existen."""
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
    logger.info("Base de datos SQLite inicializada correctamente.")

def save_photo_metadata(message_id: int, chat_id: int, file_id: str, file_unique_id: str, message_date: datetime) -> bool:
    """
    Guarda los metadatos de una fotografía recibida.
    Devuelve True si se insertó, False si ya existía (evita duplicados).
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
            logger.info(f"Fotografía registrada [message_id={message_id}, file_unique_id={file_unique_id}]")
            return True
        except sqlite3.IntegrityError:
            logger.info(f"Fotografía ya existente en BD, ignorando duplicado [message_id={message_id}]")
            return False

def get_pending_photos(date_filter: str = None):
    """
    Obtiene las fotografías pendientes.
    Si date_filter es proporcionado (formato YYYY-MM-DD), filtra solo las de ese día.
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
    """Devuelve la cantidad de fotografías pendientes."""
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
    """Marca una fotografía como descargada y registra la ruta local."""
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
    """Marca una fotografía como fallida."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE photos
            SET status = 'failed'
            WHERE id = ?
        """, (photo_id,))
        conn.commit()

def get_last_sync_time() -> str:
    """Retorna la fecha y hora de la última descarga exitosa."""
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
        return "Nunca"
