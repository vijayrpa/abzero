
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from backtest.metrics import BacktestReport, compute_drawdown
from config.defaults import AppSettings, Segment
from core.strategy_camarilla import camarilla_from_prev_day, generate_signal
from core.models import Side, Trade
from core.risk import compute_position_qty

log = logging.getLogger("backtest")


def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    need = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing columns: {missing}. Required: {need}")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    return df


def run_csv_backtest(csv_path: Path, symbol: str, segment: Segment, settings: AppSettings) -> BacktestReport:
    df = pd.read_csv(csv_path)
    df = _ensure_cols(df)
    df["date"] = df["timestamp"].dt.date

    trades: List[Trade] = []
    equity = [0.0]
    realized = 0.0
    active: Optional[Trade] = None

    # Rolling arrays for indicators
    o: List[float] = []
    h: List[float] = []
    l: List[float] = []
    c: List[float] = []
    v: List[float] = []

    for day in sorted(df["date"].unique()):
        day_df = df[df["date"] == day].copy()
        prev_days = sorted([d for d in df["date"].unique() if d < day])
        if not prev_days:
            continue
        prev_day = prev_days[-1]
        prev_df = df[df["date"] == prev_day]
        prev_high = float(prev_df["high"].max())
        prev_low = float(prev_df["low"].min())
        prev_close = float(prev_df.sort_values("timestamp")["close"].iloc[-1])
        levels = camarilla_from_prev_day(prev_high, prev_low, prev_close)
        day_open = float(day_df.sort_values("timestamp")["open"].iloc[0])

        # reset candle series each day (cleaner, strategy is day-based with prev OHLC)
        o.clear(); h.clear(); l.clear(); c.clear(); v.clear()

        for _, row in day_df.iterrows():
            o.append(float(row["open"]))
            h.append(float(row["high"]))
            l.append(float(row["low"]))
            c.append(float(row["close"]))
            v.append(float(row["volume"]))
            ts_epoch = float(pd.Timestamp(row["timestamp"]).timestamp())

            # exit checks first (intrabar candle close assumption)
            if active and active.active:
                ltp = float(row["close"])
                hit_sl = (ltp <= active.stop_loss) if active.side == Side.BUY else (ltp >= active.stop_loss)
                hit_tg = (ltp >= active.target) if active.side == Side.BUY else (ltp <= active.target)
                if hit_sl or hit_tg:
                    active.close(price=ltp, ts=ts_epoch, reason="STOP_LOSS" if hit_sl else "TARGET")
                    realized += active.pnl
                    trades.append(active)
                    active = None
                    equity.append(realized)
                    continue

            if active and active.active:
                # one active trade per symbol
                equity.append(realized)
                continue

            side, reason = generate_signal(
                levels=levels,
                settings=settings.strategy,
                o=o, h=h, l=l, c=c, v=v,
                day_open=day_open,
            )
            if side is None:
                equity.append(realized)
                continue

            entry = float(row["close"])
            if side == Side.BUY:
                stop = min(levels.l4, float(row["low"]))
                target = float(levels.h3)
            else:
                stop = max(levels.h4, float(row["high"]))
                target = float(levels.l3)

            qty = compute_position_qty(
                capital=float(settings.risk.capital),
                max_risk_pct=float(settings.risk.max_risk_per_trade_pct),
                entry=entry,
                stop=stop,
                lot_size=1,
            )
            if qty <= 0:
                equity.append(realized)
                continue

            active = Trade(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=entry,
                entry_time=ts_epoch,
                stop_loss=stop,
                target=target,
                reason=reason,
            )
            equity.append(realized)

    if active and active.active:
        # close last trade at last close
        last_close = float(df["close"].iloc[-1])
        ts = float(pd.Timestamp(df["timestamp"].iloc[-1]).timestamp())
        active.close(price=last_close, ts=ts, reason="EOD_FORCE_EXIT")
        realized += active.pnl
        trades.append(active)
        equity.append(realized)

    trade_count = len(trades)
    wins = sum(1 for t in trades if t.pnl > 0)
    win_rate = (wins / trade_count * 100.0) if trade_count else 0.0
    max_dd = compute_drawdown(equity)
    return BacktestReport(net_pnl=realized, win_rate=win_rate, max_drawdown=max_dd, trade_count=trade_count, equity_curve=equity)
