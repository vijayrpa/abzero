from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from algo_platform.models import Order, Position, Product, Side, SymbolKey, Tick


TickCallback = Callable[[Tick], None]


@dataclass(frozen=True)
class BrokerLoginResult:
    ok: bool
    message: str


@dataclass(frozen=True)
class OHLC:
    d: date
    open: float
    high: float
    low: float
    close: float


class BrokerBase(abc.ABC):
    """
    Unified broker interface for:
    place_order/modify/cancel, positions/orders, websocket subscription, and contract master.
    """

    name: str

    def __init__(self) -> None:
        self._tick_cb: Optional[TickCallback] = None

    @abc.abstractmethod
    def login(self, creds: Dict[str, Any]) -> BrokerLoginResult:
        raise NotImplementedError

    @abc.abstractmethod
    def logout(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def download_contract_master(self, out_dir: str) -> str:
        """
        Download contract master / instruments and return the saved file path.
        """

    @abc.abstractmethod
    def ensure_symbol(self, symbol: SymbolKey) -> None:
        """
        Ensure instrument/token mapping exists for this symbol.
        """

    @abc.abstractmethod
    def get_previous_day_ohlc(self, symbol: SymbolKey) -> OHLC:
        raise NotImplementedError

    @abc.abstractmethod
    def place_order(
        self,
        symbol: SymbolKey,
        side: Side,
        qty: int,
        product: Product,
        order_type: str,
        price: Optional[float] = None,
    ) -> Order:
        raise NotImplementedError

    @abc.abstractmethod
    def modify_order(self, order_id: str, qty: Optional[int] = None, price: Optional[float] = None) -> Order:
        raise NotImplementedError

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> Order:
        raise NotImplementedError

    @abc.abstractmethod
    def get_positions(self) -> List[Position]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_orders(self) -> List[Order]:
        raise NotImplementedError

    @abc.abstractmethod
    def websocket_connect(self, on_tick: TickCallback) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def websocket_disconnect(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def websocket_subscribe(self, symbols: List[SymbolKey]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def websocket_unsubscribe(self, symbols: List[SymbolKey]) -> None:
        raise NotImplementedError

