from __future__ import annotations

import logging
import math
import random
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from algo_platform.brokers.base import BrokerBase, BrokerLoginResult, OHLC, TickCallback
from algo_platform.models import Order, OrderStatus, Position, Product, Side, SymbolKey, Tick

log = logging.getLogger(__name__)


class PaperBroker(BrokerBase):
    """
    Fully working paper broker:
    - MARKET orders fill at current LTP
    - Positions/orders tracked locally
    - Websocket emits simulated ticks (random-walk) for subscribed symbols
    """

    name = "Paper"

    def __init__(self) -> None:
        super().__init__()
        self._logged_in = False
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._ltp: Dict[str, float] = {}
        self._subscribed: Dict[str, SymbolKey] = {}
        self._tick_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._on_tick: Optional[TickCallback] = None

    def login(self, creds: Dict[str, Any]) -> BrokerLoginResult:
        self._logged_in = True
        return BrokerLoginResult(ok=True, message="Paper broker ready.")

    def logout(self) -> None:
        self.websocket_disconnect()
        self._logged_in = False

    def download_contract_master(self, out_dir: str) -> str:
        # Not required for paper mode; we still satisfy interface.
        return ""

    def ensure_symbol(self, symbol: SymbolKey) -> None:
        k = symbol.key()
        if k not in self._ltp:
            # Seed deterministic-ish price based on symbol text.
            seed = sum(ord(c) for c in symbol.tradingsymbol) % 1000
            self._ltp[k] = float(100 + (seed % 200))

    def get_previous_day_ohlc(self, symbol: SymbolKey) -> OHLC:
        self.ensure_symbol(symbol)
        px = self._ltp[symbol.key()]
        # Simple synthetic OHLC around current price.
        high = px * 1.02
        low = px * 0.98
        open_ = px * 0.995
        close = px
        return OHLC(d=date.today() - timedelta(days=1), open=open_, high=high, low=low, close=close)

    def _pos(self, symbol: SymbolKey) -> Position:
        k = symbol.key()
        if k not in self._positions:
            self._positions[k] = Position(symbol=symbol, net_qty=0, avg_price=0.0)
        return self._positions[k]

    def place_order(
        self,
        symbol: SymbolKey,
        side: Side,
        qty: int,
        product: Product,
        order_type: str,
        price: Optional[float] = None,
    ) -> Order:
        if not self._logged_in:
            raise RuntimeError("Paper broker not logged in.")
        if qty <= 0:
            raise ValueError("qty must be > 0")
        self.ensure_symbol(symbol)

        oid = f"PAPER-{uuid.uuid4().hex[:12]}"
        o = Order(
            order_id=oid,
            symbol=symbol,
            side=side,
            qty=qty,
            product=product,
            order_type=order_type.upper(),
            price=price,
            status=OrderStatus.OPEN,
        )

        fill_px = self._ltp[symbol.key()]
        o.status = OrderStatus.FILLED
        o.filled_qty = qty
        o.avg_price = fill_px
        o.updated_at = datetime.utcnow()
        self._orders[oid] = o

        # Update position avg price and realized pnl on flips.
        pos = self._pos(symbol)
        signed = qty if side == Side.BUY else -qty
        if pos.net_qty == 0 or (pos.net_qty > 0 and signed > 0) or (pos.net_qty < 0 and signed < 0):
            # Same direction add.
            new_qty = pos.net_qty + signed
            if new_qty != 0:
                pos.avg_price = (pos.avg_price * abs(pos.net_qty) + fill_px * abs(signed)) / abs(new_qty)
            pos.net_qty = new_qty
        else:
            # Reducing or flipping.
            closing_qty = min(abs(pos.net_qty), abs(signed))
            if pos.net_qty > 0 and signed < 0:
                pos.realized_pnl += (fill_px - pos.avg_price) * closing_qty
            elif pos.net_qty < 0 and signed > 0:
                pos.realized_pnl += (pos.avg_price - fill_px) * closing_qty
            pos.net_qty = pos.net_qty + signed
            if pos.net_qty == 0:
                pos.avg_price = 0.0
            else:
                # Flipped: remaining qty at fill px.
                pos.avg_price = fill_px

        return o

    def modify_order(self, order_id: str, qty: Optional[int] = None, price: Optional[float] = None) -> Order:
        o = self._orders[order_id]
        o.updated_at = datetime.utcnow()
        o.broker_message = "Paper: modify ignored (orders fill immediately)."
        return o

    def cancel_order(self, order_id: str) -> Order:
        o = self._orders[order_id]
        if o.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            return o
        o.status = OrderStatus.CANCELLED
        o.updated_at = datetime.utcnow()
        return o

    def get_positions(self) -> List[Position]:
        return list(self._positions.values())

    def get_orders(self) -> List[Order]:
        return list(self._orders.values())

    def websocket_connect(self, on_tick: TickCallback) -> None:
        self._on_tick = on_tick
        if self._tick_thread and self._tick_thread.is_alive():
            return
        self._stop.clear()
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._tick_thread.start()

    def websocket_disconnect(self) -> None:
        self._stop.set()
        self._on_tick = None

    def websocket_subscribe(self, symbols: List[SymbolKey]) -> None:
        for s in symbols:
            self.ensure_symbol(s)
            self._subscribed[s.key()] = s

    def websocket_unsubscribe(self, symbols: List[SymbolKey]) -> None:
        for s in symbols:
            self._subscribed.pop(s.key(), None)

    def _tick_loop(self) -> None:
        last_hilo: Dict[str, Dict[str, float]] = {}
        while not self._stop.is_set():
            if not self._subscribed or not self._on_tick:
                time.sleep(0.2)
                continue

            now = datetime.utcnow()
            for k, sym in list(self._subscribed.items()):
                px = self._ltp.get(k, 100.0)
                # Random walk with mild volatility.
                drift = (random.random() - 0.5) * 0.6
                px = max(0.05, px + drift)
                self._ltp[k] = px

                hilo = last_hilo.setdefault(k, {"open": px, "high": px, "low": px, "prev_close": px})
                hilo["high"] = max(hilo["high"], px)
                hilo["low"] = min(hilo["low"], px)

                t = Tick(
                    symbol=sym,
                    ltp=px,
                    ts=now,
                    open=hilo["open"],
                    high=hilo["high"],
                    low=hilo["low"],
                    prev_close=hilo["prev_close"],
                )
                try:
                    self._on_tick(t)
                except Exception:
                    log.exception("Tick callback error")

            time.sleep(0.25)

