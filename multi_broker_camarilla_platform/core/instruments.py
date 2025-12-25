
from __future__ import annotations

import csv
import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from config.paths import data_dir
from config.defaults import Segment, OptionsSettings
from core.time_utils import next_weekly_expiry

log = logging.getLogger("instruments")


@dataclass
class Instrument:
    exchange: str
    tradingsymbol: str
    token: str
    name: str = ""
    segment: str = ""
    instrument_type: str = ""
    expiry: Optional[dt.date] = None
    strike: Optional[float] = None
    lot_size: int = 1


class InstrumentCache:
    '''
    Local instrument cache. For live trading, users should refresh these from their broker.
    The platform can operate without full masters in PAPER/backtest mode.
    '''

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (data_dir() / "instruments_master.csv")

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> pd.DataFrame:
        if not self.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(self.path)
            return df
        except Exception as e:
            log.warning("Failed to load instruments master: %s", e)
            return pd.DataFrame()

    def save(self, df: pd.DataFrame) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.path, index=False)


def round_to_step(price: float, step: int) -> int:
    if step <= 0:
        return int(round(price))
    return int(round(price / step) * step)


def select_atm_option_symbol(
    *,
    underlying: str,
    ltp: float,
    side: str,
    segment: Segment,
    options: OptionsSettings,
    instruments_df: Optional[pd.DataFrame] = None,
    asof_date: Optional[dt.date] = None,
) -> Tuple[str, int]:
    '''
    Returns (tradingsymbol, lot_size). Uses local master if available, otherwise builds a common NFO-style symbol.
    - CE for BUY signals
    - PE for SELL signals
    '''
    side = side.upper()
    is_call = side == "BUY"
    opt_type = "CE" if is_call else "PE"
    asof = asof_date or dt.date.today()

    expiry = next_weekly_expiry(asof, weekday=3)  # Thursday
    step = int(options.index_strike_steps.get(underlying.upper(), 50))
    strike = round_to_step(ltp, step)

    # If we have instruments master, choose the closest match.
    if instruments_df is not None and not instruments_df.empty:
        df = instruments_df.copy()
        # Normalize columns if present
        cols = {c.lower(): c for c in df.columns}
        sym_col = cols.get("tradingsymbol") or cols.get("symbol") or cols.get("trading_symbol")
        name_col = cols.get("name") or cols.get("underlying")
        exp_col = cols.get("expiry") or cols.get("expiry_date")
        strike_col = cols.get("strike") or cols.get("strike_price")
        type_col = cols.get("instrument_type") or cols.get("option_type")
        lot_col = cols.get("lot_size") or cols.get("lotsize") or cols.get("lot")

        if sym_col and name_col and exp_col and strike_col and type_col:
            try:
                df["_exp"] = pd.to_datetime(df[exp_col], errors="coerce").dt.date
                df["_strike"] = pd.to_numeric(df[strike_col], errors="coerce")
                df["_type"] = df[type_col].astype(str).str.upper()
                df["_name"] = df[name_col].astype(str).str.upper()
                cand = df[
                    (df["_name"] == underlying.upper())
                    & (df["_exp"] == expiry)
                    & (df["_type"] == opt_type)
                ].copy()
                if not cand.empty:
                    cand["_dist"] = (cand["_strike"] - strike).abs()
                    cand = cand.sort_values(["_dist"])
                    row = cand.iloc[0]
                    lot = int(row[lot_col]) if lot_col and str(row.get(lot_col, "")).strip() != "" else 1
                    return str(row[sym_col]), lot
            except Exception:
                pass

    # Fallback: best-effort common format (varies by broker). Broker adapters may transform further.
    # Example style: NIFTY 25DEC 20000 CE -> often broker-specific. We'll use YYMMDD in symbol as neutral.
    exp_tag = expiry.strftime("%y%m%d")
    tradingsymbol = f"{underlying.upper()}{exp_tag}{strike}{opt_type}"
    return tradingsymbol, 1
