
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from core.models import Side
from config.defaults import RiskSettings


@dataclass
class RiskState:
    trades_today: int = 0
    realized_pnl_today: float = 0.0
    daily_loss_hit: bool = False
    kill_switch: bool = False


def compute_position_qty(
    *,
    capital: float,
    max_risk_pct: float,
    entry: float,
    stop: float,
    lot_size: int = 1,
) -> int:
    risk_amt = max(0.0, capital * (max_risk_pct / 100.0))
    per_unit_risk = abs(entry - stop)
    if per_unit_risk <= 0:
        return 0
    raw_qty = int(risk_amt // per_unit_risk)
    if raw_qty <= 0:
        return 0
    # Round down to lot size
    qty = (raw_qty // max(1, lot_size)) * max(1, lot_size)
    return max(0, qty)


def should_allow_new_trade(risk: RiskSettings, state: RiskState) -> Tuple[bool, str]:
    if state.kill_switch or risk.kill_switch:
        return False, "KILL_SWITCH"
    if state.trades_today >= risk.max_trades_per_day:
        return False, "MAX_TRADES_PER_DAY"
    if state.daily_loss_hit and not risk.allow_new_trades_after_daily_loss_hit:
        return False, "DAILY_LOSS_LIMIT_HIT"
    return True, ""


def update_daily_loss_flag(risk: RiskSettings, state: RiskState) -> None:
    limit = abs(risk.capital * (risk.daily_loss_limit_pct / 100.0))
    if state.realized_pnl_today <= -limit:
        state.daily_loss_hit = True
