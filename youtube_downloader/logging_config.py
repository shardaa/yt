"""Structured logging configuration for the YouTube video downloader."""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILENAME = "youtube_downloader.log"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3


def setup_logging(output_dir: str) -> None:
    """Configure logging with console (INFO+) and rotating file (DEBUG+) handlers.

    Args:
        output_dir: Directory where the log file will be created.
    """
    os.makedirs(output_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers on repeated calls
    root_logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT)

    # Console handler — INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler — DEBUG and above
    log_path = os.path.join(output_dir, LOG_FILENAME)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
