import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import database
from config import Config

logger = logging.getLogger(__name__)


def generate_weekly_pdfs() -> List[Path]:
    """
    Group downloaded photos by ISO week (Monday to Sunday) and compile a chronological
    PDF file for each week.

    :return: List of Path objects pointing to the generated PDF files.
    """
    try:
        import img2pdf
        from PIL import Image
    except ImportError as e:
        logger.error(f"Failed to import PDF generation libraries: {e}")
        return []

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM photos
        WHERE status = 'downloaded' AND local_path IS NOT NULL
        ORDER BY message_date ASC
    """)
    rows = cursor.fetchall()

    if not rows:
        logger.info("No downloaded photos available for PDF generation.")
        return []

    # Group photos by week (Monday through Sunday)
    weekly_groups: Dict[tuple, List[tuple]] = {}

    for row in rows:
        photo_dict = dict(row)
        local_path = Path(photo_dict["local_path"])
        if not local_path.exists():
            continue

        try:
            msg_dt = datetime.strptime(photo_dict["message_date"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

        monday = msg_dt.date() - timedelta(days=msg_dt.weekday())
        sunday = monday + timedelta(days=6)

        week_key = (monday, sunday)
        if week_key not in weekly_groups:
            weekly_groups[week_key] = []
        weekly_groups[week_key].append((msg_dt, local_path))

    pdf_dir = Config.DOWNLOAD_ROOT / "Weekly_PDFs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    generated_pdfs: List[Path] = []

    for (monday, sunday), items in weekly_groups.items():
        if not items:
            continue

        items.sort(key=lambda x: x[0])

        first_date = items[0][0].date()
        last_date = items[-1][0].date()

        pdf_filename = f"Week_{first_date.strftime('%Y-%m-%d')}_to_{last_date.strftime('%Y-%m-%d')}.pdf"
        pdf_path = pdf_dir / pdf_filename

        image_bytes_list = []
        temp_converted_files = []

        try:
            for _, img_path in items:
                ext = img_path.suffix.lower()
                if ext in [".jpg", ".jpeg", ".png"]:
                    image_bytes_list.append(str(img_path))
                else:
                    temp_jpg = img_path.with_suffix(".temp.jpg")
                    with Image.open(img_path) as im:
                        im.convert("RGB").save(temp_jpg, "JPEG")
                    image_bytes_list.append(str(temp_jpg))
                    temp_converted_files.append(temp_jpg)

            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(image_bytes_list))

            logger.info(f"Weekly PDF generated: {pdf_filename} ({len(items)} pages)")
            generated_pdfs.append(pdf_path)

        except Exception as e:
            logger.error(f"Error generating PDF for week {first_date} to {last_date}: {e}")
        finally:
            for temp_f in temp_converted_files:
                if temp_f.exists():
                    try:
                        temp_f.unlink()
                    except Exception:
                        pass

    return generated_pdfs
