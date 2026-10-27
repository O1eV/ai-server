from __future__ import annotations

import logging
import sys

from app.core.config import get_settings

LOGGER_NAME = "laya_api"

logger = logging.getLogger(LOGGER_NAME)

_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging() -> None:
    level = getattr(logging, get_settings().log_level, logging.INFO)

    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)

    logging.getLogger("laya").setLevel(max(level, logging.WARNING))
