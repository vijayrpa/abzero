#!/usr/bin/env python3
"""
Multi-Broker Advanced Camarilla Trading Platform - Project Generator

Usage:
  python generate_project.py
  python generate_project.py --force

This script generates:
  multi_broker_camarilla_platform/
    config/ brokers/ core/ websocket/ backtest/ gui/ logs/ data/
    main.py requirements.txt README.md

Notes:
  - Live trading requires broker credentials and the broker SDK packages installed.
  - Paper trading + CSV backtesting work out of the box.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import textwrap


PROJECT_ROOT = Path("multi_broker_camarilla_platform")


def _norm(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    if not s.endswith("\n"):
        s += "\n"
    return s


def _write_file(path: Path, content: str, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return
    path.write_text(_norm(content), encoding="utf-8")


def _chmod_private(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode & ~stat.S_IRWXG & ~stat.S_IRWXO)
    except Exception:
        # Best-effort on non-POSIX FS
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate multi-broker advanced Camarilla trading platform project.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    args = parser.parse_args()

    files: dict[str, str] = {}

    # -------------------------
    # Root docs / entrypoints
    # -------------------------
    files[str(PROJECT_ROOT / "README.md")] = r"""
## Multi-Broker Advanced Camarilla Trading Platform (Desktop / Tkinter)

This project is a **production-style, desktop-based algorithmic trading platform** for Indian markets using an **Advanced Camarilla strategy** on **5-minute candles**.

### Segments supported (architecture is segment-agnostic)
- **NSE Cash (Equity)**, **BSE Cash**
- **NSE F&O** (Index & Stock options)
- **MCX** (Commodity futures & options)
- **CDS** (Currency derivatives)
- Indices: **NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY**

### Multi-broker support (via unified abstraction layer)
- Zerodha (Kite Connect)
- AliceBlue (pya3)
- Shoonya / Finvasia (Noren API)
- Angel One (SmartAPI)

### Key capabilities
- **Live trading** (broker SDKs + credentials required)
- **Paper trading** (works out of the box)
- **Websocket-first tick engine** (no market polling) with auto-reconnect
- Tick-to-5m candle aggregation
- Advanced Camarilla: **H3/H4/L3/L4**
- Options execution: auto weekly expiry, ATM strike, CE/PE selection, lot size
- Risk: 1% max risk per trade, daily loss limit, max trades/day, one active trade/symbol, global kill switch
- Telegram alerts + Telegram **STOP** kill switch
- CSV backtesting using the same strategy logic

### Install

From the repo root:

```bash
python generate_project.py --force
python -m venv .venv
source .venv/bin/activate
pip install -r multi_broker_camarilla_platform/requirements.txt
```

### Run (GUI)

```bash
python multi_broker_camarilla_platform/main.py
```

### Run (Backtest)

Put a CSV into `multi_broker_camarilla_platform/data/` with at least:
`timestamp,open,high,low,close,volume`

Example:

```bash
python multi_broker_camarilla_platform/main.py --backtest --csv multi_broker_camarilla_platform/data/sample_5m.csv --symbol NIFTY --segment NSE_FNO --paper
```

### Credentials / Security
- Credentials are stored locally in an **encrypted vault** using a GUI-managed **master password**.
- Broker access tokens and Telegram tokens are **not hardcoded** in strategy code.

### Important
- Live trading requires correct broker credentials and may require enabling your broker's websocket / market data permissions.
- This platform includes **hard risk controls** but you are responsible for compliance, connectivity, broker limitations, and operational monitoring.
"""

    files[str(PROJECT_ROOT / "requirements.txt")] = r"""
cryptography>=43.0.0
requests>=2.32.0
pandas>=2.2.0
numpy>=2.0.0
python-dateutil>=2.9.0.post0
pytz>=2024.1
websockets>=13.0

# Optional broker SDKs (install as needed for LIVE trading):
kiteconnect>=5.0.0; python_version>="3.9"
smartapi-python>=1.5.5; python_version>="3.9"
pya3>=1.0.0; python_version>="3.9"
NorenRestApiPy>=0.0.24; python_version>="3.9"
"""

    files[str(PROJECT_ROOT / "generate_project.py")] = r"""
from __future__ import annotations

import runpy
from pathlib import Path


def main() -> int:
    # Delegate to the repo-root generator (single source of truth).
    root_gen = Path(__file__).resolve().parents[1] / "generate_project.py"
    if not root_gen.exists():
        raise SystemExit("Root generate_project.py not found. Run from repo root.")
    runpy.run_path(str(root_gen), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

    files[str(PROJECT_ROOT / "main.py")] = r"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.logging_config import configure_logging
from gui.app import TradingApp
from backtest.engine import run_csv_backtest
from config.defaults import AppSettings, Segment


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Multi-broker Advanced Camarilla Trading Platform")
    p.add_argument("--backtest", action="store_true", help="Run CSV backtest instead of GUI.")
    p.add_argument("--csv", type=str, default="", help="CSV file for backtest.")
    p.add_argument("--symbol", type=str, default="NIFTY", help="Symbol for backtest.")
    p.add_argument("--segment", type=str, default="NSE_FNO", help="Segment (e.g., NSE_CASH, BSE_CASH, NSE_FNO, MCX, CDS).")
    p.add_argument("--paper", action="store_true", help="Force paper mode for backtest run.")
    return p.parse_args()


def main() -> int:
    configure_logging()
    args = _parse_args()

    if args.backtest:
        if not args.csv:
            print("Missing --csv path", file=sys.stderr)
            return 2
        seg = Segment.from_str(args.segment)
        settings = AppSettings.default()
        settings.trade_mode = "PAPER" if args.paper else settings.trade_mode
        csv_path = Path(args.csv)
        report = run_csv_backtest(
            csv_path=csv_path,
            symbol=args.symbol,
            segment=seg,
            settings=settings,
        )
        print(report.to_text())
        return 0

    app = TradingApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""

    # -------------------------
    # Package init files
    # -------------------------
    for pkg in ["config", "brokers", "core", "websocket", "backtest", "gui"]:
        files[str(PROJECT_ROOT / pkg / "__init__.py")] = ""

    # -------------------------
    # config/
    # -------------------------
    files[str(PROJECT_ROOT / "config" / "defaults.py")] = r"""
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
"""

    files[str(PROJECT_ROOT / "config" / "paths.py")] = r"""
from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    p = project_root() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    p = project_root() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_dir() -> Path:
    p = project_root() / "config"
    p.mkdir(parents=True, exist_ok=True)
    return p


def vault_path() -> Path:
    return config_dir() / "vault.enc"


def settings_path() -> Path:
    return config_dir() / "app_settings.json"
"""

    files[str(PROJECT_ROOT / "config" / "settings_store.py")] = r"""
from __future__ import annotations

import json
from typing import Any, Dict

from config.defaults import AppSettings
from config.paths import settings_path


def load_settings() -> AppSettings:
    p = settings_path()
    if not p.exists():
        return AppSettings.default()
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return AppSettings.from_dict(d)
    except Exception:
        return AppSettings.default()


def save_settings(settings: AppSettings) -> None:
    p = settings_path()
    p.write_text(json.dumps(settings.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
"""

    files[str(PROJECT_ROOT / "config" / "credentials.py")] = r"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet, InvalidToken

from config.paths import vault_path


@dataclass
class VaultRecord:
    version: int
    salt_b64: str
    iterations: int
    token_b64: str


class CredentialVault:
    '''
    Encrypted local vault.
    - Derives key from master password (PBKDF2-HMAC-SHA256).
    - Encrypts JSON payload with Fernet.
    '''

    VERSION = 1
    DEFAULT_ITERATIONS = 310_000

    def __init__(self, path: Optional[Path] = None):
        self.path = path or vault_path()

    def exists(self) -> bool:
        return self.path.exists()

    def _derive_key(self, password: str, salt: bytes, iterations: int) -> bytes:
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def init_empty(self, password: str) -> None:
        salt = os.urandom(16)
        it = self.DEFAULT_ITERATIONS
        key = self._derive_key(password=password, salt=salt, iterations=it)
        f = Fernet(key)
        payload = {"brokers": {}, "telegram": {}}
        token = f.encrypt(json.dumps(payload).encode("utf-8"))
        rec = VaultRecord(
            version=self.VERSION,
            salt_b64=base64.b64encode(salt).decode("ascii"),
            iterations=it,
            token_b64=base64.b64encode(token).decode("ascii"),
        )
        self._write_record(rec)

    def _read_record(self) -> VaultRecord:
        raw = self.path.read_text(encoding="utf-8")
        d = json.loads(raw)
        return VaultRecord(
            version=int(d["version"]),
            salt_b64=str(d["salt_b64"]),
            iterations=int(d["iterations"]),
            token_b64=str(d["token_b64"]),
        )

    def _write_record(self, rec: VaultRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "version": rec.version,
                    "salt_b64": rec.salt_b64,
                    "iterations": rec.iterations,
                    "token_b64": rec.token_b64,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        # Best-effort private perms (0600)
        try:
            os.chmod(self.path, 0o600)
        except Exception:
            pass

    def unlock(self, password: str) -> Dict[str, Any]:
        rec = self._read_record()
        salt = base64.b64decode(rec.salt_b64.encode("ascii"))
        token = base64.b64decode(rec.token_b64.encode("ascii"))
        key = self._derive_key(password=password, salt=salt, iterations=rec.iterations)
        f = Fernet(key)
        try:
            raw = f.decrypt(token)
        except InvalidToken as e:
            raise ValueError("Invalid master password or corrupted vault") from e
        return json.loads(raw.decode("utf-8"))

    def save(self, password: str, payload: Dict[str, Any]) -> None:
        rec = self._read_record()
        salt = base64.b64decode(rec.salt_b64.encode("ascii"))
        key = self._derive_key(password=password, salt=salt, iterations=rec.iterations)
        f = Fernet(key)
        token = f.encrypt(json.dumps(payload).encode("utf-8"))
        new_rec = VaultRecord(
            version=rec.version,
            salt_b64=rec.salt_b64,
            iterations=rec.iterations,
            token_b64=base64.b64encode(token).decode("ascii"),
        )
        self._write_record(new_rec)


def get_broker_creds(payload: Dict[str, Any], broker_name: str) -> Dict[str, Any]:
    return dict((payload.get("brokers") or {}).get(broker_name.upper()) or {})


def set_broker_creds(payload: Dict[str, Any], broker_name: str, creds: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})
    brokers = dict(payload.get("brokers") or {})
    brokers[broker_name.upper()] = dict(creds or {})
    payload["brokers"] = brokers
    return payload


def get_telegram_creds(payload: Dict[str, Any]) -> Dict[str, Any]:
    return dict(payload.get("telegram") or {})


def set_telegram_creds(payload: Dict[str, Any], creds: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(payload or {})
    payload["telegram"] = dict(creds or {})
    return payload
"""

    # -------------------------
    # core/
    # -------------------------
    files[str(PROJECT_ROOT / "core" / "logging_config.py")] = r"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from config.paths import logs_dir


def configure_logging(level: int = logging.INFO) -> None:
    log_dir = logs_dir()
    log_path = log_dir / "platform.log"

    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(fmt)

    fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)

    root.addHandler(sh)
    root.addHandler(fh)
"""

    files[str(PROJECT_ROOT / "core" / "models.py")] = r"""
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
"""

    files[str(PROJECT_ROOT / "core" / "indicators.py")] = r"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


def sma(values: List[float], length: int) -> Optional[float]:
    if len(values) < length:
        return None
    return float(np.mean(values[-length:]))


def rsi(closes: List[float], length: int = 14) -> Optional[float]:
    if len(closes) < length + 1:
        return None
    deltas = np.diff(np.array(closes[-(length + 1) :], dtype=float))
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains.mean()
    avg_loss = losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def atr(highs: List[float], lows: List[float], closes: List[float], length: int = 14) -> Optional[float]:
    if len(closes) < length + 1 or len(highs) < length + 1 or len(lows) < length + 1:
        return None
    h = np.array(highs[-(length + 1) :], dtype=float)
    l = np.array(lows[-(length + 1) :], dtype=float)
    c = np.array(closes[-(length + 1) :], dtype=float)
    prev_close = c[:-1]
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - prev_close), np.abs(l[1:] - prev_close)))
    return float(np.mean(tr[-length:]))
