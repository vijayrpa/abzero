
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from config.paths import logs_dir


def configure_logging(level: int = logging.INFO) -> None:
    log_dir = logs_dir()
    log_path = log_dir / "platform.log"

    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(fmt)

    fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)

    root.addHandler(sh)
    root.addHandler(fh)
