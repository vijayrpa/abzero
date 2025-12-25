
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from brokers.base import Broker
from config.defaults import Segment

log = logging.getLogger("ws_manager")


class MarketDataManager:
    '''
    Unified websocket manager.
    - Connects broker marketdata websocket (if supported)
    - Provides subscribe/unsubscribe
    - Handles basic auto-reconnect loop (best-effort)
    '''

    def __init__(self, broker: Broker):
        self.broker = broker
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._subs: list[tuple[str, Segment]] = []
        self._lock = threading.RLock()

    def start(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        self._on_tick = on_tick
        self._stop_evt.clear()
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        try:
            self.broker.disconnect_marketdata()
        except Exception:
            pass

    def subscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            if (symbol, segment) not in self._subs:
                self._subs.append((symbol, segment))
        try:
            self.broker.subscribe(symbol, segment)
        except Exception as e:
            log.warning("subscribe failed: %s", e)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs = [x for x in self._subs if x != (symbol, segment)]
        try:
            self.broker.unsubscribe(symbol, segment)
        except Exception:
            pass

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop_evt.is_set():
            try:
                if not self._on_tick:
                    time.sleep(0.2)
                    continue
                self.broker.connect_marketdata(self._on_tick)
                # Re-subscribe
                with self._lock:
                    subs = list(self._subs)
                for sym, seg in subs:
                    try:
                        self.broker.subscribe(sym, seg)
                    except Exception:
                        pass
                backoff = 1.0
                # Keep thread alive while websocket runs in broker-managed background.
                while not self._stop_evt.is_set():
                    time.sleep(1.0)
            except Exception as e:
                log.warning("Market data connect error: %s", e)
                try:
                    self.broker.disconnect_marketdata()
                except Exception:
                    pass
                time.sleep(backoff)
                backoff = min(30.0, backoff * 1.8)
