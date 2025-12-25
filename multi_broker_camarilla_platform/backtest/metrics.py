
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BacktestReport:
    net_pnl: float
    win_rate: float
    max_drawdown: float
    trade_count: int
    equity_curve: List[float]

    def to_text(self) -> str:
        return (
            f"Net P&L: {self.net_pnl:.2f}\n"
            f"Win rate: {self.win_rate:.2f}%\n"
            f"Max drawdown: {self.max_drawdown:.2f}\n"
            f"Trades: {self.trade_count}\n"
        )


def compute_drawdown(equity: List[float]) -> float:
    peak = float("-inf")
    max_dd = 0.0
    for x in equity:
        peak = max(peak, x)
        dd = peak - x
        max_dd = max(max_dd, dd)
    return float(max_dd)
