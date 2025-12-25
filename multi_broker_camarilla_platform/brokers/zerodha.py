
from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.zerodha")


class ZerodhaBroker(Broker):
    name = "ZERODHA"

    def __init__(self):
        self._kite = None
        self._ticker = None
        self._logged_in = False
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._token_map: Dict[str, int] = {}  # symbol -> instrument_token
        self._rev_token_map: Dict[int, str] = {}
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        try:
            from kiteconnect import KiteConnect
        except Exception as e:
            raise RuntimeError("kiteconnect not installed. Install requirements and retry.") from e
        api_key = creds.get("api_key") or creds.get("API_KEY")
        access_token = creds.get("access_token") or creds.get("ACCESS_TOKEN")
        if not api_key or not access_token:
            raise ValueError("Zerodha requires api_key and access_token saved in the vault.")
        kite = KiteConnect(api_key=str(api_key))
        kite.set_access_token(str(access_token))
        self._kite = kite
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return bool(self._logged_in)

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        if not self._kite:
            raise RuntimeError("Not logged in.")
        try:
            from kiteconnect import KiteTicker
        except Exception as e:
            raise RuntimeError("kiteconnect not installed (KiteTicker).") from e
        self._on_tick = on_tick
        api_key = self._kite.api_key
        access_token = self._kite.access_token
        ticker = KiteTicker(api_key, access_token)

        def _on_ticks(ws, ticks):
            for t in ticks:
                token = int(t.get("instrument_token") or 0)
                ltp = float(t.get("last_price") or 0.0)
                with self._lock:
                    sym = self._rev_token_map.get(token)
                if sym and self._on_tick:
                    self._on_tick(sym, ltp, t)

        def _on_connect(ws, resp):
            with self._lock:
                tokens = list(self._rev_token_map.keys())
            if tokens:
                ws.subscribe(tokens)
                ws.set_mode(ws.MODE_LTP, tokens)
            log.info("Zerodha websocket connected, subscribed=%d", len(tokens))

        def _on_close(ws, code, reason):
            log.warning("Zerodha websocket closed: %s %s", code, reason)

        ticker.on_ticks = _on_ticks
        ticker.on_connect = _on_connect
        ticker.on_close = _on_close
        ticker.on_error = lambda ws, code, reason: log.warning("Zerodha ws error: %s %s", code, reason)
        ticker.on_reconnect = lambda ws, attempts: log.warning("Zerodha ws reconnect attempts=%s", attempts)
        ticker.on_noreconnect = lambda ws: log.error("Zerodha ws no reconnect")
        self._ticker = ticker
        # Start websocket in a daemon thread (non-blocking)
        th = threading.Thread(target=ticker.connect, kwargs={"threaded": False, "disable_ssl_verification": False}, daemon=True)
        th.start()

    def _ensure_tokens(self):
        if not self._kite:
            raise RuntimeError("Not logged in.")
        # Load instruments only once
        if self._token_map:
            return
        inst = self._kite.instruments()
        for row in inst:
            tsym = row.get("tradingsymbol")
            token = row.get("instrument_token")
            exch = row.get("exchange")
            if not tsym or token is None:
                continue
            symkey = f"{exch}:{tsym}"
            self._token_map[symkey] = int(token)
        # Reverse map created on subscribe for requested keys only.

    def subscribe(self, symbol: str, segment: Segment) -> None:
        self._ensure_tokens()
        # Best-effort mapping: user symbol can be plain (NIFTY) or "NSE:INFY" or "NFO:NIFTY..."
        with self._lock:
            keys = []
            if ":" in symbol:
                keys.append(symbol)
            else:
                # Try common exchanges
                keys += [f"NSE:{symbol}", f"BSE:{symbol}", f"NFO:{symbol}", f"MCX:{symbol}", f"CDS:{symbol}"]
            token = None
            symkey = None
            for k in keys:
                if k in self._token_map:
                    token = self._token_map[k]
                    symkey = k
                    break
            if token is None:
                raise ValueError(f"Zerodha could not resolve instrument token for symbol={symbol}. Use exchange:symbol or refresh instruments.")
            self._rev_token_map[int(token)] = symbol

        if self._ticker:
            self._ticker.subscribe([int(token)])
            self._ticker.set_mode(self._ticker.MODE_LTP, [int(token)])

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        if not self._ticker:
            return
        with self._lock:
            token = None
            for t, s in list(self._rev_token_map.items()):
                if s == symbol:
                    token = int(t)
                    self._rev_token_map.pop(int(t), None)
                    break
        if token is not None:
            self._ticker.unsubscribe([token])

    def disconnect_marketdata(self) -> None:
        if self._ticker:
            try:
                self._ticker.close()
            except Exception:
                pass
        self._ticker = None

    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        if not self._kite:
            raise RuntimeError("Not logged in.")
        self._ensure_tokens()
        # Zerodha historical requires instrument token; we resolve best-effort
        token = None
        if ":" in symbol:
            token = self._token_map.get(symbol)
        if token is None:
            # Try NSE for indices (Zerodha has "NSE:NIFTY 50" etc; users can store correct mapping in instruments)
            token = self._token_map.get(f"NSE:{symbol}") or self._token_map.get(f"NFO:{symbol}") or self._token_map.get(f"MCX:{symbol}")
        if token is None:
            raise ValueError(f"Cannot resolve instrument token for {symbol}.")

        interval = f"{interval_minutes}minute"
        data = self._kite.historical_data(int(token), from_date=start, to_date=end, interval=interval, continuous=False, oi=False)
        df = pd.DataFrame(data)
        # expected columns: date, open, high, low, close, volume
        if "date" in df.columns:
            df = df.rename(columns={"date": "timestamp"})
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def place_order(self, order: Order) -> float:
        if not self._kite:
            raise RuntimeError("Not logged in.")
        # Market order
        variety = "regular"
        exch, tsym = ("NSE", order.symbol)
        if ":" in order.symbol:
            exch, tsym = order.symbol.split(":", 1)
        txn = "BUY" if order.side.value == "BUY" else "SELL"
        oid = self._kite.place_order(
            variety=variety,
            exchange=exch,
            tradingsymbol=tsym,
            transaction_type=txn,
            quantity=int(order.qty),
            product=order.product,
            order_type=order.order_type,
            price=None,
            tag=order.tag,
        )
        order.broker_order_id = str(oid)
        # Best-effort fill: use last_price snapshot
        try:
            q = self._kite.ltp([f"{exch}:{tsym}"])
            px = float(q[f"{exch}:{tsym}"]["last_price"])
            return px
        except Exception:
            return 0.0

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        if not self._kite:
            raise RuntimeError("Not logged in.")
        exch, tsym = ("NSE", symbol)
        if ":" in symbol:
            exch, tsym = symbol.split(":", 1)
        txn = "SELL" if side.value == "BUY" else "BUY"
        self._kite.place_order(
            variety="regular",
            exchange=exch,
            tradingsymbol=tsym,
            transaction_type=txn,
            quantity=int(qty),
            product=product,
            order_type="MARKET",
        )

    def cancel_all_orders(self) -> None:
        if not self._kite:
            return
        try:
            orders = self._kite.orders()
            for o in orders:
                if o.get("status") in ("OPEN", "TRIGGER PENDING"):
                    self._kite.cancel_order(variety=o.get("variety") or "regular", order_id=o.get("order_id"))
        except Exception as e:
            log.warning("Cancel all orders failed: %s", e)
