
from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.paper")


class PaperBroker(Broker):
    name = "PAPER"

    def __init__(self):
        self._logged_in = True
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._subs: set[str] = set()
        self._ltp: Dict[str, float] = {}
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return True

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        self._on_tick = on_tick

    def subscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.add(symbol)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.discard(symbol)

    def disconnect_marketdata(self) -> None:
        self._on_tick = None

    def set_ltp(self, symbol: str, ltp: float) -> None:
        with self._lock:
            self._ltp[symbol] = float(ltp)
            cb = self._on_tick
        if cb and symbol in self._subs:
            cb(symbol, float(ltp), {"mode": "PAPER"})

    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        # Paper broker doesn't provide market history; use CSV backtest for history.
        return pd.DataFrame()

    def place_order(self, order: Order) -> float:
        # Fill at last known LTP; if absent, use 0 and still be consistent.
        with self._lock:
            px = float(self._ltp.get(order.symbol) or self._ltp.get(order.meta.get("underlying", "")) or 0.0)
        order.broker_order_id = f"PAPER-{int(time.time()*1000)}"
        return px

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        return

    def cancel_all_orders(self) -> None:
        return
