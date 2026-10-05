import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config, SPANISH_DAY_NAMES
import downloader

logger = logging.getLogger(__name__)

async def scheduled_sync_job(bot):
    """Tarea programada que se ejecuta a la hora configurada (ej. 21:00 hs)."""
    now = datetime.now()
    current_weekday = now.weekday()
    
    logger.info(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Evaluando tarea programada de sincronización...")
    
    # Verificar si el día actual de la semana está en los días permitidos
    if Config.ALLOWED_DAY_NUMBERS and current_weekday not in Config.ALLOWED_DAY_NUMBERS:
        day_name = SPANISH_DAY_NAMES.get(current_weekday, "Desconocido")
        logger.info(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Hoy ({day_name}) no está en la lista de días permitidos. Omitiendo sincronización automática.")
        return

    today_str = now.strftime("%Y-%m-%d")
    logger.info(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Ejecutando sincronización automática para el día {today_str} ({SPANISH_DAY_NAMES.get(current_weekday)})...")
    
    res = await downloader.sync_photos(bot, date_filter=today_str)
    
    # Notificar al usuario por Telegram si se descargaron fotos o hubo errores
    if res["total"] > 0 and Config.AUTHORIZED_CHAT_IDS:
        notification_text = (
            f"🔔 **Sincronización Automática Programada ({Config.SYNC_HOUR:02d}:{Config.SYNC_MINUTE:02d})**\n\n"
            f"• Fotografías encontradas hoy: {res['total']}\n"
            f"• Guardadas exitosamente: {res['downloaded']}\n"
            f"• Fallidas: {res['failed']}"
        )
        for chat_id in Config.AUTHORIZED_CHAT_IDS:
            try:
                await bot.send_message(chat_id=chat_id, text=notification_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Error al enviar notificación programada a chat_id {chat_id}: {e}")

def setup_scheduler(app) -> AsyncIOScheduler:
    """Configura y retorna el programador APScheduler."""
    scheduler = AsyncIOScheduler()
    
    # Añadir trabajo Cron diario a SYNC_HOUR:SYNC_MINUTE
    scheduler.add_job(
        scheduled_sync_job,
        trigger=CronTrigger(hour=Config.SYNC_HOUR, minute=Config.SYNC_MINUTE),
        args=[app.bot],
        id="daily_tablero_sync",
        replace_existing=True
    )
    
    logger.info(f"Programador de tareas iniciado: Ejecución diaria a las {Config.SYNC_HOUR:02d}:{Config.SYNC_MINUTE:02d} hs.")
    return scheduler
