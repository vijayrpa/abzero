
from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.aliceblue")


class AliceBlueBroker(Broker):
    name = "ALICEBLUE"

    def __init__(self):
        self._api = None
        self._logged_in = False
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._subs: set[str] = set()
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        try:
            from pya3 import Aliceblue
        except Exception as e:
            raise RuntimeError("pya3 not installed. Install requirements and retry.") from e
        user_id = creds.get("user_id") or creds.get("USER_ID")
        api_key = creds.get("api_key") or creds.get("API_KEY")
        if not user_id or not api_key:
            raise ValueError("AliceBlue requires user_id and api_key in vault.")
        api = Aliceblue(user_id=str(user_id), api_key=str(api_key))
        self._api = api
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return bool(self._logged_in)

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        if not self._api:
            raise RuntimeError("Not logged in.")
        self._on_tick = on_tick
        # AliceBlue websocket is supported via start_websocket in pya3
        def socket_open():
            log.info("AliceBlue websocket opened")

        def socket_close():
            log.warning("AliceBlue websocket closed")

        def socket_error(msg):
            log.warning("AliceBlue websocket error: %s", msg)

        def feed_data(message):
            try:
                sym = message.get("tk") or message.get("ts") or ""
                ltp = float(message.get("lp") or 0.0)
                if sym and self._on_tick:
                    self._on_tick(sym, ltp, message)
            except Exception:
                pass

        try:
            self._api.start_websocket(
                socket_open_callback=socket_open,
                socket_close_callback=socket_close,
                socket_error_callback=socket_error,
                subscription_callback=feed_data,
                run_in_background=True,
            )
        except Exception as e:
            raise RuntimeError(f"AliceBlue websocket start failed: {e}") from e

    def subscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.add(symbol)
        # Subscription in AliceBlue typically needs contract objects; keep executable with best-effort
        try:
            self._api.subscribe([symbol])
        except Exception as e:
            log.warning("AliceBlue subscribe failed for %s (needs contract mapping): %s", symbol, e)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.discard(symbol)
        try:
            self._api.unsubscribe([symbol])
        except Exception:
            pass

    def disconnect_marketdata(self) -> None:
        try:
            if self._api:
                self._api.stop_websocket()
        except Exception:
            pass

    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        raise RuntimeError("AliceBlue historical OHLCV requires instrument mapping specific to your account/contracts.")

    def place_order(self, order: Order) -> float:
        if not self._api:
            raise RuntimeError("Not logged in.")
        # Requires contract object; keep as explicit error unless user wires instrument resolver.
        raise RuntimeError("AliceBlue order placement requires contract object mapping (see pya3 docs).")

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        raise RuntimeError("AliceBlue exit requires contract mapping.")

    def cancel_all_orders(self) -> None:
        try:
            if self._api:
                self._api.cancel_all_orders()
        except Exception:
            pass
