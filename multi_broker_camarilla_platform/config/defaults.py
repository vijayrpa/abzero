
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Optional


class Segment(str, Enum):
    NSE_CASH = "NSE_CASH"
    BSE_CASH = "BSE_CASH"
    NSE_FNO = "NSE_FNO"
    MCX = "MCX"
    CDS = "CDS"
    INDICES = "INDICES"

    @classmethod
    def from_str(cls, s: str) -> "Segment":
        s = (s or "").strip().upper()
        for v in cls:
            if v.value == s:
                return v
        raise ValueError(f"Unknown segment: {s}")


class BrokerName(str, Enum):
    PAPER = "PAPER"
    ZERODHA = "ZERODHA"
    ALICEBLUE = "ALICEBLUE"
    SHOONYA = "SHOONYA"
    ANGELONE = "ANGELONE"


@dataclass
class RiskSettings:
    capital: float = 200000.0
    max_risk_per_trade_pct: float = 1.0
    max_trades_per_day: int = 6
    daily_loss_limit_pct: float = 3.0
    allow_new_trades_after_daily_loss_hit: bool = False

    one_active_trade_per_symbol: bool = True
    kill_switch: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StrategySettings:
    timeframe_minutes: int = 5
    price_tolerance_pct: float = 0.08  # proximity threshold to L3/H3 for mean reversion
    breakout_volume_mult: float = 1.5
    confirmation_volume_mult: float = 1.1
    rsi_length: int = 14
    atr_length: int = 14
    min_atr_pct: float = 0.06
    use_volume_filters: bool = True

    # Bias detection
    bias_method: str = "OPEN_VS_PIVOT"  # or OPEN_VS_PREVCLOSE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptionsSettings:
    enabled: bool = True
    product: str = "MIS"  # MIS/NRML
    order_type: str = "MARKET"

    # index strike steps (defaults)
    index_strike_steps: Dict[str, int] = field(
        default_factory=lambda: {
            "NIFTY": 50,
            "BANKNIFTY": 100,
            "FINNIFTY": 50,
            "MIDCPNIFTY": 25,
        }
    )

    # Exchange: used in symbol formatting (resolver handles broker-specific mapping)
    default_exchange: str = "NFO"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TelegramSettings:
    enabled: bool = True
    poll_interval_sec: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AppSettings:
    broker: BrokerName = BrokerName.PAPER
    segment: Segment = Segment.NSE_FNO
    trade_mode: str = "PAPER"  # PAPER or LIVE

    symbols: list[str] = field(default_factory=lambda: ["NIFTY"])

    risk: RiskSettings = field(default_factory=RiskSettings)
    strategy: StrategySettings = field(default_factory=StrategySettings)
    options: OptionsSettings = field(default_factory=OptionsSettings)
    telegram: TelegramSettings = field(default_factory=TelegramSettings)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["broker"] = self.broker.value
        d["segment"] = self.segment.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AppSettings":
        s = cls.default()
        if not d:
            return s
        try:
            s.broker = BrokerName((d.get("broker") or s.broker.value).upper())
        except Exception:
            pass
        try:
            s.segment = Segment.from_str(d.get("segment") or s.segment.value)
        except Exception:
            pass
        s.trade_mode = (d.get("trade_mode") or s.trade_mode).upper()
        s.symbols = list(d.get("symbols") or s.symbols)

        if "risk" in d and isinstance(d["risk"], dict):
            for k, v in d["risk"].items():
                if hasattr(s.risk, k):
                    setattr(s.risk, k, v)
        if "strategy" in d and isinstance(d["strategy"], dict):
            for k, v in d["strategy"].items():
                if hasattr(s.strategy, k):
                    setattr(s.strategy, k, v)
        if "options" in d and isinstance(d["options"], dict):
            for k, v in d["options"].items():
                if hasattr(s.options, k):
                    setattr(s.options, k, v)
        if "telegram" in d and isinstance(d["telegram"], dict):
            for k, v in d["telegram"].items():
                if hasattr(s.telegram, k):
                    setattr(s.telegram, k, v)
        return s

    @classmethod
    def default(cls) -> "AppSettings":
        return cls()
