# Whiteboard Telegram Collector

Automated asynchronous Python service for capturing whiteboard photos via a private Telegram bot, organizing them by session date, and compiling them into consolidated PDF lecture decks.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![python-telegram-bot](https://img.shields.io/badge/Telegram_Bot_API-v20%2B-blue.svg)](https://github.com/python-telegram-bot/python-telegram-bot)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

Capturing classroom blackboard and whiteboard diagrams during lectures frequently results in disorganised photo galleries on mobile devices. `Whiteboard Telegram Collector` provides an end-to-end automated pipeline:

1. **Private Telegram Ingestion:** Accepts incoming photos strictly from authorized Telegram Chat IDs, rejecting unauthenticated traffic.
2. **Metadata & State Tracking:** Tracks received photos in a local SQLite database with timestamps and upload status.
3. **Scheduled Synchronization:** Automatically triggers downloads on designated lecture days/times using APScheduler.
4. **Automated PDF Compilation:** Bundles chronological daily captures into a consolidated PDF study document per session using `Pillow` and `img2pdf`.

---

## Architecture

```text
[Mobile Telegram App] ───(Secure Bot API)───> [bot.py (Async Ingestion)]
                                                     │
                                                     ▼
                                          [SQLite Database (database.py)]
                                                     │
                                                     ▼
[APScheduler (scheduler.py)] ──── triggers ───> [downloader.py]
                                                     │
                                                     ▼
                                          [Date-Sorted Storage]
                                                     │
                                                     ▼
                                          [pdf_generator.py] ──> Daily PDF Deck
```

- **`bot.py`**: Telegram bot implementation using `python-telegram-bot` v20+ with authorization guards and photo download handlers.
- **`database.py`**: SQLite data access layer for recording file IDs, capture timestamps, and download tracking.
- **`downloader.py`**: Batch asset downloader that pulls pending media and places them into date-stamped directory structures.
- **`pdf_generator.py`**: Image processing engine that sorts images chronologically, optimizes aspect ratios, and generates searchable PDF decks.
- **`scheduler.py`**: Background task scheduler configuring cron-like execution for specific class days and hours.

---

## Requirements

- Python 3.10+
- A registered Telegram Bot token from [@BotFather](https://t.me/BotFather)

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env`:

```ini
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
AUTHORIZED_CHAT_ID=your_chat_id_here

# Directory where photos will be stored organized by date
DOWNLOAD_ROOT=./downloads/whiteboard_photos

# Scheduled Synchronization Configuration (24h format)
SYNC_HOUR=21
SYNC_MINUTE=0

# Permitted sync days
ALLOWED_DAYS=tuesday,thursday
```

---

## Usage

### Run the Service (Bot + Background Scheduler)
```bash
python main.py
```

### Run Immediate Manual Synchronization
```bash
python main.py --sync-now
```

### Generate PDF for a Specific Date
```bash
python main.py --generate-pdf "2026-10-05"
```

---

## Security & Privacy Considerations

- **Authorization Whitelist:** The bot ignores messages from any Chat ID not explicitly declared in `AUTHORIZED_CHAT_ID`.
- **Environment Isolation:** Tokens, databases, and downloaded photos are strictly excluded from version control via `.gitignore`.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
