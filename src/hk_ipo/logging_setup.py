"""Centralised logging setup for hk_ipo pipeline.

Provides a ``get_logger(name)`` factory that configures both a
RotatingFileHandler (``data/logs/app.log``) and a StreamHandler (stderr).
Default level ``INFO``; override with the ``HK_IPO_LOG_LEVEL`` env var.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path("data/logs")
_LOG_FILE = _LOG_DIR / "app.log"

_initialized = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger for *name*, configuring handlers once on first call.

    File handler writes everything DEBUG and above to ``data/logs/app.log``
    with rotation (5 MiB per file, 3 backups).  Stream handler writes to
    stderr at the level given by ``HK_IPO_LOG_LEVEL`` (default ``INFO``).
    """
    global _initialized
    if not _initialized:
        _initialized = True
        level_name = os.environ.get("HK_IPO_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        # RotatingFileHandler: 5 MiB max, keep 3 backups
        file_handler = RotatingFileHandler(
            str(_LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
        )

        # StreamHandler to stderr so logs never pollute stdout
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )

        logging.basicConfig(level=level, handlers=[file_handler, stream_handler])

    return logging.getLogger(name)