"""

    files[str(PROJECT_ROOT / "core" / "strategy_camarilla.py")] = r"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

from core.indicators import sma, rsi, atr
from core.models import Side
from config.defaults import StrategySettings


@dataclass
class CamarillaLevels:
    h3: float
    h4: float
    l3: float
    l4: float
    pivot: float
    prev_close: float


def camarilla_from_prev_day(prev_high: float, prev_low: float, prev_close: float) -> CamarillaLevels:
    rng = (prev_high - prev_low)
    # Camarilla constants
    h3 = prev_close + (rng * 1.1 / 4.0)
    h4 = prev_close + (rng * 1.1 / 2.0)
    l3 = prev_close - (rng * 1.1 / 4.0)
    l4 = prev_close - (rng * 1.1 / 2.0)
    pivot = (prev_high + prev_low + prev_close) / 3.0
    return CamarillaLevels(h3=h3, h4=h4, l3=l3, l4=l4, pivot=pivot, prev_close=prev_close)


def _pct_diff(a: float, b: float) -> float:
    if b == 0:
        return 999.0
    return abs(a - b) / abs(b) * 100.0


def detect_bias(open_price: float, levels: CamarillaLevels, method: str) -> str:
    m = (method or "OPEN_VS_PIVOT").upper()
    if m == "OPEN_VS_PREVCLOSE":
        if open_price > levels.prev_close:
            return "BULL"
        if open_price < levels.prev_close:
            return "BEAR"
        return "NEUTRAL"
    # OPEN_VS_PIVOT
    if open_price > levels.pivot:
        return "BULL"
    if open_price < levels.pivot:
        return "BEAR"
    return "NEUTRAL"


def generate_signal(
    *,
    levels: CamarillaLevels,
    settings: StrategySettings,
    o: List[float],
    h: List[float],
    l: List[float],
    c: List[float],
    v: List[float],
    day_open: float,
) -> Tuple[Optional[Side], str]:
    '''
    Advanced Camarilla Strategy (5m candles):
    Mean Reversion:
      - BUY near L3 with confirmation
      - SELL near H3 with confirmation
    Breakout:
      - BUY above H4 with volume
      - SELL below L4 with momentum
    '''
    if len(c) < 3:
        return None, ""

    close = c[-1]
    open_ = o[-1]
    high = h[-1]
    low = l[-1]
    vol = v[-1] if v else 0.0

    bias = detect_bias(day_open, levels, settings.bias_method)

    r = rsi(c, settings.rsi_length)
    a = atr(h, l, c, settings.atr_length)
    vol_sma = sma(v, 20) if v else None

    # Safety: if volume missing, disable strict volume filters
    use_vol = bool(settings.use_volume_filters and vol_sma is not None and vol_sma > 0)

    # Mean reversion proximity
    near_l3 = _pct_diff(close, levels.l3) <= settings.price_tolerance_pct
    near_h3 = _pct_diff(close, levels.h3) <= settings.price_tolerance_pct

    bullish_confirm = close > open_ and (close - low) > (high - close)  # close in upper half
    bearish_confirm = close < open_ and (high - close) > (close - low)  # close in lower half

    vol_ok_confirm = (not use_vol) or (vol >= (vol_sma * settings.confirmation_volume_mult))
    vol_ok_break = (not use_vol) or (vol >= (vol_sma * settings.breakout_volume_mult))

    # Momentum proxy for breakdown: ATR must be meaningful and RSI must align
    atr_ok = True
    if a is not None and close > 0:
        atr_ok = (a / close * 100.0) >= settings.min_atr_pct

    # ---------------------------
    # Breakout rules (priority)
    # ---------------------------
    if close > levels.h4 and vol_ok_break and (r is None or r >= 52.0):
        if bias in ("BULL", "NEUTRAL"):
            return Side.BUY, "BREAKOUT_ABOVE_H4"
        # allow counter-bias breakout but label it
        return Side.BUY, "BREAKOUT_ABOVE_H4_COUNTER_BIAS"

    if close < levels.l4 and atr_ok and (r is None or r <= 48.0):
        if bias in ("BEAR", "NEUTRAL"):
            return Side.SELL, "BREAKDOWN_BELOW_L4"
        return Side.SELL, "BREAKDOWN_BELOW_L4_COUNTER_BIAS"

    # ---------------------------
    # Mean reversion rules
    # ---------------------------
    if near_l3 and bullish_confirm and vol_ok_confirm and (r is None or r <= 55.0):
        if bias in ("BULL", "NEUTRAL"):
            return Side.BUY, "MEAN_REVERT_BUY_L3"
        return Side.BUY, "MEAN_REVERT_BUY_L3_COUNTER_BIAS"

    if near_h3 and bearish_confirm and vol_ok_confirm and (r is None or r >= 45.0):
        if bias in ("BEAR", "NEUTRAL"):
            return Side.SELL, "MEAN_REVERT_SELL_H3"
        return Side.SELL, "MEAN_REVERT_SELL_H3_COUNTER_BIAS"

    return None, ""
"""

    files[str(PROJECT_ROOT / "core" / "risk.py")] = r"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from core.models import Side
from config.defaults import RiskSettings


@dataclass
class RiskState:
    trades_today: int = 0
    realized_pnl_today: float = 0.0
    daily_loss_hit: bool = False
    kill_switch: bool = False


