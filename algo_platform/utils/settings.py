from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Settings:
    app_name: str
    timezone: str
    log_level: str
    credentials_file: str
    kdf_iterations: int
    contract_master_dir: str
    trade_logs_dir: str
    paper_fill_slippage_bps: int
    paper_default_qty: int


def load_settings(settings_path: str) -> Settings:
    with open(settings_path, "r", encoding="utf-8") as f:
        raw: Dict[str, Any] = json.load(f)

    def p(rel: str) -> str:
        # Normalize to absolute path from repo root.
        if os.path.isabs(rel):
            return rel
        repo_root = os.path.abspath(os.path.join(os.path.dirname(settings_path), "..", ".."))
        return os.path.join(repo_root, rel)

    return Settings(
        app_name=raw["app"]["name"],
        timezone=raw["app"]["timezone"],
        log_level=raw["app"]["log_level"],
        credentials_file=p(raw["security"]["credentials_file"]),
        kdf_iterations=int(raw["security"]["kdf_iterations"]),
        contract_master_dir=p(raw["data"]["contract_master_dir"]),
        trade_logs_dir=p(raw["data"]["trade_logs_dir"]),
        paper_fill_slippage_bps=int(raw["paper"]["fill_slippage_bps"]),
        paper_default_qty=int(raw["paper"]["default_qty"]),
    )

