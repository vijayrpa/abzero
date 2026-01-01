from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional

from algo_platform.execution.order_manager import OrderManager
from algo_platform.models import (
    ActiveTrade,
    PerSymbolConfig,
    Side,
    StrategyRow,
    SymbolKey,
)
from algo_platform.risk.risk_manager import RiskManager
from algo_platform.utils.quantity_validator import QuantityValidator
from algo_platform.websocket.tick_engine import TickEngine

log = logging.getLogger(__name__)


class StrategyEngine:
    """
    Runs strategies for all rows.
    - One active trade per symbol row (sequential re-entries supported via max counts)
    - Trailing SL behaves like real trading
    - Risk limits can stop per-symbol strategy and optionally force-exit
    """

    def __init__(
        self,
        tick_engine: TickEngine,
        order_manager: OrderManager,
        risk: RiskManager,
        qty_validator: Optional[QuantityValidator] = None,
    ) -> None:
        self._tick_engine = tick_engine
        self._om = order_manager
        self._risk = risk
        self._qty_validator = qty_validator
        self._rows: Dict[str, StrategyRow] = {}
        self._lock = threading.RLock()

        self._tick_engine.add_listener(self.on_tick)

    def upsert_row(self, row: StrategyRow) -> None:
        with self._lock:
            self._rows[row.symbol.key() + "|" + row.strategy_type.value] = row

    def remove_row(self, row: StrategyRow) -> None:
        with self._lock:
            self._rows.pop(row.symbol.key() + "|" + row.strategy_type.value, None)

    def list_rows(self) -> List[StrategyRow]:
        with self._lock:
            return list(self._rows.values())

    def set_row_config(self, row_key: str, cfg: PerSymbolConfig) -> None:
        with self._lock:
            self._rows[row_key].config = cfg

    def set_running(self, row_key: str, running: bool) -> None:
        with self._lock:
            r = self._rows[row_key]
            r.state.running = running
            r.state.status = "Running" if running else "Stopped"
            r.state.last_status_msg = ""
            if running:
                self._risk.clear(r.symbol)

    def restart(self, row_key: str) -> None:
        with self._lock:
            r = self._rows[row_key]
            r.state.buy_trades_done = 0
            r.state.sell_trades_done = 0
            r.state.buy_armed = True
            r.state.sell_armed = True
            r.active_trade = None
            self._risk.clear(r.symbol)
            r.state.running = True
            r.state.status = "Running"
            r.state.last_status_msg = "Restarted"

    def manual_exit(self, row_key: str, ltp: float, reason: str = "Manual") -> None:
        with self._lock:
            r = self._rows[row_key]
            if not r.active_trade or r.active_trade.closed:
                return
            tr = r.active_trade
            res = self._om.exit_trade(
                trade_mode=r.config.trade_mode,
                strategy_type=r.strategy_type.value,
                symbol=r.symbol,
                side=tr.side,
                qty=tr.qty,
                ltp=ltp,
                reason=reason,
            )
            if res.ok:
                tr.closed = True
                tr.exit_price = res.fill_price or ltp
                tr.exit_time = datetime.utcnow()
                tr.exit_reason = reason
                r.active_trade = None

    def on_tick(self, tick) -> None:
        # Called from tick engine thread. Keep it quick.
        rows = self.list_rows()
        for r in rows:
            if r.symbol.key() != tick.symbol.key():
                continue
            self._process_row_tick(r, tick.ltp)

    def _process_row_tick(self, row: StrategyRow, ltp: float) -> None:
        row_key = row.symbol.key() + "|" + row.strategy_type.value
        with self._lock:
            r = self._rows.get(row_key)
            if not r:
                return

            # Risk evaluation
            pnl_total = self._om.get_pnl(r.symbol, ltp, r.config.trade_mode)
            rd = self._risk.evaluate(
                symbol=r.symbol,
                risk_on=r.config.risk_on,
                daily_loss_limit=r.config.daily_loss_limit,
                daily_profit_limit=r.config.daily_profit_limit,
                pnl_total=pnl_total,
            )
            if rd.should_stop:
                if r.active_trade:
                    self.manual_exit(row_key, ltp, reason="RiskLimit")
                r.state.running = False
                r.state.status = "Stopped"
                r.state.last_status_msg = rd.reason
                return

            if not r.config.strategy_on or not r.state.running:
                return

            # Rearm logic to avoid duplicate trades at same level.
            if not r.state.buy_armed and ltp < r.levels.buy_level:
                r.state.buy_armed = True
            if not r.state.sell_armed and ltp > r.levels.sell_level:
                r.state.sell_armed = True

            # Manage active trade exits / trailing
            if r.active_trade:
                self._update_trailing_and_exit(r, ltp)
                return

            # Entry checks (no trade open)
            et = r.config.entry_type.value
            if et in ("Buy", "Both") and r.state.buy_trades_done < r.config.max_buy_trades:
                if r.state.buy_armed and ltp >= r.levels.buy_level:
                    if self._enter(r, Side.BUY, ltp):
                        r.state.buy_trades_done += 1
                        r.state.buy_armed = False
                    return
            if et in ("Sell", "Both") and r.state.sell_trades_done < r.config.max_sell_trades:
                if r.state.sell_armed and ltp <= r.levels.sell_level:
                    if self._enter(r, Side.SELL, ltp):
                        r.state.sell_trades_done += 1
                        r.state.sell_armed = False
                    return

    def _enter(self, r: StrategyRow, side: Side, ltp: float) -> bool:
        if self._qty_validator:
            vd = self._qty_validator.validate(r.symbol, int(r.config.qty))
            if not vd.ok:
                r.state.last_status_msg = vd.message
                return False
            if vd.message:
                r.state.last_status_msg = vd.message
        if side == Side.BUY:
            sl = r.levels.buy_sl
            t1 = r.levels.buy_t1
            t2 = r.levels.buy_t2
        else:
            sl = r.levels.sell_sl
            t1 = r.levels.sell_t1
            t2 = r.levels.sell_t2
        res = self._om.enter_trade(
            trade_mode=r.config.trade_mode,
            strategy_type=r.strategy_type.value,
            symbol=r.symbol,
            side=side,
            qty=r.config.qty,
            ltp=ltp,
        )
        if not res.ok:
            r.state.last_status_msg = res.message
            return False
        entry_px = res.fill_price or ltp
        r.active_trade = ActiveTrade(
            symbol=r.symbol,
            side=side,
            entry_price=entry_px,
            qty=r.config.qty,
            sl=float(sl),
            initial_sl=float(sl),
            t1=float(t1),
            t2=float(t2),
            trailing_on=bool(r.config.trailing_on),
            trail_value=float(r.config.trail_value or 0.0),
            best_price=entry_px,
            open_time=datetime.utcnow(),
        )
        r.state.status = "Running"
        r.state.last_status_msg = f"Entered {side.value} @ {entry_px:.2f}"
        return True

    def _update_trailing_and_exit(self, r: StrategyRow, ltp: float) -> None:
        tr = r.active_trade
        if not tr:
            return

        # Update best price
        if tr.side == Side.BUY:
            tr.best_price = max(tr.best_price, ltp)
        else:
            tr.best_price = min(tr.best_price, ltp)

        # Trailing stop logic (step-based, exactly like example)
        if tr.trailing_on and tr.trail_value > 0:
            if tr.side == Side.BUY:
                steps = int((tr.best_price - tr.entry_price) // tr.trail_value)
                new_sl = max(tr.sl, (tr.initial_sl + steps * tr.trail_value))
                tr.sl = float(new_sl)
            else:
                steps = int((tr.entry_price - tr.best_price) // tr.trail_value)
                new_sl = min(tr.sl, (tr.initial_sl - steps * tr.trail_value))
                tr.sl = float(new_sl)

        # Exit checks
        if tr.side == Side.BUY:
            if ltp <= tr.sl:
                self._exit(r, ltp, reason="SL")
                return
            if r.config.exit_at_t1 and ltp >= tr.t1:
                self._exit(r, ltp, reason="T1")
                return
            if r.config.exit_at_t2 and ltp >= tr.t2:
                self._exit(r, ltp, reason="T2")
                return
        else:
            if ltp >= tr.sl:
                self._exit(r, ltp, reason="SL")
                return
            if r.config.exit_at_t1 and ltp <= tr.t1:
                self._exit(r, ltp, reason="T1")
                return
            if r.config.exit_at_t2 and ltp <= tr.t2:
                self._exit(r, ltp, reason="T2")
                return

    def _exit(self, r: StrategyRow, ltp: float, reason: str) -> None:
        tr = r.active_trade
        if not tr:
            return
        res = self._om.exit_trade(
            trade_mode=r.config.trade_mode,
            strategy_type=r.strategy_type.value,
            symbol=r.symbol,
            side=tr.side,
            qty=tr.qty,
            ltp=ltp,
            reason=reason,
        )
        if not res.ok:
            r.state.last_status_msg = res.message
            return
        tr.closed = True
        tr.exit_price = res.fill_price or ltp
        tr.exit_time = datetime.utcnow()
        tr.exit_reason = reason
        r.active_trade = None
        r.state.last_status_msg = f"Exit {reason} @ {tr.exit_price:.2f}"

