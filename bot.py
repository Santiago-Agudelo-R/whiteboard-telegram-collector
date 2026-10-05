import logging
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from config import Config
import database
import downloader

logger = logging.getLogger(__name__)

def is_authorized(chat_id: int) -> bool:
    """Verifica si un chat_id está en la lista de usuarios autorizados."""
    if not Config.AUTHORIZED_CHAT_IDS:
        return False
    return chat_id in Config.AUTHORIZED_CHAT_IDS

async def check_authorization(update: Update) -> bool:
    """Valida el acceso del usuario. Si no está autorizado, responde y devuelve False."""
    chat_id = update.effective_chat.id
    if not is_authorized(chat_id):
        logger.warning(f"Intento de acceso no autorizado desde chat_id: {chat_id}")
        if not Config.AUTHORIZED_CHAT_IDS:
            msg = (
                f"⚠️ **Bot Privado**\n\n"
                f"Aún no has configurado tu Chat ID autorizado.\n"
                f"Tu Chat ID es: `{chat_id}`\n\n"
                f"Por favor, agrégalo a tu archivo `.env` en `AUTHORIZED_CHAT_ID={chat_id}` y reinicia la aplicación."
            )
        else:
            msg = "⛔ Acceso denegado. Este es un bot privado."
        
        if update.message:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return False
    return True

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start."""
    if not await check_authorization(update):
        return
    
    welcome_text = (
        "📸 **Bot Recolector de Apuntes del Tablero**\n\n"
        "Envía tus fotografías del tablero en cualquier momento durante las clases.\n"
        f"Serán guardadas y descargadas automáticamente en tu PC: {Config.schedule_description()}.\n\n"
        "Comandos disponibles:\n"
        "/status - Estado del bot y fotos pendientes\n"
        "/sync - Iniciar sincronización manual\n"
        "/help - Ayuda e instrucciones"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /status."""
    if not await check_authorization(update):
        return
    
    pending_count = database.get_pending_count()
    last_sync = database.get_last_sync_time()
    
    status_text = (
        "🤖 **Estado del Sistema**\n\n"
        f"• **Estado:** En línea y funcionando\n"
        f"• **Usuario autorizado:** Sí (`{update.effective_chat.id}`)\n"
        f"• **Fotografías pendientes:** {pending_count}\n"
        f"• **Última sincronización:** {last_sync}\n\n"
        f"• **Programación:** {Config.schedule_description()}"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /sync para forzar la sincronización."""
    if not await check_authorization(update):
        return
    
    pending_count = database.get_pending_count()
    if pending_count == 0:
        await update.message.reply_text("ℹ️ No hay fotografías pendientes para sincronizar.")
        return
    
    await update.message.reply_text(f"🔄 Iniciando sincronización manual de {pending_count} fotografía(s)...")
    res = await downloader.sync_photos(context.bot)
    
    summary_text = (
        "✅ **Sincronización completada**\n\n"
        f"• Fotografías procesadas: {res['total']}\n"
        f"• Guardadas con éxito: {res['downloaded']}\n"
        f"• Fallidas: {res['failed']}"
    )
    await update.message.reply_text(summary_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /help."""
    if not await check_authorization(update):
        return
    
    help_text = (
        "📖 **Guía de Uso**\n\n"
        "1. **Enviar fotos:** Simplemente toma una foto del tablero y envíala a este chat (como foto o archivo de imagen).\n"
        f"2. **Procesamiento automático:** La PC descargará las fotos: {Config.schedule_description()}.\n"
        "3. **Sincronización manual:** Usa el comando /sync si deseas descargar las fotos inmediatamente sin esperar al horario programado.\n"
        "4. **Consultar estado:** Usa /status para saber cuántas fotos faltan por descargar."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa fotografías enviadas al bot (individuales o en álbumes)."""
    if not await check_authorization(update):
        return
    
    message = update.message
    if not message or not message.photo:
        return
        
    # Obtener la versión de mayor resolución de la foto
    photo = message.photo[-1]
    
    saved = database.save_photo_metadata(
        message_id=message.message_id,
        chat_id=message.chat_id,
        file_id=photo.file_id,
        file_unique_id=photo.file_unique_id,
        message_date=message.date
    )
    
    pending = database.get_pending_count()
    # Si la foto pertenece a un álbum (media_group_id), no enviamos spam de mensajes por cada foto
    if saved and not message.media_group_id:
        await message.reply_text(f"📸 Fotografía registrada (Pendientes para descarga: {pending})")
    elif saved and message.media_group_id:
        logger.info(f"Foto de álbum registrada (message_id={message.message_id}, pendientes={pending})")

async def document_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa imágenes enviadas como documentos/archivos (por mime_type o extensión)."""
    if not await check_authorization(update):
        return
    
    message = update.message
    if not message or not message.document:
        return
        
    doc = message.document
    filename = (doc.file_name or "").lower()
    mime = (doc.mime_type or "").lower()
    
    is_image = (
        mime.startswith("image/") or
        any(filename.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp", ".tiff"])
    )
    
    if not is_image:
        await message.reply_text("⚠️ El archivo enviado no es una imagen reconocida.")
        return
        
    saved = database.save_photo_metadata(
        message_id=message.message_id,
        chat_id=message.chat_id,
        file_id=doc.file_id,
        file_unique_id=doc.file_unique_id,
        message_date=message.date
    )
    
    pending = database.get_pending_count()
    if saved and not message.media_group_id:
        await message.reply_text(f"📄 Imagen (Documento) registrada (Pendientes para descarga: {pending})")


async def pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /pdf para generar y enviar los documentos PDF semanales."""
    if not await check_authorization(update):
        return
    
    await update.message.reply_text("📄 Generando documento PDF semanal de apuntes...")
    import pdf_generator
    pdfs = pdf_generator.generate_weekly_pdfs()
    
    if not pdfs:
        await update.message.reply_text("⚠️ No se encontraron fotos descargadas para generar el PDF semanal.")
        return
    
    await update.message.reply_text(f"✅ Se han generado {len(pdfs)} archivo(s) PDF semanal(es). Enviando el más reciente...")
    latest_pdf = pdfs[-1]
    
    with open(latest_pdf, "rb") as doc_file:
        await update.message.reply_document(
            document=doc_file,
            filename=latest_pdf.name,
            caption=f"📚 **PDF Semanal de Apuntes:**\n`{latest_pdf.name}`",
            parse_mode="Markdown"
        )

def create_application() -> Application:
    """Crea y configura la aplicación de Telegram Bot."""
    Config.validate()
    app = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("sync", sync_command))
    app.add_handler(CommandHandler("pdf", pdf_command))
    app.add_handler(CommandHandler("help", help_command))
    
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.Document.IMAGE, document_photo_handler))
    
    return app

