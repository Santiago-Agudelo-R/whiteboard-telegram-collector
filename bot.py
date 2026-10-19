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
    """Return True if chat_id is in the configured set of authorized users."""
    if not Config.AUTHORIZED_CHAT_IDS:
        return False
    return chat_id in Config.AUTHORIZED_CHAT_IDS


async def check_authorization(update: Update) -> bool:
    """Validate user authorization. Replies with an error message and returns False if unauthorized."""
    chat_id = update.effective_chat.id
    if not is_authorized(chat_id):
        logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
        if not Config.AUTHORIZED_CHAT_IDS:
            msg = (
                f"**Private Bot**\n\n"
                f"No authorized Chat ID is configured yet.\n"
                f"Your Chat ID is: `{chat_id}`\n\n"
                f"Add `AUTHORIZED_CHAT_ID={chat_id}` to your `.env` file and restart the service."
            )
        else:
            msg = "Access denied. This is a private bot."

        if update.message:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return False
    return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    if not await check_authorization(update):
        return

    welcome_text = (
        "**Whiteboard Photo Collector**\n\n"
        "Send whiteboard photos at any time during lectures.\n"
        f"Photos are queued and synchronized automatically: {Config.schedule_description()}.\n\n"
        "Available commands:\n"
        "/status - Service status and pending photo count\n"
        "/sync - Trigger an immediate manual synchronization\n"
        "/pdf - Compile and send the latest weekly PDF\n"
        "/help - Usage instructions"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /status command."""
    if not await check_authorization(update):
        return

    pending_count = database.get_pending_count()
    last_sync = database.get_last_sync_time()

    status_text = (
        "**System Status**\n\n"
        f"- **Status:** Online\n"
        f"- **Authorized Chat ID:** `{update.effective_chat.id}`\n"
        f"- **Pending photos:** {pending_count}\n"
        f"- **Last synchronization:** {last_sync}\n"
        f"- **Schedule:** {Config.schedule_description()}"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /sync command to trigger an immediate download."""
    if not await check_authorization(update):
        return

    pending_count = database.get_pending_count()
    if pending_count == 0:
        await update.message.reply_text("No pending photos to synchronize.")
        return

    await update.message.reply_text(f"Starting manual synchronization of {pending_count} photo(s)...")
    res = await downloader.sync_photos(context.bot)

    summary_text = (
        "**Synchronization Completed**\n\n"
        f"- Processed: {res['total']}\n"
        f"- Downloaded: {res['downloaded']}\n"
        f"- Failed: {res['failed']}"
    )
    await update.message.reply_text(summary_text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
    if not await check_authorization(update):
        return

    help_text = (
        "**Usage Guide**\n\n"
        "1. **Send photos:** Send whiteboard photos to this chat as standard images or uncompressed document files.\n"
        f"2. **Automated sync:** Scheduled downloads run on: {Config.schedule_description()}.\n"
        "3. **Manual sync:** Run /sync to download pending photos immediately.\n"
        "4. **Check status:** Run /status to inspect the pending queue."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process incoming photos sent to the bot (single photos or media albums)."""
    if not await check_authorization(update):
        return

    message = update.message
    if not message or not message.photo:
        return

    # Select the highest-resolution photo variant
    photo = message.photo[-1]

    saved = database.save_photo_metadata(
        message_id=message.message_id,
        chat_id=message.chat_id,
        file_id=photo.file_id,
        file_unique_id=photo.file_unique_id,
        message_date=message.date
    )

    pending = database.get_pending_count()
    # Avoid replying to every item in a media album
    if saved and not message.media_group_id:
        await message.reply_text(f"Photo queued (Pending downloads: {pending})")
    elif saved and message.media_group_id:
        logger.info(f"Album photo queued (message_id={message.message_id}, pending={pending})")


async def document_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process uncompressed images sent as document attachments."""
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
        await message.reply_text("The uploaded document is not a supported image format.")
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
        await message.reply_text(f"Image document queued (Pending downloads: {pending})")


async def pdf_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /pdf command to compile and send weekly PDF decks."""
    if not await check_authorization(update):
        return

    await update.message.reply_text("Generating weekly lecture PDF...")
    import pdf_generator
    pdfs = pdf_generator.generate_weekly_pdfs()

    if not pdfs:
        await update.message.reply_text("No downloaded photos found to compile a weekly PDF.")
        return

    await update.message.reply_text(f"Generated {len(pdfs)} weekly PDF file(s). Uploading the most recent deck...")
    latest_pdf = pdfs[-1]

    with open(latest_pdf, "rb") as doc_file:
        await update.message.reply_document(
            document=doc_file,
            filename=latest_pdf.name,
            caption=f"**Weekly Lecture Notes PDF:**\n`{latest_pdf.name}`",
            parse_mode="Markdown"
        )


def create_application() -> Application:
    """Create and configure the Telegram Bot application instance."""
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
