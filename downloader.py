import re
import logging
from pathlib import Path
from datetime import datetime
from config import Config, SPANISH_DAY_NAMES
import database

logger = logging.getLogger(__name__)

def get_next_tablero_index(folder_path: Path) -> int:
    """
    Escanea la carpeta de destino y encuentra el siguiente número ordinal disponible para tablero_XX.jpg.
    """
    if not folder_path.exists():
        return 1
    
    max_index = 0
    pattern = re.compile(r"^tablero_(\d+)\.[a-zA-Z0-9]+$")
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
    Sincroniza y descarga las fotografías pendientes desde Telegram.
    
    :param bot: Instancia del Bot de Telegram (telegram.Bot)
    :param date_filter: Opcional 'YYYY-MM-DD'. Si es None, descarga todas las pendientes.
    :return: dict con el resultado de la sincronización.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{now_str}] Iniciando sincronización...")
    
    pending_photos = database.get_pending_photos(date_filter=date_filter)
    total_count = len(pending_photos)
    
    if total_count == 0:
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No hay fotografías pendientes para descargar.")
        return {"total": 0, "downloaded": 0, "failed": 0}
    
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fotografías encontradas: {total_count}")
    
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
        day_name = SPANISH_DAY_NAMES.get(day_num, "Dia")
        folder_name = f"{msg_dt.strftime('%Y-%m-%d')}_{day_name}"
        
        target_dir = Config.DOWNLOAD_ROOT / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        
        next_idx = get_next_tablero_index(target_dir)
        filename = f"tablero_{next_idx:02d}.jpg"
        local_file_path = target_dir / filename
        
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Descargando fotografía {idx}/{total_count}")
        
        try:
            tg_file = await bot.get_file(file_id)
            await tg_file.download_to_drive(custom_path=str(local_file_path))
            
            database.mark_as_downloaded(photo_id, local_file_path)
            downloaded_count += 1
            logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Guardada: {filename} en {folder_name}")
        except Exception as e:
            failed_count += 1
            database.mark_as_failed(photo_id)
            logger.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error descargando fotografía {photo_id}: {e}")
            
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sincronización completada: {downloaded_count} exitosas, {failed_count} fallidas.")
    
    # Generar / Actualizar automáticamente los documentos PDF semanales
    try:
        import pdf_generator
        pdf_generator.generate_weekly_pdfs()
    except Exception as e:
        logger.error(f"Error generando PDFs semanales tras la sincronización: {e}")
        
    return {
        "total": total_count,
        "downloaded": downloaded_count,
        "failed": failed_count
    }

