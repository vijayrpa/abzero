from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from algo_platform.models import EntryType, PerSymbolConfig, StrategyLevels, StrategyRow, StrategyType, SymbolKey


REQUIRED_COLUMNS = [
    "Symbol",
    "Buy Level",
    "Buy T1",
    "Buy T2",
    "Buy SL",
    "Sell Level",
    "Sell T1",
    "Sell T2",
    "Sell SL",
    "Quantity",
]


@dataclass(frozen=True)
class ExcelLoadResult:
    rows: List[StrategyRow]


def load_manual_strategy_excel(path: str, default_exchange: str = "NSE", default_segment: str = "CASH") -> ExcelLoadResult:
    df = pd.read_excel(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Excel missing columns: {missing}. Required: {REQUIRED_COLUMNS}")

    rows: List[StrategyRow] = []
    for i, r in df.iterrows():
        sym = str(r["Symbol"]).strip()
        if not sym or sym.lower() == "nan":
            continue

        def f(x) -> float:
            try:
                return float(x)
            except Exception:
                raise ValueError(f"Row {i+2}: invalid numeric value {x!r}")

        qty = int(r["Quantity"])
        if qty <= 0:
            raise ValueError(f"Row {i+2}: Quantity must be > 0")

        levels = StrategyLevels(
            buy_level=f(r["Buy Level"]),
            buy_t1=f(r["Buy T1"]),
            buy_t2=f(r["Buy T2"]),
            buy_sl=f(r["Buy SL"]),
            sell_level=f(r["Sell Level"]),
            sell_t1=f(r["Sell T1"]),
            sell_t2=f(r["Sell T2"]),
            sell_sl=f(r["Sell SL"]),
        )
        internal = SymbolKey(exchange=default_exchange, segment=default_segment, tradingsymbol=sym)
        cfg = PerSymbolConfig(qty=qty, entry_type=EntryType.BOTH)
        rows.append(
            StrategyRow(
                symbol=internal,
                strategy_type=StrategyType.MANUAL,
                levels=levels,
                config=cfg,
            )
        )

    if not rows:
        raise ValueError("Excel contains no valid rows.")
    return ExcelLoadResult(rows=rows)

