from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str, level: str = "INFO") -> None:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Avoid duplicate handlers on re-entry.
    if any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        return

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"), maxBytes=2_000_000, backupCount=5
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logger.level)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    stream.setLevel(logger.level)

    logger.addHandler(file_handler)
    logger.addHandler(stream)

