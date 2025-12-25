
from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.angelone")


class AngelOneBroker(Broker):
    name = "ANGELONE"

    def __init__(self):
        self._api = None
        self._ws = None
        self._logged_in = False
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._subs: set[str] = set()
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        try:
            from SmartApi import SmartConnect
        except Exception as e:
            raise RuntimeError("smartapi-python not installed. Install requirements and retry.") from e
        api_key = creds.get("api_key") or creds.get("API_KEY")
        client_code = creds.get("client_code") or creds.get("CLIENT_CODE")
        password = creds.get("password") or creds.get("PASSWORD")
        totp = creds.get("totp") or creds.get("TOTP")  # optional
        if not api_key or not client_code or not password:
            raise ValueError("Angel One requires api_key, client_code, password (and optionally totp) in vault.")
        api = SmartConnect(api_key=str(api_key))
        sess = api.generateSession(str(client_code), str(password), str(totp) if totp else None)
        if not sess or not sess.get("status"):
            raise RuntimeError(f"Angel One login failed: {sess}")
        self._api = api
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return bool(self._logged_in)

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        if not self._api:
            raise RuntimeError("Not logged in.")
        self._on_tick = on_tick
        try:
            # SmartWebSocketV2 is used in newer versions
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2
        except Exception as e:
            raise RuntimeError("Angel websocket class not available in your smartapi-python version.") from e

        feed_token = self._api.getfeedToken()
        auth = self._api.getAccessToken()
        client_code = self._api.userId
        ws = SmartWebSocketV2(auth, api_key=self._api.api_key, client_code=client_code, feed_token=feed_token)

        def on_data(wsapp, message):
            # Message structure differs; handle best-effort
            try:
                sym = message.get("tradingsymbol") or message.get("symbol") or ""
                ltp = float(message.get("last_traded_price") or message.get("ltp") or 0.0)
                if sym and self._on_tick:
                    self._on_tick(sym, ltp, message)
            except Exception:
                return

        def on_open(wsapp):
            log.info("Angel websocket opened")
            # Subscriptions should be done via subscribe() calls

        def on_error(wsapp, error):
            log.warning("Angel websocket error: %s", error)

        def on_close(wsapp):
            log.warning("Angel websocket closed")

        ws.on_data = on_data
        ws.on_open = on_open
        ws.on_error = on_error
        ws.on_close = on_close

        self._ws = ws
        th = threading.Thread(target=ws.connect, daemon=True)
        th.start()

    def subscribe(self, symbol: str, segment: Segment) -> None:
        if not self._ws:
            with self._lock:
                self._subs.add(symbol)
            return
        with self._lock:
            self._subs.add(symbol)
        # SmartAPI subscription requires tokens; you should use scrip master.
        # To keep system executable, we allow raw symbol subscription best-effort if supported by installed SDK.
        try:
            # Some builds support subscribe with a dict payload
            self._ws.subscribe(correlation_id="cam", mode=1, token_list=[{"exchangeType": 1, "tokens": [symbol]}])
        except Exception as e:
            log.warning("Angel subscribe failed for %s (needs token mapping): %s", symbol, e)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.discard(symbol)

    def disconnect_marketdata(self) -> None:
        if self._ws:
            try:
                self._ws.close_connection()
            except Exception:
                pass
        self._ws = None

    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        if not self._api:
            raise RuntimeError("Not logged in.")
        # Angel historical data requires token + exchange mapping. For production you should load scrip master.
        raise RuntimeError("Angel One historical OHLCV requires token mapping (scrip master). Load instruments and implement resolver for your account.")

    def place_order(self, order: Order) -> float:
        if not self._api:
            raise RuntimeError("Not logged in.")
        txn = "BUY" if order.side.value == "BUY" else "SELL"
        payload = {
            "variety": "NORMAL",
            "tradingsymbol": order.symbol,
            "symboltoken": order.meta.get("token") or order.symbol,
            "transactiontype": txn,
            "exchange": order.meta.get("exchange") or "NSE",
            "ordertype": order.order_type,
            "producttype": order.product,
            "duration": "DAY",
            "price": "0",
            "quantity": str(int(order.qty)),
        }
        r = self._api.placeOrder(payload)
        if not r or not r.get("status"):
            raise RuntimeError(f"Angel placeOrder failed: {r}")
        order.broker_order_id = str(r.get("data") or "")
        return 0.0

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        # Place opposite market order (requires token mapping in meta for precise execution)
        o = Order(symbol=symbol, side=Side.SELL if side == Side.BUY else Side.BUY, qty=qty, order_type="MARKET", product=product)
        self.place_order(o)

    def cancel_all_orders(self) -> None:
        # SmartAPI supports orderbook; cancelling open orders is account dependent
        try:
            ob = self._api.orderBook()
            for o in (ob.get("data") or []):
                if str(o.get("orderstatus", "")).upper() in ("OPEN", "TRIGGER PENDING"):
                    self._api.cancelOrder(o.get("orderid"))
        except Exception as e:
            log.warning("Cancel all orders failed: %s", e)
