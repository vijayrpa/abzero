
from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, List, Tuple

import pandas as pd

from brokers.base import Broker
from core.models import Side, Trade, Order
from core.risk import RiskState, should_allow_new_trade, update_daily_loss_flag, compute_position_qty
from core.strategy_camarilla import camarilla_from_prev_day, generate_signal, CamarillaLevels
from core.time_utils import IST, now_ist
from core.instruments import InstrumentCache, select_atm_option_symbol
from config.defaults import AppSettings, Segment

log = logging.getLogger("engine")


@dataclass
class SymbolContext:
    symbol: str
    segment: Segment
    levels: Optional[CamarillaLevels] = None
    day_open: Optional[float] = None
    candles_o: List[float] = None
    candles_h: List[float] = None
    candles_l: List[float] = None
    candles_c: List[float] = None
    candles_v: List[float] = None
    active_trade: Optional[Trade] = None

    def __post_init__(self):
        self.candles_o = self.candles_o or []
        self.candles_h = self.candles_h or []
        self.candles_l = self.candles_l or []
        self.candles_c = self.candles_c or []
        self.candles_v = self.candles_v or []


class AlgoEngine:
    '''
    Event-driven engine:
      - Receives completed 5m candles (from websocket tick aggregator or backtest feed)
      - Computes signals (Advanced Camarilla)
      - Applies risk controls
      - Places/cancels via Broker abstraction
    '''

    def __init__(
        self,
        broker: Broker,
        settings: AppSettings,
        on_status: Optional[Callable[[str], None]] = None,
        on_ltp: Optional[Callable[[str, float], None]] = None,
        on_pnl: Optional[Callable[[float, float], None]] = None,
    ):
        self.broker = broker
        self.settings = settings
        self.on_status = on_status
        self.on_ltp = on_ltp
        self.on_pnl = on_pnl

        self._stop_evt = threading.Event()
        self._lock = threading.RLock()
        self._risk_state = RiskState()
        self._contexts: Dict[str, SymbolContext] = {}
        self._instrument_cache = InstrumentCache()
        self._instruments_df = self._instrument_cache.load()

        self._unrealized = 0.0
        self._realized = 0.0

    def start(self) -> None:
        self._stop_evt.clear()
        self._risk_state.kill_switch = False
        self._risk_state.daily_loss_hit = False
        self._risk_state.trades_today = 0
        self._risk_state.realized_pnl_today = 0.0
        self._unrealized = 0.0
        self._realized = 0.0

        with self._lock:
            self._contexts = {sym: SymbolContext(symbol=sym, segment=self.settings.segment) for sym in self.settings.symbols}

        self._emit_status("ENGINE_STARTED")

    def stop(self) -> None:
        self._stop_evt.set()
        self._emit_status("ENGINE_STOPPING")

    def kill(self) -> None:
        with self._lock:
            self._risk_state.kill_switch = True
        self._emit_status("KILL_SWITCH_ON - Cancelling orders and stopping")
        try:
            self.broker.cancel_all_orders()
        except Exception as e:
            log.warning("Cancel all failed: %s", e)
        self.stop()

    def is_running(self) -> bool:
        return not self._stop_evt.is_set()

    def _emit_status(self, msg: str) -> None:
        log.info(msg)
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    def _emit_ltp(self, symbol: str, ltp: float) -> None:
        if self.on_ltp:
            try:
                self.on_ltp(symbol, ltp)
            except Exception:
                pass

    def _emit_pnl(self) -> None:
        if self.on_pnl:
            try:
                self.on_pnl(self._realized, self._unrealized)
            except Exception:
                pass

    def on_tick(self, symbol: str, ltp: float) -> None:
        self._emit_ltp(symbol, ltp)
        # unrealized PnL update if trade active
        with self._lock:
            ctx = self._contexts.get(symbol)
            if not ctx or not ctx.active_trade or not ctx.active_trade.active:
                return
            t = ctx.active_trade
            if t.side == Side.BUY:
                self._unrealized = (ltp - t.entry_price) * t.qty
            else:
                self._unrealized = (t.entry_price - ltp) * t.qty
        self._emit_pnl()

    def prime_prev_day_levels(self, symbol: str) -> None:
        '''
        Compute Camarilla from previous day OHLC using broker historical candles if available.
        '''
        end = now_ist().date()
        start = end - dt.timedelta(days=7)
        df = self.broker.get_historical_ohlcv(symbol=symbol, segment=self.settings.segment, start=start, end=end, interval_minutes=5)
        if df is None or df.empty:
            raise RuntimeError("Cannot fetch historical candles for levels. Provide instruments/credentials or use backtest/paper.")
        df = df.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        # compute previous trading day from last complete day
        df["date"] = df["timestamp"].dt.date
        last_date = df["date"].max()
        prev_date = sorted([d for d in df["date"].unique() if d < last_date])[-1]
        prev = df[df["date"] == prev_date]
        prev_high = float(prev["high"].max())
        prev_low = float(prev["low"].min())
        prev_close = float(prev.sort_values("timestamp")["close"].iloc[-1])

        levels = camarilla_from_prev_day(prev_high, prev_low, prev_close)

        today = df[df["date"] == last_date].sort_values("timestamp")
        day_open = float(today["open"].iloc[0]) if not today.empty else prev_close

        with self._lock:
            ctx = self._contexts[symbol]
            ctx.levels = levels
            ctx.day_open = day_open

        self._emit_status(f"{symbol}: Levels primed H3={levels.h3:.2f} H4={levels.h4:.2f} L3={levels.l3:.2f} L4={levels.l4:.2f} BiasOpen={day_open:.2f}")

    def on_candle_close(self, symbol: str, candle: Dict[str, float], ts_epoch: float) -> None:
        '''
        Candle dict: open/high/low/close/volume
        '''
        if self._stop_evt.is_set():
            return
        with self._lock:
            ctx = self._contexts.get(symbol)
            if not ctx:
                return
            if ctx.levels is None or ctx.day_open is None:
                # lazy prime; for live this will fetch historical once per symbol
                pass

        if ctx.levels is None or ctx.day_open is None:
            self.prime_prev_day_levels(symbol)

        with self._lock:
            ctx = self._contexts[symbol]
            ctx.candles_o.append(float(candle["open"]))
            ctx.candles_h.append(float(candle["high"]))
            ctx.candles_l.append(float(candle["low"]))
            ctx.candles_c.append(float(candle["close"]))
            ctx.candles_v.append(float(candle.get("volume", 0.0)))

        self._evaluate_and_trade(symbol=symbol, ts_epoch=ts_epoch)
        self._check_exit(symbol=symbol, ltp=float(candle["close"]), ts_epoch=ts_epoch)

    def _evaluate_and_trade(self, symbol: str, ts_epoch: float) -> None:
        with self._lock:
            ctx = self._contexts[symbol]
            # Hard rule: one active trade per symbol
            if self.settings.risk.one_active_trade_per_symbol and ctx.active_trade and ctx.active_trade.active:
                return

            allow, reason = should_allow_new_trade(self.settings.risk, self._risk_state)
            if not allow:
                return

            side, sig_reason = generate_signal(
                levels=ctx.levels,
                settings=self.settings.strategy,
                o=ctx.candles_o,
                h=ctx.candles_h,
                l=ctx.candles_l,
                c=ctx.candles_c,
                v=ctx.candles_v,
                day_open=ctx.day_open,
            )
            if side is None:
                return

            entry = ctx.candles_c[-1]
            # Stop/target: based on Camarilla levels (structured) + a buffer
            if side == Side.BUY:
                stop = min(ctx.levels.l4, ctx.candles_l[-1])  # breakdown invalidation
                target = ctx.levels.h3
            else:
                stop = max(ctx.levels.h4, ctx.candles_h[-1])
                target = ctx.levels.l3

            lot = 1
            order_symbol = symbol
            if self.settings.options.enabled and self.settings.segment == Segment.NSE_FNO:
                # execute on options for F&O indices/stocks (common use)
                opt_sym, lot_sz = select_atm_option_symbol(
                    underlying=symbol,
                    ltp=entry,
                    side=side.value,
                    segment=self.settings.segment,
                    options=self.settings.options,
                    instruments_df=self._instruments_df,
                    asof_date=now_ist().date(),
                )
                order_symbol = opt_sym
                lot = max(1, int(lot_sz))

            qty = compute_position_qty(
                capital=float(self.settings.risk.capital),
                max_risk_pct=float(self.settings.risk.max_risk_per_trade_pct),
                entry=float(entry),
                stop=float(stop),
                lot_size=lot,
            )
            if qty <= 0:
                self._emit_status(f"{symbol}: Signal {sig_reason} but qty=0 (risk sizing).")
                return

            # Place order
            o = Order(
                symbol=order_symbol,
                side=side,
                qty=qty,
                order_type=self.settings.options.order_type if self.settings.options.enabled else "MARKET",
                product=self.settings.options.product if self.settings.options.enabled else "MIS",
                tag="ADV_CAMARILLA",
                meta={"underlying": symbol, "signal": sig_reason},
            )

        # broker call outside lock
        try:
            fill_price = self.broker.place_order(o)
        except Exception as e:
            self._emit_status(f"ORDER_FAILED {symbol}: {e}")
            return

        with self._lock:
            trade = Trade(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=float(fill_price),
                entry_time=float(ts_epoch),
                stop_loss=float(stop),
                target=float(target),
                reason=sig_reason,
                meta={"exec_symbol": o.symbol},
            )
            ctx = self._contexts[symbol]
            ctx.active_trade = trade
            self._risk_state.trades_today += 1
            self._emit_status(f"ENTER {symbol} {side.value} qty={qty} at {fill_price:.2f} SL={stop:.2f} TG={target:.2f} ({sig_reason})")

    def _check_exit(self, symbol: str, ltp: float, ts_epoch: float) -> None:
        with self._lock:
            ctx = self._contexts.get(symbol)
            if not ctx or not ctx.active_trade or not ctx.active_trade.active:
                return
            t = ctx.active_trade
            hit_sl = (ltp <= t.stop_loss) if t.side == Side.BUY else (ltp >= t.stop_loss)
            hit_tg = (ltp >= t.target) if t.side == Side.BUY else (ltp <= t.target)
            if not (hit_sl or hit_tg):
                return
            reason = "STOP_LOSS" if hit_sl else "TARGET"
            exit_price = float(ltp)

        # Try to exit via broker (market)
        try:
            self.broker.exit_position(symbol=t.meta.get("exec_symbol") or symbol, side=t.side, qty=t.qty, product=self.settings.options.product)
        except Exception as e:
            log.warning("Exit order failed (will still mark trade closed): %s", e)

        with self._lock:
            ctx = self._contexts[symbol]
            t = ctx.active_trade
            t.close(price=exit_price, ts=ts_epoch, reason=reason)
            self._realized += t.pnl
            self._risk_state.realized_pnl_today = self._realized
            update_daily_loss_flag(self.settings.risk, self._risk_state)
            self._unrealized = 0.0
            self._emit_status(f"EXIT {symbol} {t.side.value} pnl={t.pnl:.2f} reason={reason} total_realized={self._realized:.2f}")
        self._emit_pnl()

    def get_status_snapshot(self) -> Dict[str, str]:
        with self._lock:
            lines = {}
            for sym, ctx in self._contexts.items():
                if ctx.active_trade and ctx.active_trade.active:
                    t = ctx.active_trade
                    lines[sym] = f"IN_TRADE {t.side.value} qty={t.qty} entry={t.entry_price:.2f} SL={t.stop_loss:.2f} TG={t.target:.2f}"
                else:
                    lines[sym] = "FLAT"
            return lines
