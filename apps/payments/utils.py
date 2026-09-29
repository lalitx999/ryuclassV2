import os
import time
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def save_slip_file(slip_file, user_id):
    """
    Saves an uploaded slip file safely.
    Tries settings.SLIPS_STORAGE_DIR first.
    If writing fails due to an OSError (e.g. read-only filesystem Errno 30 or permission error),
    it automatically falls back to backend/storage/slips/.
    Returns (filename, target_path).
    """
    ext = os.path.splitext(slip_file.name)[1] or '.jpg'
    filename = f"slip_{user_id}_{int(time.time())}{ext}"

    primary_dir = getattr(settings, 'SLIPS_STORAGE_DIR', str(settings.BASE_DIR / 'storage' / 'slips'))
    fallback_dir = str(settings.BASE_DIR / 'storage' / 'slips')

    try:
        os.makedirs(primary_dir, exist_ok=True)
        target_path = os.path.join(primary_dir, filename)
        with open(target_path, 'wb+') as destination:
            for chunk in slip_file.chunks():
                destination.write(chunk)
        logger.info(f"Successfully saved slip {filename} to primary path: {target_path}")
        return filename, target_path
    except OSError as e:
        logger.warning(f"Failed to save slip to primary path {primary_dir} due to OSError: {e}. Falling back to {fallback_dir}")
        os.makedirs(fallback_dir, exist_ok=True)
        target_path = os.path.join(fallback_dir, filename)
        with open(target_path, 'wb+') as destination:
            for chunk in slip_file.chunks():
                destination.write(chunk)
        logger.info(f"Successfully saved slip {filename} to fallback path: {target_path}")
        return filename, target_path
