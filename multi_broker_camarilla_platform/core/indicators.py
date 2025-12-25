
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
