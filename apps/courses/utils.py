import os
import time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def save_pdf_file(pdf_file, lesson_id=None):
    """
    Saves an uploaded PDF file safely.
    Tries settings.PDF_STORAGE_DIR (/mnt/hdd_backup/storage/php_app/uploads/protected_pdfs) first.
    If writing fails due to an OSError (e.g. read-only filesystem Errno 30 or permission error),
    it automatically falls back to backend/storage/protected_pdfs/.
    Returns (filename, target_path).
    """
    ext = os.path.splitext(pdf_file.name)[1] or '.pdf'
    identifier = lesson_id if lesson_id else int(time.time())
    filename = f"pdf_lesson_{identifier}_{int(time.time())}{ext}"

    primary_dir = getattr(settings, 'PDF_STORAGE_DIR', str(settings.BASE_DIR / 'storage' / 'protected_pdfs'))
    fallback_dir = str(settings.BASE_DIR / 'storage' / 'protected_pdfs')

    try:
        os.makedirs(primary_dir, exist_ok=True)
        target_path = os.path.join(primary_dir, filename)
        with open(target_path, 'wb+') as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)
        logger.info(f"Successfully saved PDF {filename} to primary path: {target_path}")
        return filename, target_path
    except OSError as e:
        logger.warning(f"Failed to save PDF to primary path {primary_dir} due to OSError: {e}. Falling back to {fallback_dir}")
        os.makedirs(fallback_dir, exist_ok=True)
        target_path = os.path.join(fallback_dir, filename)
        with open(target_path, 'wb+') as destination:
            for chunk in pdf_file.chunks():
                destination.write(chunk)
        logger.info(f"Successfully saved PDF {filename} to fallback path: {target_path}")
        return filename, target_path
