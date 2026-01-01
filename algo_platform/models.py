from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


class TradeMode(str, enum.Enum):
    PAPER = "Paper"
    REAL = "Real"


class Side(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, enum.Enum):
    NEW = "NEW"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Product(str, enum.Enum):
    CNC = "CNC"
    MIS = "MIS"
    NRML = "NRML"


@dataclass(frozen=True)
class SymbolKey:
    """
    Canonical internal identifier, independent of broker.
    For cash: exchange=NSE/BSE, tradingsymbol=INFY, segment=CASH
    For derivatives: tradingsymbol like NIFTY24JAN18000CE, segment=NFO/MCX/CDS.
    """

    exchange: str
    tradingsymbol: str
    segment: str

    def key(self) -> str:
        return f"{self.exchange}:{self.segment}:{self.tradingsymbol}"


@dataclass
class MarketSnapshot:
    ltp: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    last_tick_time: Optional[datetime] = None


@dataclass
class Tick:
    symbol: SymbolKey
    ltp: float
    ts: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prev_close: Optional[float] = None


@dataclass
class Order:
    order_id: str
    symbol: SymbolKey
    side: Side
    qty: int
    product: Product
    order_type: str  # MARKET / LIMIT
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.NEW
    filled_qty: int = 0
    avg_price: float = 0.0
    broker_message: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Position:
    symbol: SymbolKey
    net_qty: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class StrategyLevels:
    buy_level: float
    buy_t1: float
    buy_t2: float
    buy_sl: float
    sell_level: float
    sell_t1: float
    sell_t2: float
    sell_sl: float


class StrategyType(str, enum.Enum):
    CAMARILLA = "Camarilla"
    MANUAL = "Manual"


class EntryType(str, enum.Enum):
    BUY_ONLY = "Buy"
    SELL_ONLY = "Sell"
    BOTH = "Both"


@dataclass
class PerSymbolConfig:
    qty: int
    entry_type: EntryType = EntryType.BOTH
    max_buy_trades: int = 1
    max_sell_trades: int = 1
    trailing_on: bool = False
    trail_value: float = 0.0
    strategy_on: bool = True
    trade_mode: TradeMode = TradeMode.PAPER
    exit_at_t1: bool = False
    exit_at_t2: bool = True
    risk_on: bool = False
    daily_loss_limit: float = 0.0
    daily_profit_limit: float = 0.0


@dataclass
class PerSymbolState:
    buy_trades_done: int = 0
    sell_trades_done: int = 0
    status: str = "Stopped"
    last_status_msg: str = ""
    running: bool = False
    # Re-arm flags to prevent duplicate immediate re-entries at same level.
    buy_armed: bool = True
    sell_armed: bool = True


@dataclass
class ActiveTrade:
    symbol: SymbolKey
    side: Side
    entry_price: float
    qty: int
    sl: float
    initial_sl: float
    t1: float
    t2: float
    trailing_on: bool
    trail_value: float
    best_price: float  # highest for BUY, lowest for SELL
    open_time: datetime
    closed: bool = False
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None


@dataclass
class StrategyRow:
    symbol: SymbolKey
    strategy_type: StrategyType
    levels: StrategyLevels
    config: PerSymbolConfig
    state: PerSymbolState = field(default_factory=PerSymbolState)
    active_trade: Optional[ActiveTrade] = None


@dataclass
class PortfolioView:
    positions: Dict[str, Position] = field(default_factory=dict)  # key: SymbolKey.key()
    orders: Dict[str, Order] = field(default_factory=dict)  # order_id -> Order

