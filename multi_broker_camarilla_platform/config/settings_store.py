
from __future__ import annotations

import json
from typing import Any, Dict

from config.defaults import AppSettings
from config.paths import settings_path


def load_settings() -> AppSettings:
    p = settings_path()
    if not p.exists():
        return AppSettings.default()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return AppSettings.from_dict(d)
    except Exception:
        return AppSettings.default()


def save_settings(settings: AppSettings) -> None:
    p = settings_path()
    p.write_text(json.dumps(settings.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
