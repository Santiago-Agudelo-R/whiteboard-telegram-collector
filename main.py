import argparse
import asyncio
import logging
from config import Config
import database
import downloader
import bot
import scheduler

# Configurar logging en el formato solicitado
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def run_manual_sync():
    """Ejecuta una sincronización manual inmediata desde la línea de comandos."""
    database.init_db()
    app = bot.create_application()
    async with app:
        await app.initialize()
        await app.start()
        res = await downloader.sync_photos(app.bot)
        await app.stop()
        await app.shutdown()
        logger.info(f"Sincronización manual finalizada: {res['downloaded']} guardadas.")

async def post_init_callback(application):
    """Callback de inicialización del bot para arrancar el programador de tareas."""
    sched = scheduler.setup_scheduler(application)
    sched.start()
    application.scheduler_instance = sched
    logger.info("Bot de Telegram y Programador de Tareas activos.")

def main():
    parser = argparse.ArgumentParser(description="Bot Recolector de Fotos del Tablero")
    parser.add_argument("--sync", action="store_true", help="Fuerza una sincronización manual inmediata de las fotos pendientes")
    parser.add_argument("--pdf", action="store_true", help="Genera los documentos PDF semanales para las fotos descargadas")
    args = parser.parse_args()

    # Validar configuración antes de proceder
    Config.validate()
    database.init_db()

    if args.sync:
        logger.info("Modo de sincronización manual solicitado vía CLI (--sync).")
        asyncio.run(run_manual_sync())
        return

    if args.pdf:
        logger.info("Generación de PDFs semanales solicitada vía CLI (--pdf).")
        import pdf_generator
        pdfs = pdf_generator.generate_weekly_pdfs()
        logger.info(f"Se generaron {len(pdfs)} archivo(s) PDF semanal(es).")
        return


    logger.info("Iniciando aplicación en modo continuo...")
    app = bot.create_application()
    app.post_init = post_init_callback

    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Aplicación detenida por el usuario.")
    except Exception as e:
        logger.error(f"Error inesperado en la ejecución del bot: {e}")

if __name__ == "__main__":
    main()
