import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import database
from config import Config

logger = logging.getLogger(__name__)

def generate_weekly_pdfs() -> List[Path]:
    """
    Agrupa las fotografías descargadas por semana y genera un archivo PDF para cada semana
    ordenado cronológicamente con formato: Semana_del_YYYY-MM-DD_al_YYYY-MM-DD.pdf
    
    :return: Lista de rutas Path a los archivos PDF generados.
    """
    try:
        import img2pdf
        from PIL import Image
    except ImportError as e:
        logger.error(f"Error al importar librerías de PDF: {e}")
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
        logger.info("No hay fotografías descargadas para generar PDF.")
        return []

    # Agrupar por semana (Lunes a Domingo)
    weekly_groups: Dict[tuple, List[dict]] = {}
    
    for row in rows:
        photo_dict = dict(row)
        local_path = Path(photo_dict["local_path"])
        if not local_path.exists():
            continue

        try:
            msg_dt = datetime.strptime(photo_dict["message_date"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

        # Lunes de esa semana
        monday = msg_dt.date() - timedelta(days=msg_dt.weekday())
        # Domingo de esa semana
        sunday = monday + timedelta(days=6)
        
        week_key = (monday, sunday)
        if week_key not in weekly_groups:
            weekly_groups[week_key] = []
        weekly_groups[week_key].append((msg_dt, local_path))

    pdf_dir = Config.DOWNLOAD_ROOT / "PDFs_Semanales"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    generated_pdfs: List[Path] = []

    for (monday, sunday), items in weekly_groups.items():
        if not items:
            continue
            
        # Ordenar cronológicamente por fecha del mensaje
        items.sort(key=lambda x: x[0])
        
        # Fecha real de inicio y fin de las fotos tomadas esa semana
        first_date = items[0][0].date()
        last_date = items[-1][0].date()
        
        pdf_filename = f"Semana_del_{first_date.strftime('%Y-%m-%d')}_al_{last_date.strftime('%Y-%m-%d')}.pdf"
        pdf_path = pdf_dir / pdf_filename

        image_bytes_list = []
        temp_converted_files = []

        try:
            for _, img_path in items:
                # img2pdf prefiere imágenes JPEG/PNG. Convertimos si es necesario.
                ext = img_path.suffix.lower()
                if ext in [".jpg", ".jpeg", ".png"]:
                    image_bytes_list.append(str(img_path))
                else:
                    # Convertir a JPEG temporal para compatibilidad
                    temp_jpg = img_path.with_suffix(".temp.jpg")
                    with Image.open(img_path) as im:
                        im.convert("RGB").save(temp_jpg, "JPEG")
                    image_bytes_list.append(str(temp_jpg))
                    temp_converted_files.append(temp_jpg)

            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(image_bytes_list))

            logger.info(f"PDF semanal generado: {pdf_filename} ({len(items)} páginas)")
            generated_pdfs.append(pdf_path)

        except Exception as e:
            logger.error(f"Error generando PDF para la semana {first_date} al {last_date}: {e}")
        finally:
            # Limpiar convertidos temporales
            for temp_f in temp_converted_files:
                if temp_f.exists():
                    try:
                        temp_f.unlink()
                    except Exception:
                        pass

    return generated_pdfs
