from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set

from algo_platform.brokers.base import BrokerBase
from algo_platform.models import MarketSnapshot, SymbolKey, Tick

log = logging.getLogger(__name__)


TickListener = Callable[[Tick], None]


@dataclass
class TickEngineStatus:
    connected: bool = False
    last_error: str = ""
    last_tick_at: Optional[datetime] = None


class TickEngine:
    """
    Central tick engine:
    - One websocket connection per broker
    - Auto-resubscribe on reconnect
    - Tick fan-out to listeners (strategies, GUI, PnL)
    """

    def __init__(self, broker: BrokerBase) -> None:
        self._broker = broker
        self._listeners: List[TickListener] = []
        self._subscribed: Dict[str, SymbolKey] = {}
        self._snapshots: Dict[str, MarketSnapshot] = {}
        self._lock = threading.RLock()
        self._status = TickEngineStatus()
        self._running = False
        self._watchdog_thread: Optional[threading.Thread] = None

    def add_listener(self, cb: TickListener) -> None:
        with self._lock:
            self._listeners.append(cb)

    def remove_listener(self, cb: TickListener) -> None:
        with self._lock:
            self._listeners = [x for x in self._listeners if x != cb]

    def status(self) -> TickEngineStatus:
        with self._lock:
            return TickEngineStatus(
                connected=self._status.connected,
                last_error=self._status.last_error,
                last_tick_at=self._status.last_tick_at,
            )

    def get_snapshot(self, symbol: SymbolKey) -> MarketSnapshot:
        with self._lock:
            return self._snapshots.get(symbol.key(), MarketSnapshot())

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._connect()
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def stop(self) -> None:
        self._running = False
        try:
            self._broker.websocket_disconnect()
        except Exception:
            pass
        with self._lock:
            self._status.connected = False

    def subscribe(self, symbols: List[SymbolKey]) -> None:
        # Ensure symbol mapping exists first.
        for s in symbols:
            self._broker.ensure_symbol(s)
        try:
            self._broker.websocket_subscribe(symbols)
        except Exception as e:
            with self._lock:
                self._status.last_error = str(e)
            raise
        with self._lock:
            for s in symbols:
                self._subscribed[s.key()] = s

    def unsubscribe(self, symbols: List[SymbolKey]) -> None:
        try:
            self._broker.websocket_unsubscribe(symbols)
        except Exception:
            pass
        with self._lock:
            for s in symbols:
                self._subscribed.pop(s.key(), None)

    def subscribed_symbols(self) -> List[str]:
        with self._lock:
            return sorted(self._subscribed.keys())

    def _connect(self) -> None:
        try:
            self._broker.websocket_connect(self._on_tick)
            with self._lock:
                self._status.connected = True
                self._status.last_error = ""
        except Exception as e:
            with self._lock:
                self._status.connected = False
                self._status.last_error = str(e)
            log.exception("TickEngine connect failed")

    def _watchdog_loop(self) -> None:
        # Reconnect if needed and re-subscribe.
        while self._running:
            time.sleep(2.0)
            st = self.status()
            if not st.connected:
                self._connect()
                if self.status().connected:
                    # resubscribe
                    try:
                        with self._lock:
                            syms = list(self._subscribed.values())
                        if syms:
                            self._broker.websocket_subscribe(syms)
                    except Exception:
                        log.exception("Resubscribe failed")

    def _on_tick(self, tick: Tick) -> None:
        with self._lock:
            snap = self._snapshots.setdefault(tick.symbol.key(), MarketSnapshot())
            snap.ltp = tick.ltp
            if tick.open is not None:
                snap.open = tick.open
            if tick.high is not None:
                snap.high = tick.high
            if tick.low is not None:
                snap.low = tick.low
            if tick.prev_close is not None:
                snap.prev_close = tick.prev_close
            snap.last_tick_time = tick.ts
            self._status.last_tick_at = tick.ts
        listeners = []
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(tick)
            except Exception:
                log.exception("Tick listener error")

