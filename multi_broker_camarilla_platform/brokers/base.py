
from __future__ import annotations

import abc
import datetime as dt
from typing import Any, Callable, Dict, Optional

import pandas as pd

from config.defaults import Segment
from core.models import Order, Side


class Broker(abc.ABC):
    name: str

    @abc.abstractmethod
    def login(self, creds: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def is_logged_in(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        '''
        Must be websocket-first for live market data.
        on_tick(symbol, ltp, raw_tick_dict)
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def subscribe(self, symbol: str, segment: Segment) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def disconnect_marketdata(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abc.abstractmethod
    def place_order(self, order: Order) -> float:
        '''
        Returns fill price (best-effort).
        '''
        raise NotImplementedError

    @abc.abstractmethod
    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def cancel_all_orders(self) -> None:
        raise NotImplementedError
