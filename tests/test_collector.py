import sys
from pathlib import Path
from datetime import datetime
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import database
import downloader
import bot


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_database.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    database.init_db()
    return db_file


def test_save_and_deduplicate_photo_metadata(temp_db):
    msg_dt = datetime(2026, 3, 10, 14, 30, 0)
    inserted_first = database.save_photo_metadata(
        message_id=101,
        chat_id=999001,
        file_id="file_abc_1",
        file_unique_id="uniq_abc_1",
        message_date=msg_dt,
    )
    assert inserted_first is True

    # Duplicate message_id should be ignored
    inserted_duplicate = database.save_photo_metadata(
        message_id=101,
        chat_id=999001,
        file_id="file_abc_1",
        file_unique_id="uniq_abc_1",
        message_date=msg_dt,
    )
    assert inserted_duplicate is False
    assert database.get_pending_count() == 1


def test_pending_filter_and_status_transitions(temp_db):
    dt_day1 = datetime(2026, 3, 10, 10, 0, 0)
    dt_day2 = datetime(2026, 3, 12, 11, 15, 0)

    database.save_photo_metadata(201, 12345, "f1", "u1", dt_day1)
    database.save_photo_metadata(202, 12345, "f2", "u2", dt_day2)

    assert database.get_pending_count() == 2
    assert database.get_pending_count(date_filter="2026-03-10") == 1
    assert database.get_last_sync_time() == "Never"

    day1_rows = database.get_pending_photos(date_filter="2026-03-10")
    assert len(day1_rows) == 1
    photo_id = day1_rows[0]["id"]

    database.mark_as_downloaded(photo_id, "/tmp/2026-03-10_Tuesday/tablero_01.jpg")
    assert database.get_pending_count() == 1
    assert database.get_last_sync_time() != "Never"

    day2_rows = database.get_pending_photos(date_filter="2026-03-12")
    database.mark_as_failed(day2_rows[0]["id"])
    assert database.get_pending_count() == 0


def test_get_next_tablero_index(tmp_path):
    target_dir = tmp_path / "2026-03-10_Tuesday"
    assert downloader.get_next_tablero_index(target_dir) == 1

    target_dir.mkdir(parents=True)
    (target_dir / "tablero_01.jpg").write_bytes(b"img1")
    (target_dir / "tablero_02.jpg").write_bytes(b"img2")
    (target_dir / "notes.txt").write_text("ignore")

    assert downloader.get_next_tablero_index(target_dir) == 3


def test_authorization_whitelist(monkeypatch):
    monkeypatch.setattr(config.Config, "AUTHORIZED_CHAT_IDS", {111222333})
    assert bot.is_authorized(111222333) is True
    assert bot.is_authorized(999888777) is False

    monkeypatch.setattr(config.Config, "AUTHORIZED_CHAT_IDS", set())
    assert bot.is_authorized(111222333) is False


def test_schedule_description(monkeypatch):
    monkeypatch.setattr(config.Config, "ALLOWED_DAY_NUMBERS", {1, 3})
    monkeypatch.setattr(config.Config, "SYNC_HOUR", 21)
    monkeypatch.setattr(config.Config, "SYNC_MINUTE", 0)
    assert config.Config.schedule_description() == "Tuesday and Thursday at 21:00"
