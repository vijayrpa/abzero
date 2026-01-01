from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from algo_platform.models import SymbolKey

log = logging.getLogger(__name__)


@dataclass
class ContractInfo:
    lot_size: int


class ContractMaster:
    """
    Loads lot sizes from downloaded contract masters.

    Supported sources (best-effort):
    - Zerodha instruments CSV: `zerodha_instruments_YYYY-MM-DD.csv`
    - Shoonya scrip master TXT: `shoonya_EXCH_YYYY-MM-DD_*.txt` (pipe-separated)
    """

    def __init__(self, contract_master_dir: str) -> None:
        self._dir = contract_master_dir
        self._cache: Dict[str, ContractInfo] = {}
        self._loaded = False

    def _latest_file(self, prefix: str, suffix: str) -> Optional[str]:
        if not os.path.isdir(self._dir):
            return None
        best = None
        best_m = -1.0
        for name in os.listdir(self._dir):
            if not (name.startswith(prefix) and name.endswith(suffix)):
                continue
            fp = os.path.join(self._dir, name)
            try:
                m = os.path.getmtime(fp)
            except Exception:
                continue
            if m > best_m:
                best_m = m
                best = fp
        return best

    def refresh(self) -> None:
        self._cache.clear()
        self._loaded = False
        self._load_all()

    def _load_all(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._load_zerodha()
        self._load_shoonya()

    def get_lot_size(self, symbol: SymbolKey) -> Optional[int]:
        self._load_all()
        info = self._cache.get(symbol.key())
        return info.lot_size if info else None

    def _load_zerodha(self) -> None:
        fp = self._latest_file("zerodha_instruments_", ".csv")
        if not fp:
            return
        try:
            with open(fp, "r", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    exch = (row.get("exchange") or "").strip()
                    tsym = (row.get("tradingsymbol") or "").strip()
                    seg = (row.get("segment") or "").strip()
                    lot = row.get("lot_size")
                    if not (exch and tsym and lot):
                        continue
                    try:
                        lot_i = int(float(lot))
                    except Exception:
                        continue
                    if lot_i <= 0:
                        continue
                    # Normalize segment to our internal.
                    if "NFO" in seg:
                        segment = "NFO"
                    elif "MCX" in seg:
                        segment = "MCX"
                    elif "CDS" in seg:
                        segment = "CDS"
                    else:
                        segment = "CASH"
                    sk = SymbolKey(exchange=exch, segment=segment, tradingsymbol=tsym)
                    self._cache[sk.key()] = ContractInfo(lot_size=lot_i)
        except Exception:
            log.exception("Failed to load Zerodha contract master: %s", fp)

    def _load_shoonya(self) -> None:
        if not os.path.isdir(self._dir):
            return
        # Load all shoonya txt masters in dir.
        for name in os.listdir(self._dir):
            if not (name.startswith("shoonya_") and name.endswith(".txt")):
                continue
            fp = os.path.join(self._dir, name)
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    header = f.readline().strip().split("|")
                    idx = {h.strip(): i for i, h in enumerate(header)}

                    def get(cols, key, default=""):
                        i = idx.get(key)
                        return cols[i].strip() if i is not None and i < len(cols) else default

                    for line in f:
                        cols = line.strip().split("|")
                        exch = get(cols, "Exchange") or get(cols, "Exch") or ""
                        tsym = get(cols, "TradingSymbol") or get(cols, "TSym") or get(cols, "Tsym") or ""
                        lot = get(cols, "LotSize") or get(cols, "Lot") or ""
                        if not (exch and tsym and lot):
                            continue
                        try:
                            lot_i = int(float(lot))
                        except Exception:
                            continue
                        if lot_i <= 0:
                            continue
                        segment = "CASH" if exch in ("NSE", "BSE") else exch
                        sk = SymbolKey(exchange=exch, segment=segment, tradingsymbol=tsym)
                        self._cache.setdefault(sk.key(), ContractInfo(lot_size=lot_i))
            except Exception:
                log.exception("Failed to load Shoonya contract master: %s", fp)

