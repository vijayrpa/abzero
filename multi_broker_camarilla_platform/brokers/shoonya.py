
from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.shoonya")


class ShoonyaBroker(Broker):
    name = "SHOONYA"

    def __init__(self):
        self._api = None
        self._logged_in = False
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._subs: set[str] = set()
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        try:
            from NorenRestApiPy.NorenApi import NorenApi
        except Exception as e:
            raise RuntimeError("NorenRestApiPy not installed. Install requirements and retry.") from e

        class _Api(NorenApi):
            def __init__(self):
                super().__init__(host="https://api.shoonya.com/NorenWClientTP/", websocket="wss://api.shoonya.com/NorenWSTP/")

        uid = creds.get("user_id") or creds.get("USER_ID")
        pwd = creds.get("password") or creds.get("PASSWORD")
        factor2 = creds.get("factor2") or creds.get("FACTOR2")  # TOTP/2FA
        vc = creds.get("vendor_code") or creds.get("VENDOR_CODE")
        app_key = creds.get("app_key") or creds.get("APP_KEY")
        imei = creds.get("imei") or creds.get("IMEI") or "1234567890"

        if not uid or not pwd or not factor2 or not vc or not app_key:
            raise ValueError("Shoonya requires user_id,password,factor2,vendor_code,app_key (and imei optional).")

        api = _Api()
        r = api.login(userid=str(uid), password=str(pwd), twoFA=str(factor2), vendor_code=str(vc), api_secret=str(app_key), imei=str(imei))
        if not r or r.get("stat") != "Ok":
            raise RuntimeError(f"Shoonya login failed: {r}")
        self._api = api
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return bool(self._logged_in)

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        if not self._api:
            raise RuntimeError("Not logged in.")
        self._on_tick = on_tick

        def event_handler_order_update(msg):
            return

        def event_handler_feed_update(tick):
            try:
                sym = tick.get("ts") or ""
                ltp = float(tick.get("lp") or 0.0)
                if sym and self._on_tick:
                    self._on_tick(sym, ltp, tick)
            except Exception:
                pass

        def open_callback():
            log.info("Shoonya websocket opened")
            # Subscriptions happen via subscribe()

        try:
            self._api.start_websocket(
                order_update_callback=event_handler_order_update,
                subscribe_callback=event_handler_feed_update,
                socket_open_callback=open_callback,
            )
        except Exception as e:
            raise RuntimeError(f"Shoonya websocket start failed: {e}") from e

    def subscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.add(symbol)
        # Shoonya subscription requires exch and token; keep executable with best-effort if user provides correct symbol format.
        try:
            # Accept format: "NSE|26000" (exch|token) commonly used in examples
            self._api.subscribe(symbol)
        except Exception as e:
            log.warning("Shoonya subscribe failed for %s (needs exch|token): %s", symbol, e)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.discard(symbol)
        try:
            self._api.unsubscribe(symbol)
        except Exception:
            pass

    def disconnect_marketdata(self) -> None:
        try:
            if self._api:
                self._api.close_websocket()
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
        raise RuntimeError("Shoonya historical OHLCV requires token mapping.")

    def place_order(self, order: Order) -> float:
        if not self._api:
            raise RuntimeError("Not logged in.")
        # Shoonya order requires exch, tradingsymbol, qty, buy/sell etc. User must provide token/exchange mapping.
        raise RuntimeError("Shoonya order placement requires exchange/token mapping specific to contract.")

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        raise RuntimeError("Shoonya exit requires exchange/token mapping.")

    def cancel_all_orders(self) -> None:
        try:
            if self._api:
                ob = self._api.get_order_book()
                for o in (ob or []):
                    if str(o.get("status", "")).upper() in ("OPEN", "TRIGGER_PENDING"):
                        self._api.cancel_order(o.get("norenordno"))
        except Exception as e:
            log.warning("Cancel all orders failed: %s", e)
