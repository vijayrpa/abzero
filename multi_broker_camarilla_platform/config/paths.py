
from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    p = project_root() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    p = project_root() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_dir() -> Path:
    p = project_root() / "config"
    p.mkdir(parents=True, exist_ok=True)
    return p


def vault_path() -> Path:
    return config_dir() / "vault.enc"


def settings_path() -> Path:
    return config_dir() / "app_settings.json"
