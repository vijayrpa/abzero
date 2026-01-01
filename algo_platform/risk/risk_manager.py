from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from algo_platform.models import SymbolKey


@dataclass
class RiskDecision:
    should_stop: bool
    reason: str


class RiskManager:
    """
    Per-symbol daily profit/loss limits.
    Decision is based on (realized + unrealized) PnL provided by the caller.
    """

    def __init__(self) -> None:
        self._stopped: Dict[str, str] = {}

    def is_stopped(self, symbol: SymbolKey) -> bool:
        return symbol.key() in self._stopped

    def stop(self, symbol: SymbolKey, reason: str) -> None:
        self._stopped[symbol.key()] = reason

    def clear(self, symbol: SymbolKey) -> None:
        self._stopped.pop(symbol.key(), None)

    def evaluate(
        self,
        *,
        symbol: SymbolKey,
        risk_on: bool,
        daily_loss_limit: float,
        daily_profit_limit: float,
        pnl_total: float,
    ) -> RiskDecision:
        if not risk_on:
            return RiskDecision(should_stop=False, reason="")
        if self.is_stopped(symbol):
            return RiskDecision(should_stop=True, reason=self._stopped[symbol.key()])
        if daily_loss_limit > 0 and pnl_total <= -abs(daily_loss_limit):
            reason = f"Daily loss limit hit: {pnl_total:.2f} <= {-abs(daily_loss_limit):.2f}"
            self.stop(symbol, reason)
            return RiskDecision(should_stop=True, reason=reason)
        if daily_profit_limit > 0 and pnl_total >= abs(daily_profit_limit):
            reason = f"Daily profit limit hit: {pnl_total:.2f} >= {abs(daily_profit_limit):.2f}"
            self.stop(symbol, reason)
            return RiskDecision(should_stop=True, reason=reason)
        return RiskDecision(should_stop=False, reason="")