def compute_position_qty(
    *,
    capital: float,
    max_risk_pct: float,
    entry: float,
    stop: float,
    lot_size: int = 1,
) -> int:
    risk_amt = max(0.0, capital * (max_risk_pct / 100.0))
    per_unit_risk = abs(entry - stop)
    if per_unit_risk <= 0:
        return 0
    raw_qty = int(risk_amt // per_unit_risk)
    if raw_qty <= 0:
        return 0
    # Round down to lot size
    qty = (raw_qty // max(1, lot_size)) * max(1, lot_size)
    return max(0, qty)


def should_allow_new_trade(risk: RiskSettings, state: RiskState) -> Tuple[bool, str]:
    if state.kill_switch or risk.kill_switch:
        return False, "KILL_SWITCH"
    if state.trades_today >= risk.max_trades_per_day:
        return False, "MAX_TRADES_PER_DAY"
    if state.daily_loss_hit and not risk.allow_new_trades_after_daily_loss_hit:
        return False, "DAILY_LOSS_LIMIT_HIT"
    return True, ""


def update_daily_loss_flag(risk: RiskSettings, state: RiskState) -> None:
    limit = abs(risk.capital * (risk.daily_loss_limit_pct / 100.0))
    if state.realized_pnl_today <= -limit:
        state.daily_loss_hit = True
"""

    files[str(PROJECT_ROOT / "core" / "telegram.py")] = r"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Optional

import requests


log = logging.getLogger("telegram")


class TelegramClient:
    def __init__(self, bot_token: str, chat_id: str, poll_interval_sec: float = 2.0):
        self.bot_token = bot_token.strip()
        self.chat_id = str(chat_id).strip()
        self.poll_interval_sec = float(poll_interval_sec)
        self._base = f"https://api.telegram.org/bot{self.bot_token}"
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._offset: Optional[int] = None

    def send(self, text: str) -> None:
        if not self.bot_token or not self.chat_id:
            return
        try:
            requests.post(
                f"{self._base}/sendMessage",
                json={"chat_id": self.chat_id, "text": text},
                timeout=10,
            ).raise_for_status()
        except Exception as e:
            log.warning("Telegram send failed: %s", e)

    def start_kill_switch_listener(self, on_stop: Callable[[], None]) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._poll_loop, args=(on_stop,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()

    def _poll_loop(self, on_stop: Callable[[], None]) -> None:
        if not self.bot_token:
            return
        while not self._stop_evt.is_set():
            try:
                params = {"timeout": 0}
                if self._offset is not None:
                    params["offset"] = self._offset
                r = requests.get(f"{self._base}/getUpdates", params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
                for upd in data.get("result", []):
                    self._offset = int(upd["update_id"]) + 1
                    msg = (upd.get("message") or {}).get("text") or ""
                    chat = (upd.get("message") or {}).get("chat") or {}
                    chat_id = str(chat.get("id") or "")
                    if chat_id != self.chat_id:
                        continue
                    if msg.strip().upper() == "STOP":
                        log.warning("Telegram STOP received. Triggering kill switch.")
                        try:
                            on_stop()
                        except Exception as e:
                            log.exception("Kill switch handler failed: %s", e)
            except Exception as e:
                log.warning("Telegram poll error: %s", e)
            time.sleep(self.poll_interval_sec)
"""

    files[str(PROJECT_ROOT / "core" / "time_utils.py")] = r"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, Optional

import pytz


IST = pytz.timezone("Asia/Kolkata")


def now_ist() -> dt.datetime:
    return dt.datetime.now(tz=IST)


def to_ist(ts: dt.datetime) -> dt.datetime:
    if ts.tzinfo is None:
        return IST.localize(ts)
    return ts.astimezone(IST)


def floor_time(ts: dt.datetime, minutes: int) -> dt.datetime:
    ts = to_ist(ts)
    discard = dt.timedelta(minutes=ts.minute % minutes, seconds=ts.second, microseconds=ts.microsecond)
    return ts - discard


def next_weekly_expiry(base: dt.date, weekday: int = 3) -> dt.date:
    '''
    Weekly expiry default: Thursday (weekday=3).
    If today is after expiry weekday, move to next week.
    '''
    days_ahead = (weekday - base.weekday()) % 7
    expiry = base + dt.timedelta(days=days_ahead)
    if expiry < base:
        expiry = expiry + dt.timedelta(days=7)
    return expiry


def format_nfo_expiry(expiry: dt.date) -> str:
    # Standard broker symbol formats vary; resolver adapts.
    return expiry.strftime("%y%m%d")
"""

    files[str(PROJECT_ROOT / "core" / "instruments.py")] = r"""
from __future__ import annotations

import csv
import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from config.paths import data_dir
from config.defaults import Segment, OptionsSettings
from core.time_utils import next_weekly_expiry

log = logging.getLogger("instruments")


@dataclass
class Instrument:
    exchange: str
    tradingsymbol: str
    token: str
    name: str = ""
    segment: str = ""
    instrument_type: str = ""
    expiry: Optional[dt.date] = None
    strike: Optional[float] = None
    lot_size: int = 1


class InstrumentCache:
    '''
    Local instrument cache. For live trading, users should refresh these from their broker.
    The platform can operate without full masters in PAPER/backtest mode.
    '''

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (data_dir() / "instruments_master.csv")

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> pd.DataFrame:
        if not self.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(self.path)
            return df
        except Exception as e:
            log.warning("Failed to load instruments master: %s", e)
            return pd.DataFrame()

    def save(self, df: pd.DataFrame) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.path, index=False)


def round_to_step(price: float, step: int) -> int:
    if step <= 0:
        return int(round(price))
    return int(round(price / step) * step)


def select_atm_option_symbol(
    *,
    underlying: str,
    ltp: float,
    side: str,
    segment: Segment,
    options: OptionsSettings,
    instruments_df: Optional[pd.DataFrame] = None,
    asof_date: Optional[dt.date] = None,
) -> Tuple[str, int]:
    '''
    Returns (tradingsymbol, lot_size). Uses local master if available, otherwise builds a common NFO-style symbol.
    - CE for BUY signals
    - PE for SELL signals
    '''
    side = side.upper()
    is_call = side == "BUY"
    opt_type = "CE" if is_call else "PE"
    asof = asof_date or dt.date.today()

    expiry = next_weekly_expiry(asof, weekday=3)  # Thursday
    step = int(options.index_strike_steps.get(underlying.upper(), 50))
    strike = round_to_step(ltp, step)

    # If we have instruments master, choose the closest match.
    if instruments_df is not None and not instruments_df.empty:
        df = instruments_df.copy()
        # Normalize columns if present
        cols = {c.lower(): c for c in df.columns}
        sym_col = cols.get("tradingsymbol") or cols.get("symbol") or cols.get("trading_symbol")
        name_col = cols.get("name") or cols.get("underlying")
        exp_col = cols.get("expiry") or cols.get("expiry_date")
        strike_col = cols.get("strike") or cols.get("strike_price")
        type_col = cols.get("instrument_type") or cols.get("option_type")
        lot_col = cols.get("lot_size") or cols.get("lotsize") or cols.get("lot")

        if sym_col and name_col and exp_col and strike_col and type_col:
            try:
                df["_exp"] = pd.to_datetime(df[exp_col], errors="coerce").dt.date
                df["_strike"] = pd.to_numeric(df[strike_col], errors="coerce")
                df["_type"] = df[type_col].astype(str).str.upper()
                df["_name"] = df[name_col].astype(str).str.upper()
                cand = df[
                    (df["_name"] == underlying.upper())
                    & (df["_exp"] == expiry)
                    & (df["_type"] == opt_type)
                ].copy()
                if not cand.empty:
                    cand["_dist"] = (cand["_strike"] - strike).abs()
                    cand = cand.sort_values(["_dist"])
                    row = cand.iloc[0]
                    lot = int(row[lot_col]) if lot_col and str(row.get(lot_col, "")).strip() != "" else 1
                    return str(row[sym_col]), lot
            except Exception:
                pass

    # Fallback: best-effort common format (varies by broker). Broker adapters may transform further.
    # Example style: NIFTY 25DEC 20000 CE -> often broker-specific. We'll use YYMMDD in symbol as neutral.
    exp_tag = expiry.strftime("%y%m%d")
    tradingsymbol = f"{underlying.upper()}{exp_tag}{strike}{opt_type}"
    return tradingsymbol, 1
"""

    files[str(PROJECT_ROOT / "core" / "execution.py")] = r"""
from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, List, Tuple

import pandas as pd

from brokers.base import Broker
from core.models import Side, Trade, Order
from core.risk import RiskState, should_allow_new_trade, update_daily_loss_flag, compute_position_qty
from core.strategy_camarilla import camarilla_from_prev_day, generate_signal, CamarillaLevels
from core.time_utils import IST, now_ist
from core.instruments import InstrumentCache, select_atm_option_symbol
from config.defaults import AppSettings, Segment

log = logging.getLogger("engine")


@dataclass
class SymbolContext:
    symbol: str
    segment: Segment
    levels: Optional[CamarillaLevels] = None
    day_open: Optional[float] = None
    candles_o: List[float] = None
    candles_h: List[float] = None
    candles_l: List[float] = None
    candles_c: List[float] = None
    candles_v: List[float] = None
    active_trade: Optional[Trade] = None

    def __post_init__(self):
        self.candles_o = self.candles_o or []
        self.candles_h = self.candles_h or []
        self.candles_l = self.candles_l or []
        self.candles_c = self.candles_c or []
        self.candles_v = self.candles_v or []


class AlgoEngine:
    '''
    Event-driven engine:
      - Receives completed 5m candles (from websocket tick aggregator or backtest feed)
      - Computes signals (Advanced Camarilla)
      - Applies risk controls
      - Places/cancels via Broker abstraction
    '''

    def __init__(
        self,
        broker: Broker,
        settings: AppSettings,
        on_status: Optional[Callable[[str], None]] = None,
        on_ltp: Optional[Callable[[str, float], None]] = None,
        on_pnl: Optional[Callable[[float, float], None]] = None,
    ):
        self.broker = broker
        self.settings = settings
        self.on_status = on_status
        self.on_ltp = on_ltp
        self.on_pnl = on_pnl

        self._stop_evt = threading.Event()
        self._lock = threading.RLock()
        self._risk_state = RiskState()
        self._contexts: Dict[str, SymbolContext] = {}
        self._instrument_cache = InstrumentCache()
        self._instruments_df = self._instrument_cache.load()

        self._unrealized = 0.0
        self._realized = 0.0

    def start(self) -> None:
        self._stop_evt.clear()
        self._risk_state.kill_switch = False
        self._risk_state.daily_loss_hit = False
        self._risk_state.trades_today = 0
        self._risk_state.realized_pnl_today = 0.0
        self._unrealized = 0.0
        self._realized = 0.0

        with self._lock:
            self._contexts = {sym: SymbolContext(symbol=sym, segment=self.settings.segment) for sym in self.settings.symbols}

        self._emit_status("ENGINE_STARTED")

    def stop(self) -> None:
        self._stop_evt.set()
        self._emit_status("ENGINE_STOPPING")

    def kill(self) -> None:
        with self._lock:
            self._risk_state.kill_switch = True
        self._emit_status("KILL_SWITCH_ON - Cancelling orders and stopping")
        try:
            self.broker.cancel_all_orders()
        except Exception as e:
            log.warning("Cancel all failed: %s", e)
        self.stop()

    def is_running(self) -> bool:
        return not self._stop_evt.is_set()

    def _emit_status(self, msg: str) -> None:
        log.info(msg)
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                pass

    def _emit_ltp(self, symbol: str, ltp: float) -> None:
        if self.on_ltp:
            try:
                self.on_ltp(symbol, ltp)
            except Exception:
                pass

    def _emit_pnl(self) -> None:
        if self.on_pnl:
            try:
                self.on_pnl(self._realized, self._unrealized)
            except Exception:
                pass

    def on_tick(self, symbol: str, ltp: float) -> None:
        self._emit_ltp(symbol, ltp)
        # unrealized PnL update if trade active
        with self._lock:
            ctx = self._contexts.get(symbol)
            if not ctx or not ctx.active_trade or not ctx.active_trade.active:
                return
            t = ctx.active_trade
            if t.side == Side.BUY:
                self._unrealized = (ltp - t.entry_price) * t.qty
            else:
                self._unrealized = (t.entry_price - ltp) * t.qty
        self._emit_pnl()

    def prime_prev_day_levels(self, symbol: str) -> None:
        '''
        Compute Camarilla from previous day OHLC using broker historical candles if available.
        '''
        end = now_ist().date()
        start = end - dt.timedelta(days=7)
        df = self.broker.get_historical_ohlcv(symbol=symbol, segment=self.settings.segment, start=start, end=end, interval_minutes=5)
        if df is None or df.empty:
            raise RuntimeError("Cannot fetch historical candles for levels. Provide instruments/credentials or use backtest/paper.")
        df = df.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        # compute previous trading day from last complete day
        df["date"] = df["timestamp"].dt.date
        last_date = df["date"].max()
        prev_date = sorted([d for d in df["date"].unique() if d < last_date])[-1]
        prev = df[df["date"] == prev_date]
        prev_high = float(prev["high"].max())
        prev_low = float(prev["low"].min())
        prev_close = float(prev.sort_values("timestamp")["close"].iloc[-1])

        levels = camarilla_from_prev_day(prev_high, prev_low, prev_close)

        today = df[df["date"] == last_date].sort_values("timestamp")
        day_open = float(today["open"].iloc[0]) if not today.empty else prev_close

        with self._lock:
            ctx = self._contexts[symbol]
            ctx.levels = levels
            ctx.day_open = day_open

        self._emit_status(f"{symbol}: Levels primed H3={levels.h3:.2f} H4={levels.h4:.2f} L3={levels.l3:.2f} L4={levels.l4:.2f} BiasOpen={day_open:.2f}")

    def on_candle_close(self, symbol: str, candle: Dict[str, float], ts_epoch: float) -> None:
        '''
        Candle dict: open/high/low/close/volume
        '''
        if self._stop_evt.is_set():
            return
        with self._lock:
            ctx = self._contexts.get(symbol)
            if not ctx:
                return
            if ctx.levels is None or ctx.day_open is None:
                # lazy prime; for live this will fetch historical once per symbol
                pass

        if ctx.levels is None or ctx.day_open is None:
            self.prime_prev_day_levels(symbol)

        with self._lock:
            ctx = self._contexts[symbol]
            ctx.candles_o.append(float(candle["open"]))
            ctx.candles_h.append(float(candle["high"]))
            ctx.candles_l.append(float(candle["low"]))
            ctx.candles_c.append(float(candle["close"]))
            ctx.candles_v.append(float(candle.get("volume", 0.0)))

        self._evaluate_and_trade(symbol=symbol, ts_epoch=ts_epoch)
        self._check_exit(symbol=symbol, ltp=float(candle["close"]), ts_epoch=ts_epoch)

    def _evaluate_and_trade(self, symbol: str, ts_epoch: float) -> None:
        with self._lock:
            ctx = self._contexts[symbol]
            # Hard rule: one active trade per symbol
            if self.settings.risk.one_active_trade_per_symbol and ctx.active_trade and ctx.active_trade.active:
                return

            allow, reason = should_allow_new_trade(self.settings.risk, self._risk_state)
            if not allow:
                return

            side, sig_reason = generate_signal(
                levels=ctx.levels,
                settings=self.settings.strategy,
                o=ctx.candles_o,
                h=ctx.candles_h,
                l=ctx.candles_l,
                c=ctx.candles_c,
                v=ctx.candles_v,
                day_open=ctx.day_open,
            )
            if side is None:
                return

            entry = ctx.candles_c[-1]
            # Stop/target: based on Camarilla levels (structured) + a buffer
            if side == Side.BUY:
                stop = min(ctx.levels.l4, ctx.candles_l[-1])  # breakdown invalidation
                target = ctx.levels.h3
            else:
                stop = max(ctx.levels.h4, ctx.candles_h[-1])
                target = ctx.levels.l3

            lot = 1
            order_symbol = symbol
            if self.settings.options.enabled and self.settings.segment == Segment.NSE_FNO:
                # execute on options for F&O indices/stocks (common use)
                opt_sym, lot_sz = select_atm_option_symbol(
                    underlying=symbol,
                    ltp=entry,
                    side=side.value,
                    segment=self.settings.segment,
                    options=self.settings.options,
                    instruments_df=self._instruments_df,
                    asof_date=now_ist().date(),
                )
                order_symbol = opt_sym
                lot = max(1, int(lot_sz))

            qty = compute_position_qty(
                capital=float(self.settings.risk.capital),
                max_risk_pct=float(self.settings.risk.max_risk_per_trade_pct),
                entry=float(entry),
                stop=float(stop),
                lot_size=lot,
            )
            if qty <= 0:
                self._emit_status(f"{symbol}: Signal {sig_reason} but qty=0 (risk sizing).")
                return

            # Place order
            o = Order(
                symbol=order_symbol,
                side=side,
                qty=qty,
                order_type=self.settings.options.order_type if self.settings.options.enabled else "MARKET",
                product=self.settings.options.product if self.settings.options.enabled else "MIS",
                tag="ADV_CAMARILLA",
                meta={"underlying": symbol, "signal": sig_reason},
            )

        # broker call outside lock
        try:
            fill_price = self.broker.place_order(o)
        except Exception as e:
            self._emit_status(f"ORDER_FAILED {symbol}: {e}")
            return

        with self._lock:
            trade = Trade(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=float(fill_price),
                entry_time=float(ts_epoch),
                stop_loss=float(stop),
                target=float(target),
                reason=sig_reason,
                meta={"exec_symbol": o.symbol},
            )
            ctx = self._contexts[symbol]
            ctx.active_trade = trade
            self._risk_state.trades_today += 1
            self._emit_status(f"ENTER {symbol} {side.value} qty={qty} at {fill_price:.2f} SL={stop:.2f} TG={target:.2f} ({sig_reason})")

    def _check_exit(self, symbol: str, ltp: float, ts_epoch: float) -> None:
        with self._lock:
            ctx = self._contexts.get(symbol)
            if not ctx or not ctx.active_trade or not ctx.active_trade.active:
                return
            t = ctx.active_trade
            hit_sl = (ltp <= t.stop_loss) if t.side == Side.BUY else (ltp >= t.stop_loss)
            hit_tg = (ltp >= t.target) if t.side == Side.BUY else (ltp <= t.target)
            if not (hit_sl or hit_tg):
                return
            reason = "STOP_LOSS" if hit_sl else "TARGET"
            exit_price = float(ltp)

        # Try to exit via broker (market)
        try:
            self.broker.exit_position(symbol=t.meta.get("exec_symbol") or symbol, side=t.side, qty=t.qty, product=self.settings.options.product)
        except Exception as e:
            log.warning("Exit order failed (will still mark trade closed): %s", e)

        with self._lock:
            ctx = self._contexts[symbol]
            t = ctx.active_trade
            t.close(price=exit_price, ts=ts_epoch, reason=reason)
            self._realized += t.pnl
            self._risk_state.realized_pnl_today = self._realized
            update_daily_loss_flag(self.settings.risk, self._risk_state)
            self._unrealized = 0.0
            self._emit_status(f"EXIT {symbol} {t.side.value} pnl={t.pnl:.2f} reason={reason} total_realized={self._realized:.2f}")
        self._emit_pnl()

    def get_status_snapshot(self) -> Dict[str, str]:
        with self._lock:
            lines = {}
            for sym, ctx in self._contexts.items():
                if ctx.active_trade and ctx.active_trade.active:
                    t = ctx.active_trade
                    lines[sym] = f"IN_TRADE {t.side.value} qty={t.qty} entry={t.entry_price:.2f} SL={t.stop_loss:.2f} TG={t.target:.2f}"
                else:
                    lines[sym] = "FLAT"
            return lines
"""

    # -------------------------
    # brokers/
    # -------------------------
    files[str(PROJECT_ROOT / "brokers" / "base.py")] = r"""
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
"""

    files[str(PROJECT_ROOT / "brokers" / "paper.py")] = r"""
from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.paper")


class PaperBroker(Broker):
    name = "PAPER"

    def __init__(self):
        self._logged_in = True
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._subs: set[str] = set()
        self._ltp: Dict[str, float] = {}
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return True

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        self._on_tick = on_tick

    def subscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.add(symbol)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.discard(symbol)

    def disconnect_marketdata(self) -> None:
        self._on_tick = None

    def set_ltp(self, symbol: str, ltp: float) -> None:
        with self._lock:
            self._ltp[symbol] = float(ltp)
            cb = self._on_tick
        if cb and symbol in self._subs:
            cb(symbol, float(ltp), {"mode": "PAPER"})

    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        # Paper broker doesn't provide market history; use CSV backtest for history.
        return pd.DataFrame()

    def place_order(self, order: Order) -> float:
        # Fill at last known LTP; if absent, use 0 and still be consistent.
        with self._lock:
            px = float(self._ltp.get(order.symbol) or self._ltp.get(order.meta.get("underlying", "")) or 0.0)
        order.broker_order_id = f"PAPER-{int(time.time()*1000)}"
        return px

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        return

    def cancel_all_orders(self) -> None:
        return
"""

    files[str(PROJECT_ROOT / "brokers" / "zerodha.py")] = r"""
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
"""

    files[str(PROJECT_ROOT / "brokers" / "angelone.py")] = r"""
from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.angelone")


class AngelOneBroker(Broker):
    name = "ANGELONE"

    def __init__(self):
        self._api = None
        self._ws = None
        self._logged_in = False
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._subs: set[str] = set()
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        try:
            from SmartApi import SmartConnect
        except Exception as e:
            raise RuntimeError("smartapi-python not installed. Install requirements and retry.") from e
        api_key = creds.get("api_key") or creds.get("API_KEY")
        client_code = creds.get("client_code") or creds.get("CLIENT_CODE")
        password = creds.get("password") or creds.get("PASSWORD")
        totp = creds.get("totp") or creds.get("TOTP")  # optional
        if not api_key or not client_code or not password:
            raise ValueError("Angel One requires api_key, client_code, password (and optionally totp) in vault.")
        api = SmartConnect(api_key=str(api_key))
        sess = api.generateSession(str(client_code), str(password), str(totp) if totp else None)
        if not sess or not sess.get("status"):
            raise RuntimeError(f"Angel One login failed: {sess}")
        self._api = api
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return bool(self._logged_in)

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        if not self._api:
            raise RuntimeError("Not logged in.")
        self._on_tick = on_tick
        try:
            # SmartWebSocketV2 is used in newer versions
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2
        except Exception as e:
            raise RuntimeError("Angel websocket class not available in your smartapi-python version.") from e

        feed_token = self._api.getfeedToken()
        auth = self._api.getAccessToken()
        client_code = self._api.userId
        ws = SmartWebSocketV2(auth, api_key=self._api.api_key, client_code=client_code, feed_token=feed_token)

        def on_data(wsapp, message):
            # Message structure differs; handle best-effort
            try:
                sym = message.get("tradingsymbol") or message.get("symbol") or ""
                ltp = float(message.get("last_traded_price") or message.get("ltp") or 0.0)
                if sym and self._on_tick:
                    self._on_tick(sym, ltp, message)
            except Exception:
                return

        def on_open(wsapp):
            log.info("Angel websocket opened")
            # Subscriptions should be done via subscribe() calls

        def on_error(wsapp, error):
            log.warning("Angel websocket error: %s", error)

        def on_close(wsapp):
            log.warning("Angel websocket closed")

        ws.on_data = on_data
        ws.on_open = on_open
        ws.on_error = on_error
        ws.on_close = on_close

        self._ws = ws
        th = threading.Thread(target=ws.connect, daemon=True)
        th.start()

    def subscribe(self, symbol: str, segment: Segment) -> None:
        if not self._ws:
            with self._lock:
                self._subs.add(symbol)
            return
        with self._lock:
            self._subs.add(symbol)
        # SmartAPI subscription requires tokens; you should use scrip master.
        # To keep system executable, we allow raw symbol subscription best-effort if supported by installed SDK.
        try:
            # Some builds support subscribe with a dict payload
            self._ws.subscribe(correlation_id="cam", mode=1, token_list=[{"exchangeType": 1, "tokens": [symbol]}])
        except Exception as e:
            log.warning("Angel subscribe failed for %s (needs token mapping): %s", symbol, e)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.discard(symbol)

    def disconnect_marketdata(self) -> None:
        if self._ws:
            try:
                self._ws.close_connection()
            except Exception:
                pass
        self._ws = None

    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        if not self._api:
            raise RuntimeError("Not logged in.")
        # Angel historical data requires token + exchange mapping. For production you should load scrip master.
        raise RuntimeError("Angel One historical OHLCV requires token mapping (scrip master). Load instruments and implement resolver for your account.")

    def place_order(self, order: Order) -> float:
        if not self._api:
            raise RuntimeError("Not logged in.")
        txn = "BUY" if order.side.value == "BUY" else "SELL"
        payload = {
            "variety": "NORMAL",
            "tradingsymbol": order.symbol,
            "symboltoken": order.meta.get("token") or order.symbol,
            "transactiontype": txn,
            "exchange": order.meta.get("exchange") or "NSE",
            "ordertype": order.order_type,
            "producttype": order.product,
            "duration": "DAY",
            "price": "0",
            "quantity": str(int(order.qty)),
        }
        r = self._api.placeOrder(payload)
        if not r or not r.get("status"):
            raise RuntimeError(f"Angel placeOrder failed: {r}")
        order.broker_order_id = str(r.get("data") or "")
        return 0.0

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        # Place opposite market order (requires token mapping in meta for precise execution)
        o = Order(symbol=symbol, side=Side.SELL if side == Side.BUY else Side.BUY, qty=qty, order_type="MARKET", product=product)
        self.place_order(o)

    def cancel_all_orders(self) -> None:
        # SmartAPI supports orderbook; cancelling open orders is account dependent
        try:
            ob = self._api.orderBook()
            for o in (ob.get("data") or []):
                if str(o.get("orderstatus", "")).upper() in ("OPEN", "TRIGGER PENDING"):
                    self._api.cancelOrder(o.get("orderid"))
        except Exception as e:
            log.warning("Cancel all orders failed: %s", e)
"""

    files[str(PROJECT_ROOT / "brokers" / "aliceblue.py")] = r"""
from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.aliceblue")


class AliceBlueBroker(Broker):
    name = "ALICEBLUE"

    def __init__(self):
        self._api = None
        self._logged_in = False
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._subs: set[str] = set()
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        try:
            from pya3 import Aliceblue
        except Exception as e:
            raise RuntimeError("pya3 not installed. Install requirements and retry.") from e
        user_id = creds.get("user_id") or creds.get("USER_ID")
        api_key = creds.get("api_key") or creds.get("API_KEY")
        if not user_id or not api_key:
            raise ValueError("AliceBlue requires user_id and api_key in vault.")
        api = Aliceblue(user_id=str(user_id), api_key=str(api_key))
        self._api = api
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return bool(self._logged_in)

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        if not self._api:
            raise RuntimeError("Not logged in.")
        self._on_tick = on_tick
        # AliceBlue websocket is supported via start_websocket in pya3
        def socket_open():
            log.info("AliceBlue websocket opened")

        def socket_close():
            log.warning("AliceBlue websocket closed")

        def socket_error(msg):
            log.warning("AliceBlue websocket error: %s", msg)

        def feed_data(message):
            try:
                sym = message.get("tk") or message.get("ts") or ""
                ltp = float(message.get("lp") or 0.0)
                if sym and self._on_tick:
                    self._on_tick(sym, ltp, message)
            except Exception:
                pass

        try:
            self._api.start_websocket(
                socket_open_callback=socket_open,
                socket_close_callback=socket_close,
                socket_error_callback=socket_error,
                subscription_callback=feed_data,
                run_in_background=True,
            )
        except Exception as e:
            raise RuntimeError(f"AliceBlue websocket start failed: {e}") from e

    def subscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.add(symbol)
        # Subscription in AliceBlue typically needs contract objects; keep executable with best-effort
        try:
            self._api.subscribe([symbol])
        except Exception as e:
            log.warning("AliceBlue subscribe failed for %s (needs contract mapping): %s", symbol, e)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.discard(symbol)
        try:
            self._api.unsubscribe([symbol])
        except Exception:
            pass

    def disconnect_marketdata(self) -> None:
        try:
            if self._api:
                self._api.stop_websocket()
        except Exception:
            pass

    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        raise RuntimeError("AliceBlue historical OHLCV requires instrument mapping specific to your account/contracts.")

    def place_order(self, order: Order) -> float:
        if not self._api:
            raise RuntimeError("Not logged in.")
        # Requires contract object; keep as explicit error unless user wires instrument resolver.
        raise RuntimeError("AliceBlue order placement requires contract object mapping (see pya3 docs).")

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        raise RuntimeError("AliceBlue exit requires contract mapping.")

    def cancel_all_orders(self) -> None:
        try:
            if self._api:
                self._api.cancel_all_orders()
        except Exception:
            pass
"""

    files[str(PROJECT_ROOT / "brokers" / "shoonya.py")] = r"""
from __future__ import annotations

import datetime as dt
import logging
import threading
from typing import Any, Callable, Dict, Optional

import pandas as pd

from brokers.base import Broker
from config.defaults import Segment
from core.models import Order, Side

log = logging.getLogger("broker.shoonya")


class ShoonyaBroker(Broker):
    name = "SHOONYA"

    def __init__(self):
        self._api = None
        self._logged_in = False
        self._on_tick: Optional[Callable[[str, float, Dict[str, Any]], None]] = None
        self._subs: set[str] = set()
        self._lock = threading.RLock()

    def login(self, creds: Dict[str, Any]) -> None:
        try:
            from NorenRestApiPy.NorenApi import NorenApi
        except Exception as e:
            raise RuntimeError("NorenRestApiPy not installed. Install requirements and retry.") from e

        class _Api(NorenApi):
            def __init__(self):
                super().__init__(host="https://api.shoonya.com/NorenWClientTP/", websocket="wss://api.shoonya.com/NorenWSTP/")

        uid = creds.get("user_id") or creds.get("USER_ID")
        pwd = creds.get("password") or creds.get("PASSWORD")
        factor2 = creds.get("factor2") or creds.get("FACTOR2")  # TOTP/2FA
        vc = creds.get("vendor_code") or creds.get("VENDOR_CODE")
        app_key = creds.get("app_key") or creds.get("APP_KEY")
        imei = creds.get("imei") or creds.get("IMEI") or "1234567890"

        if not uid or not pwd or not factor2 or not vc or not app_key:
            raise ValueError("Shoonya requires user_id,password,factor2,vendor_code,app_key (and imei optional).")

        api = _Api()
        r = api.login(userid=str(uid), password=str(pwd), twoFA=str(factor2), vendor_code=str(vc), api_secret=str(app_key), imei=str(imei))
        if not r or r.get("stat") != "Ok":
            raise RuntimeError(f"Shoonya login failed: {r}")
        self._api = api
        self._logged_in = True

    def is_logged_in(self) -> bool:
        return bool(self._logged_in)

    def connect_marketdata(self, on_tick: Callable[[str, float, Dict[str, Any]], None]) -> None:
        if not self._api:
            raise RuntimeError("Not logged in.")
        self._on_tick = on_tick

        def event_handler_order_update(msg):
            return

        def event_handler_feed_update(tick):
            try:
                sym = tick.get("ts") or ""
                ltp = float(tick.get("lp") or 0.0)
                if sym and self._on_tick:
                    self._on_tick(sym, ltp, tick)
            except Exception:
                pass

        def open_callback():
            log.info("Shoonya websocket opened")
            # Subscriptions happen via subscribe()

        try:
            self._api.start_websocket(
                order_update_callback=event_handler_order_update,
                subscribe_callback=event_handler_feed_update,
                socket_open_callback=open_callback,
            )
        except Exception as e:
            raise RuntimeError(f"Shoonya websocket start failed: {e}") from e

    def subscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.add(symbol)
        # Shoonya subscription requires exch and token; keep executable with best-effort if user provides correct symbol format.
        try:
            # Accept format: "NSE|26000" (exch|token) commonly used in examples
            self._api.subscribe(symbol)
        except Exception as e:
            log.warning("Shoonya subscribe failed for %s (needs exch|token): %s", symbol, e)

    def unsubscribe(self, symbol: str, segment: Segment) -> None:
        with self._lock:
            self._subs.discard(symbol)
        try:
            self._api.unsubscribe(symbol)
        except Exception:
            pass

    def disconnect_marketdata(self) -> None:
        try:
            if self._api:
                self._api.close_websocket()
        except Exception:
            pass

    def get_historical_ohlcv(
        self,
        symbol: str,
        segment: Segment,
        start: dt.date,
        end: dt.date,
        interval_minutes: int,
    ) -> pd.DataFrame:
        raise RuntimeError("Shoonya historical OHLCV requires token mapping.")

    def place_order(self, order: Order) -> float:
        if not self._api:
            raise RuntimeError("Not logged in.")
        # Shoonya order requires exch, tradingsymbol, qty, buy/sell etc. User must provide token/exchange mapping.
        raise RuntimeError("Shoonya order placement requires exchange/token mapping specific to contract.")

    def exit_position(self, symbol: str, side: Side, qty: int, product: str) -> None:
        raise RuntimeError("Shoonya exit requires exchange/token mapping.")

    def cancel_all_orders(self) -> None:
        try:
            if self._api:
                ob = self._api.get_order_book()
                for o in (ob or []):
                    if str(o.get("status", "")).upper() in ("OPEN", "TRIGGER_PENDING"):
                        self._api.cancel_order(o.get("norenordno"))
        except Exception as e:
            log.warning("Cancel all orders failed: %s", e)
"""

    files[str(PROJECT_ROOT / "brokers" / "factory.py")] = r"""
from __future__ import annotations

from config.defaults import BrokerName
from brokers.paper import PaperBroker
from brokers.zerodha import ZerodhaBroker
from brokers.angelone import AngelOneBroker
from brokers.aliceblue import AliceBlueBroker
from brokers.shoonya import ShoonyaBroker


def create_broker(name: BrokerName):
    n = (name.value if hasattr(name, "value") else str(name)).upper()
    if n == "PAPER":
        return PaperBroker()
    if n == "ZERODHA":
        return ZerodhaBroker()
    if n == "ANGELONE":
        return AngelOneBroker()
    if n == "ALICEBLUE":
        return AliceBlueBroker()
    if n == "SHOONYA":
        return ShoonyaBroker()
    raise ValueError(f"Unknown broker: {name}")
"""

    # -------------------------
    # websocket/
    # -------------------------
    files[str(PROJECT_ROOT / "websocket" / "candle_aggregator.py")] = r"""
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
"""

    files[str(PROJECT_ROOT / "websocket" / "manager.py")] = r"""
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
"""

    # -------------------------
    # backtest/
    # -------------------------
    files[str(PROJECT_ROOT / "backtest" / "metrics.py")] = r"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BacktestReport:
    net_pnl: float
    win_rate: float
    max_drawdown: float
    trade_count: int
    equity_curve: List[float]

    def to_text(self) -> str:
        return (
            f"Net P&L: {self.net_pnl:.2f}\n"
            f"Win rate: {self.win_rate:.2f}%\n"
            f"Max drawdown: {self.max_drawdown:.2f}\n"
            f"Trades: {self.trade_count}\n"
        )


def compute_drawdown(equity: List[float]) -> float:
    peak = float("-inf")
    max_dd = 0.0
    for x in equity:
        peak = max(peak, x)
        dd = peak - x
        max_dd = max(max_dd, dd)
    return float(max_dd)
"""

    files[str(PROJECT_ROOT / "backtest" / "engine.py")] = r"""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from backtest.metrics import BacktestReport, compute_drawdown
from config.defaults import AppSettings, Segment
from core.strategy_camarilla import camarilla_from_prev_day, generate_signal
from core.models import Side, Trade
from core.risk import compute_position_qty

log = logging.getLogger("backtest")


def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    need = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing columns: {missing}. Required: {need}")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    return df


def run_csv_backtest(csv_path: Path, symbol: str, segment: Segment, settings: AppSettings) -> BacktestReport:
    df = pd.read_csv(csv_path)
    df = _ensure_cols(df)
    df["date"] = df["timestamp"].dt.date

    trades: List[Trade] = []
    equity = [0.0]
    realized = 0.0
    active: Optional[Trade] = None

    # Rolling arrays for indicators
    o: List[float] = []
    h: List[float] = []
    l: List[float] = []
    c: List[float] = []
    v: List[float] = []

    for day in sorted(df["date"].unique()):
        day_df = df[df["date"] == day].copy()
        prev_days = sorted([d for d in df["date"].unique() if d < day])
        if not prev_days:
            continue
        prev_day = prev_days[-1]
        prev_df = df[df["date"] == prev_day]
        prev_high = float(prev_df["high"].max())
        prev_low = float(prev_df["low"].min())
        prev_close = float(prev_df.sort_values("timestamp")["close"].iloc[-1])
        levels = camarilla_from_prev_day(prev_high, prev_low, prev_close)
        day_open = float(day_df.sort_values("timestamp")["open"].iloc[0])

        # reset candle series each day (cleaner, strategy is day-based with prev OHLC)
        o.clear(); h.clear(); l.clear(); c.clear(); v.clear()

        for _, row in day_df.iterrows():
            o.append(float(row["open"]))
            h.append(float(row["high"]))
            l.append(float(row["low"]))
            c.append(float(row["close"]))
            v.append(float(row["volume"]))
            ts_epoch = float(pd.Timestamp(row["timestamp"]).timestamp())

            # exit checks first (intrabar candle close assumption)
            if active and active.active:
                ltp = float(row["close"])
                hit_sl = (ltp <= active.stop_loss) if active.side == Side.BUY else (ltp >= active.stop_loss)
                hit_tg = (ltp >= active.target) if active.side == Side.BUY else (ltp <= active.target)
                if hit_sl or hit_tg:
                    active.close(price=ltp, ts=ts_epoch, reason="STOP_LOSS" if hit_sl else "TARGET")
                    realized += active.pnl
                    trades.append(active)
                    active = None
                    equity.append(realized)
                    continue

            if active and active.active:
                # one active trade per symbol
                equity.append(realized)
                continue

            side, reason = generate_signal(
                levels=levels,
                settings=settings.strategy,
                o=o, h=h, l=l, c=c, v=v,
                day_open=day_open,
            )
            if side is None:
                equity.append(realized)
                continue

            entry = float(row["close"])
            if side == Side.BUY:
                stop = min(levels.l4, float(row["low"]))
                target = float(levels.h3)
            else:
                stop = max(levels.h4, float(row["high"]))
                target = float(levels.l3)

            qty = compute_position_qty(
                capital=float(settings.risk.capital),
                max_risk_pct=float(settings.risk.max_risk_per_trade_pct),
                entry=entry,
                stop=stop,
                lot_size=1,
            )
            if qty <= 0:
                equity.append(realized)
                continue

            active = Trade(
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=entry,
                entry_time=ts_epoch,
                stop_loss=stop,
                target=target,
                reason=reason,
            )
            equity.append(realized)

    if active and active.active:
        # close last trade at last close
        last_close = float(df["close"].iloc[-1])
        ts = float(pd.Timestamp(df["timestamp"].iloc[-1]).timestamp())
        active.close(price=last_close, ts=ts, reason="EOD_FORCE_EXIT")
        realized += active.pnl
        trades.append(active)
        equity.append(realized)

    trade_count = len(trades)
    wins = sum(1 for t in trades if t.pnl > 0)
    win_rate = (wins / trade_count * 100.0) if trade_count else 0.0
    max_dd = compute_drawdown(equity)
    return BacktestReport(net_pnl=realized, win_rate=win_rate, max_drawdown=max_dd, trade_count=trade_count, equity_curve=equity)
"""

    # -------------------------
    # gui/
    # -------------------------
    files[str(PROJECT_ROOT / "gui" / "dialogs.py")] = r"""
from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, messagebox


def ask_password(parent: tk.Tk, title: str, prompt: str) -> str:
    return simpledialog.askstring(title, prompt, parent=parent, show="*") or ""


def info(parent: tk.Tk, title: str, msg: str) -> None:
    messagebox.showinfo(title, msg, parent=parent)


def error(parent: tk.Tk, title: str, msg: str) -> None:
    messagebox.showerror(title, msg, parent=parent)
"""

    files[str(PROJECT_ROOT / "gui" / "credentials_window.py")] = r"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional

from config.credentials import CredentialVault, get_broker_creds, set_broker_creds, get_telegram_creds, set_telegram_creds
from gui.dialogs import ask_password, info, error
from config.defaults import BrokerName


class CredentialsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.title("Credentials Vault")
        self.geometry("700x420")
        self.resizable(False, False)

        self.vault = CredentialVault()
        self.master_pw = ""
        self.payload: Dict[str, Any] = {}

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(frm)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Unlock / Init Vault", command=self.unlock).pack(side=tk.LEFT)
        ttk.Button(top, text="Save", command=self.save).pack(side=tk.LEFT, padx=8)

        self.broker_var = tk.StringVar(value=BrokerName.ZERODHA.value)
        ttk.Label(top, text="Broker:").pack(side=tk.LEFT, padx=(20, 6))
        ttk.Combobox(top, textvariable=self.broker_var, values=[b.value for b in BrokerName if b.value != "PAPER"], width=14, state="readonly").pack(side=tk.LEFT)

        nb = ttk.Notebook(frm)
        nb.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.broker_tab = ttk.Frame(nb)
        self.telegram_tab = ttk.Frame(nb)
        nb.add(self.broker_tab, text="Broker")
        nb.add(self.telegram_tab, text="Telegram")

        self._build_broker_tab()
        self._build_telegram_tab()

    def _build_broker_tab(self):
        f = self.broker_tab
        self.entries: Dict[str, tk.Entry] = {}

        row = 0
        for key in ["api_key", "access_token", "client_code", "password", "totp", "user_id", "vendor_code", "app_key", "factor2", "imei"]:
            ttk.Label(f, text=key).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            e = ttk.Entry(f, width=55)
            e.grid(row=row, column=1, sticky="w", padx=6, pady=4)
            self.entries[key] = e
            row += 1

        ttk.Button(f, text="Load for selected broker", command=self.load_selected_broker).grid(row=row, column=1, sticky="w", padx=6, pady=10)

    def _build_telegram_tab(self):
        f = self.telegram_tab
        self.tg_entries: Dict[str, tk.Entry] = {}
        row = 0
        for key in ["bot_token", "chat_id"]:
            ttk.Label(f, text=key).grid(row=row, column=0, sticky="w", padx=6, pady=6)
            e = ttk.Entry(f, width=60, show="*" if key == "bot_token" else None)
            e.grid(row=row, column=1, sticky="w", padx=6, pady=6)
            self.tg_entries[key] = e
            row += 1
        ttk.Button(f, text="Load Telegram", command=self.load_telegram).grid(row=row, column=1, sticky="w", padx=6, pady=10)

    def unlock(self) -> None:
        pw = ask_password(self, "Vault", "Enter master password (new vault will be created if missing):")
        if not pw:
            return
        try:
            if not self.vault.exists():
                self.vault.init_empty(pw)
            payload = self.vault.unlock(pw)
        except Exception as e:
            error(self, "Vault", str(e))
            return
        self.master_pw = pw
        self.payload = payload
        info(self, "Vault", "Vault unlocked.")
        self.load_selected_broker()
        self.load_telegram()

    def load_selected_broker(self) -> None:
        if not self.payload:
            return
        b = self.broker_var.get()
        creds = get_broker_creds(self.payload, b)
        for k, e in self.entries.items():
            e.delete(0, tk.END)
            if k in creds and creds[k] is not None:
                e.insert(0, str(creds[k]))

    def load_telegram(self) -> None:
        if not self.payload:
            return
        creds = get_telegram_creds(self.payload)
        for k, e in self.tg_entries.items():
            e.delete(0, tk.END)
            if k in creds and creds[k] is not None:
                e.insert(0, str(creds[k]))

    def save(self) -> None:
        if not self.master_pw:
            error(self, "Vault", "Unlock the vault first.")
            return
        b = self.broker_var.get()
        creds = {k: (e.get().strip() or None) for k, e in self.entries.items() if e.get().strip() != ""}
        self.payload = set_broker_creds(self.payload, b, creds)
        tg = {k: (e.get().strip() or None) for k, e in self.tg_entries.items() if e.get().strip() != ""}
        self.payload = set_telegram_creds(self.payload, tg)
        try:
            self.vault.save(self.master_pw, self.payload)
        except Exception as e:
            error(self, "Vault", str(e))
            return
        info(self, "Vault", "Saved.")
"""

    files[str(PROJECT_ROOT / "gui" / "settings_window.py")] = r"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config.settings_store import load_settings, save_settings
from config.defaults import AppSettings, BrokerName, Segment


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, settings: AppSettings):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("720x520")
        self.resizable(False, False)
        self.settings = settings

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        row = 0
        ttk.Label(frm, text="Broker").grid(row=row, column=0, sticky="w", pady=6)
        self.broker_var = tk.StringVar(value=settings.broker.value)
        ttk.Combobox(frm, textvariable=self.broker_var, values=[b.value for b in BrokerName], state="readonly", width=18).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(frm, text="Segment").grid(row=row, column=0, sticky="w", pady=6)
        self.segment_var = tk.StringVar(value=settings.segment.value)
        ttk.Combobox(frm, textvariable=self.segment_var, values=[s.value for s in Segment], state="readonly", width=18).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(frm, text="Trade mode").grid(row=row, column=0, sticky="w", pady=6)
        self.mode_var = tk.StringVar(value=settings.trade_mode)
        ttk.Combobox(frm, textvariable=self.mode_var, values=["PAPER", "LIVE"], state="readonly", width=18).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Separator(frm).grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        ttk.Label(frm, text="Capital").grid(row=row, column=0, sticky="w", pady=4)
        self.capital = tk.DoubleVar(value=float(settings.risk.capital))
        ttk.Entry(frm, textvariable=self.capital, width=20).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(frm, text="Max risk/trade (%)").grid(row=row, column=0, sticky="w", pady=4)
        self.riskpct = tk.DoubleVar(value=float(settings.risk.max_risk_per_trade_pct))
        ttk.Entry(frm, textvariable=self.riskpct, width=20).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(frm, text="Max trades/day").grid(row=row, column=0, sticky="w", pady=4)
        self.maxtrades = tk.IntVar(value=int(settings.risk.max_trades_per_day))
        ttk.Entry(frm, textvariable=self.maxtrades, width=20).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(frm, text="Daily loss limit (%)").grid(row=row, column=0, sticky="w", pady=4)
        self.dll = tk.DoubleVar(value=float(settings.risk.daily_loss_limit_pct))
        ttk.Entry(frm, textvariable=self.dll, width=20).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Separator(frm).grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        ttk.Label(frm, text="Symbols (comma separated)").grid(row=row, column=0, sticky="w", pady=4)
        self.symbols = tk.StringVar(value=",".join(settings.symbols))
        ttk.Entry(frm, textvariable=self.symbols, width=45).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Separator(frm).grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        row += 1

        ttk.Label(frm, text="Options enabled").grid(row=row, column=0, sticky="w", pady=4)
        self.opt_enabled = tk.BooleanVar(value=bool(settings.options.enabled))
        ttk.Checkbutton(frm, variable=self.opt_enabled).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(frm, text="Options product (MIS/NRML)").grid(row=row, column=0, sticky="w", pady=4)
        self.opt_product = tk.StringVar(value=str(settings.options.product))
        ttk.Entry(frm, textvariable=self.opt_product, width=20).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Button(frm, text="Save", command=self._save).grid(row=row + 1, column=1, sticky="w", pady=14)

    def _save(self) -> None:
        s = self.settings
        s.broker = BrokerName(self.broker_var.get())
        s.segment = Segment.from_str(self.segment_var.get())
        s.trade_mode = self.mode_var.get().upper()

        s.risk.capital = float(self.capital.get())
        s.risk.max_risk_per_trade_pct = float(self.riskpct.get())
        s.risk.max_trades_per_day = int(self.maxtrades.get())
        s.risk.daily_loss_limit_pct = float(self.dll.get())

        syms = [x.strip().upper() for x in self.symbols.get().split(",") if x.strip()]
        s.symbols = syms or s.symbols

        s.options.enabled = bool(self.opt_enabled.get())
        s.options.product = str(self.opt_product.get()).strip().upper() or "MIS"

        save_settings(s)
        self.destroy()
"""

    files[str(PROJECT_ROOT / "gui" / "app.py")] = r"""
from __future__ import annotations

import logging
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional

from brokers.factory import create_broker
from config.settings_store import load_settings
from config.credentials import CredentialVault, get_broker_creds, get_telegram_creds
from config.defaults import BrokerName
from core.execution import AlgoEngine
from core.telegram import TelegramClient
from websocket.manager import MarketDataManager
from websocket.candle_aggregator import CandleAggregator
from gui.settings_window import SettingsWindow
from gui.credentials_window import CredentialsWindow
from gui.dialogs import ask_password, error, info

log = logging.getLogger("gui")


class TradingApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Advanced Camarilla Multi-Broker Trading Platform")
        self.root.geometry("980x640")
        self.root.resizable(True, True)

        self.settings = load_settings()

        self._ui_q: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        self._engine: Optional[AlgoEngine] = None
        self._broker = None
        self._mdm: Optional[MarketDataManager] = None
        self._agg: Optional[CandleAggregator] = None
        self._tg: Optional[TelegramClient] = None

        self._vault = CredentialVault()
        self._vault_pw = ""
        self._vault_payload: Dict[str, Any] = {}

        self._build()
        self._tick_ui_loop()

    def run(self) -> None:
        self.root.mainloop()

    def _build(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Settings", command=self.open_settings).pack(side=tk.LEFT)
        ttk.Button(top, text="Credentials", command=self.open_credentials).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="Unlock Vault", command=self.unlock_vault).pack(side=tk.LEFT, padx=8)

        ttk.Separator(self.root).pack(fill=tk.X)

        controls = ttk.Frame(self.root, padding=10)
        controls.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="READY")
        ttk.Label(controls, text="Status:").pack(side=tk.LEFT)
        ttk.Label(controls, textvariable=self.status_var, width=90).pack(side=tk.LEFT, padx=6)

        self.start_btn = ttk.Button(controls, text="Start Algo", command=self.start_algo)
        self.stop_btn = ttk.Button(controls, text="Stop Algo", command=self.stop_algo, state=tk.DISABLED)
        self.kill_btn = ttk.Button(controls, text="KILL SWITCH", command=self.kill_algo)
        self.start_btn.pack(side=tk.RIGHT)
        self.stop_btn.pack(side=tk.RIGHT, padx=8)
        self.kill_btn.pack(side=tk.RIGHT, padx=8)

        mid = ttk.Frame(self.root, padding=10)
        mid.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = ttk.Frame(mid)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(left, text="Live LTP").pack(anchor="w")
        self.ltp_text = tk.Text(left, height=10, width=80)
        self.ltp_text.pack(fill=tk.X, pady=(4, 10))

        ttk.Label(left, text="Trade Status").pack(anchor="w")
        self.trade_text = tk.Text(left, height=14, width=80)
        self.trade_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        ttk.Label(right, text="P&L").pack(anchor="w")
        self.pnl_var = tk.StringVar(value="Realized: 0.00 | Unrealized: 0.00")
        ttk.Label(right, textvariable=self.pnl_var, width=30).pack(anchor="w", pady=(6, 20))

        ttk.Label(right, text="Mode").pack(anchor="w")
        self.mode_var = tk.StringVar(value=f"{self.settings.trade_mode} / {self.settings.broker.value}")
        ttk.Label(right, textvariable=self.mode_var, width=30).pack(anchor="w", pady=(6, 20))

        ttk.Label(right, text="Symbols").pack(anchor="w")
        self.sym_var = tk.StringVar(value=", ".join(self.settings.symbols))
        ttk.Label(right, textvariable=self.sym_var, width=30, wraplength=220).pack(anchor="w", pady=(6, 20))

    def open_settings(self) -> None:
        SettingsWindow(self.root, self.settings)

    def open_credentials(self) -> None:
        CredentialsWindow(self.root)

    def unlock_vault(self) -> None:
        pw = ask_password(self.root, "Vault", "Enter master password:")
        if not pw:
            return
        try:
            if not self._vault.exists():
                self._vault.init_empty(pw)
            payload = self._vault.unlock(pw)
        except Exception as e:
            error(self.root, "Vault", str(e))
            return
        self._vault_pw = pw
        self._vault_payload = payload
        info(self.root, "Vault", "Unlocked.")

    def start_algo(self) -> None:
        self.settings = load_settings()  # reload any saved changes
        self.mode_var.set(f"{self.settings.trade_mode} / {self.settings.broker.value}")
        self.sym_var.set(", ".join(self.settings.symbols))

        if self.settings.trade_mode == "LIVE" and not self._vault_pw:
            error(self.root, "Start", "Unlock vault first (credentials required for LIVE).")
            return

        broker = create_broker(self.settings.broker)
        if self.settings.trade_mode == "LIVE":
            creds = get_broker_creds(self._vault_payload, self.settings.broker.value)
            try:
                broker.login(creds)
            except Exception as e:
                error(self.root, "Broker login failed", str(e))
                return
        else:
            broker.login({})

        self._broker = broker
        self._mdm = MarketDataManager(broker)

        self._engine = AlgoEngine(
            broker=broker,
            settings=self.settings,
            on_status=lambda m: self._ui_q.put(("status", m)),
            on_ltp=lambda sym, ltp: self._ui_q.put(("ltp", (sym, ltp))),
            on_pnl=lambda r, u: self._ui_q.put(("pnl", (r, u))),
        )
        self._engine.start()

        # Candle aggregation
        self._agg = CandleAggregator(
            timeframe_minutes=self.settings.strategy.timeframe_minutes,
            on_candle_close=lambda sym, candle, ts: self._engine.on_candle_close(sym, candle, ts),
        )

        def on_tick(sym: str, ltp: float, raw: Dict[str, Any]):
            # engine LTP updates
            self._engine.on_tick(sym, ltp)
            # aggregator for strategy candles
            self._agg.on_tick(sym, ltp)

        try:
            self._mdm.start(on_tick=on_tick)
        except Exception as e:
            error(self.root, "Market data", str(e))
            return

        # Subscribe symbols
        for sym in self.settings.symbols:
            self._mdm.subscribe(sym, self.settings.segment)

        # Telegram integration
        if self.settings.telegram.enabled and self._vault_payload:
            tg = get_telegram_creds(self._vault_payload)
            if tg.get("bot_token") and tg.get("chat_id"):
                self._tg = TelegramClient(
                    bot_token=str(tg["bot_token"]),
                    chat_id=str(tg["chat_id"]),
                    poll_interval_sec=self.settings.telegram.poll_interval_sec,
                )
                self._tg.send(f"Algo STARTED ({self.settings.trade_mode}/{self.settings.broker.value}) symbols={self.settings.symbols}")
                self._tg.start_kill_switch_listener(on_stop=self.kill_algo)

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.status_var.set("RUNNING")

    def stop_algo(self) -> None:
        if self._tg:
            self._tg.send("Algo STOPPING")
        if self._engine:
            self._engine.stop()
        if self._mdm:
            self._mdm.stop()
        if self._agg:
            self._agg.flush()
        if self._tg:
            self._tg.stop()

        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.status_var.set("STOPPED")

    def kill_algo(self) -> None:
        if self._tg:
            self._tg.send("KILL SWITCH ACTIVATED: Cancelling orders & stopping.")
        if self._engine:
            self._engine.kill()
        if self._mdm:
            self._mdm.stop()
        if self._agg:
            self._agg.flush()
        if self._tg:
            self._tg.stop()
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.status_var.set("KILLED")

    def _tick_ui_loop(self) -> None:
        try:
            while True:
                typ, payload = self._ui_q.get_nowait()
                if typ == "status":
                    self.status_var.set(str(payload))
                    if self._tg:
                        # avoid spamming; only send key events
                        if str(payload).startswith(("ENTER", "EXIT", "ORDER_FAILED", "KILL", "ENGINE")):
                            self._tg.send(str(payload))
                    self._refresh_trade_status()
                elif typ == "ltp":
                    sym, ltp = payload
                    self._append_ltp(sym, ltp)
                elif typ == "pnl":
                    r, u = payload
                    self.pnl_var.set(f"Realized: {r:.2f} | Unrealized: {u:.2f}")
                else:
                    pass
        except queue.Empty:
            pass
        self.root.after(250, self._tick_ui_loop)

    def _append_ltp(self, sym: str, ltp: float) -> None:
        self.ltp_text.delete("1.0", tk.END)
        # show latest snapshot from engine status, but keep it simple
        self.ltp_text.insert(tk.END, f"{sym}: {ltp:.2f}\n")

    def _refresh_trade_status(self) -> None:
        if not self._engine:
            return
        snap = self._engine.get_status_snapshot()
        self.trade_text.delete("1.0", tk.END)
        for sym, line in snap.items():
            self.trade_text.insert(tk.END, f"{sym}: {line}\n")
"""

    # -------------------------
    # data/ placeholders (empty)
    # -------------------------
    files[str(PROJECT_ROOT / "data" / ".gitkeep")] = ""
    files[str(PROJECT_ROOT / "logs" / ".gitkeep")] = ""

    # Write files
    for rel, content in files.items():
        _write_file(Path(rel), content, force=args.force)

    # Make vault path private if exists (created later by app), but ensure dirs exist now.
    (PROJECT_ROOT / "config").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)

    print(f"Generated project at: {PROJECT_ROOT.resolve()}")
    print("Next:")
    print("  pip install -r multi_broker_camarilla_platform/requirements.txt")
    print("  python multi_broker_camarilla_platform/main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

