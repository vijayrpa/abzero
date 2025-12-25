
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class Order:
    symbol: str
    side: Side
    qty: int
    order_type: str = "MARKET"
    product: str = "MIS"
    price: Optional[float] = None
    tag: str = "CAMARILLA"
    broker_order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.NEW
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trade:
    symbol: str
    side: Side
    qty: int
    entry_price: float
    entry_time: float
    stop_loss: float
    target: float
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    active: bool = True
    reason: str = ""
    pnl: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def close(self, price: float, ts: float, reason: str) -> None:
        self.exit_price = price
        self.exit_time = ts
        self.active = False
        self.reason = reason
        self.pnl = self._calc_pnl(price)

    def _calc_pnl(self, exit_price: float) -> float:
        if self.side == Side.BUY:
            return (exit_price - self.entry_price) * self.qty
        return (self.entry_price - exit_price) * self.qty
