
from __future__ import annotations

import datetime as dt
import logging
import threading
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from core.time_utils import IST, floor_time, to_ist

log = logging.getLogger("candle_agg")


@dataclass
class Candle:
    start: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {"open": self.open, "high": self.high, "low": self.low, "close": self.close, "volume": self.volume}


class CandleAggregator:
    '''
    Builds N-minute candles from tick LTP.
    - Pure websocket input (ticks), no polling.
    - Emits on candle close.
    '''

    def __init__(self, timeframe_minutes: int, on_candle_close: Callable[[str, Dict[str, float], float], None]):
        self.tf = int(timeframe_minutes)
        self.on_candle_close = on_candle_close
        self._lock = threading.RLock()
        self._cur: Dict[str, Candle] = {}

    def on_tick(self, symbol: str, ltp: float, ts: Optional[dt.datetime] = None, volume: float = 0.0) -> None:
        ts = to_ist(ts or dt.datetime.now(tz=IST))
        bucket = floor_time(ts, self.tf)
        with self._lock:
            cur = self._cur.get(symbol)
            if cur is None:
                self._cur[symbol] = Candle(start=bucket, open=ltp, high=ltp, low=ltp, close=ltp, volume=float(volume or 0.0))
                return
            if bucket != cur.start:
                # close old candle
                try:
                    self.on_candle_close(symbol, cur.to_dict(), cur.start.timestamp())
                except Exception as e:
                    log.exception("on_candle_close failed: %s", e)
                # start new
                self._cur[symbol] = Candle(start=bucket, open=ltp, high=ltp, low=ltp, close=ltp, volume=float(volume or 0.0))
                return
            # update
            cur.close = ltp
            cur.high = max(cur.high, ltp)
            cur.low = min(cur.low, ltp)
            if volume:
                cur.volume += float(volume)

    def flush(self) -> None:
        with self._lock:
            for sym, cur in list(self._cur.items()):
                try:
                    self.on_candle_close(sym, cur.to_dict(), cur.start.timestamp())
                except Exception:
                    pass
            self._cur.clear()
