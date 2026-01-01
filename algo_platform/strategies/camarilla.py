from __future__ import annotations

from dataclasses import dataclass

from algo_platform.brokers.base import OHLC
from algo_platform.models import StrategyLevels


def compute_advanced_camarilla_levels(prev: OHLC) -> StrategyLevels:
    """
    Advanced Camarilla levels based on previous day's High/Low/Close.

    Uses common breakout model:
    - Entry: H4 / L4
    - Stop:  H3 / L3
    - Targets: H5/H6 and L5/L6
    """

    h = float(prev.high)
    l = float(prev.low)
    c = float(prev.close)
    rng = max(0.000001, h - l)

    h3 = c + (rng * 1.1 / 4.0)
    h4 = c + (rng * 1.1 / 2.0)
    l3 = c - (rng * 1.1 / 4.0)
    l4 = c - (rng * 1.1 / 2.0)

    # Extended targets
    # H5/L5 are often used as range expansion from H/L ratio.
    h5 = (h / l) * c if l > 0 else (c + rng)
    l5 = c - (h5 - c)
    h6 = h5 + 1.168 * (h5 - h4)
    l6 = l5 - 1.168 * (l4 - l5)

    return StrategyLevels(
        buy_level=h4,
        buy_t1=h5,
        buy_t2=h6,
        buy_sl=h3,
        sell_level=l4,
        sell_t1=l5,
        sell_t2=l6,
        sell_sl=l3,
    )

