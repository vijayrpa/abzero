
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
