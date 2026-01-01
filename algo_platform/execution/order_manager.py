from __future__ import annotations

import csv
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

from algo_platform.brokers.base import BrokerBase
from algo_platform.models import (
    ActiveTrade,
    Order,
    OrderStatus,
    Position,
    Product,
    Side,
    SymbolKey,
    TradeMode,
)

log = logging.getLogger(__name__)


@dataclass
class ExecResult:
    ok: bool
    message: str
    order_id: Optional[str] = None
    fill_price: Optional[float] = None


class TradeLogger:
    def __init__(self, out_dir: str) -> None:
        self._out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self) -> str:
        d = datetime.now().date().isoformat()
        return os.path.join(self._out_dir, f"trades_{d}.csv")

    def log_event(
        self,
        event: str,
        symbol: SymbolKey,
        side: Side,
        qty: int,
        price: float,
        reason: str,
        strategy_type: str,
        trade_mode: str,
        extra: str = "",
    ) -> None:
        fp = self._path()
        header = [
            "ts",
            "event",
            "exchange",
            "segment",
            "symbol",
            "side",
            "qty",
            "price",
            "reason",
            "strategy_type",
            "trade_mode",
            "extra",
        ]
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            event,
            symbol.exchange,
            symbol.segment,
            symbol.tradingsymbol,
            side.value,
            str(qty),
            f"{price:.4f}",
            reason,
            strategy_type,
            trade_mode,
            extra,
        ]
        with self._lock:
            write_header = not os.path.exists(fp)
            with open(fp, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if write_header:
                    w.writerow(header)
                w.writerow(row)


class OrderManager:
    """
    Execution manager for both Paper and Real modes.
    - Paper: simulate instant fills at tick LTP, track positions locally.
    - Real: place market orders via broker and poll until filled/rejected.
    """

    def __init__(self, broker: BrokerBase, trade_logs_dir: str) -> None:
        self._broker = broker
        self._logger = TradeLogger(trade_logs_dir)
        self._paper_positions: Dict[str, Position] = {}
        self._paper_orders: Dict[str, Order] = {}
        self._lock = threading.RLock()
        self._real_positions_cache: Dict[str, Position] = {}
        self._real_positions_cache_ts: float = 0.0

    def get_paper_positions(self) -> Dict[str, Position]:
        with self._lock:
            return dict(self._paper_positions)

    def paper_unrealized_pnl(self, symbol: SymbolKey, ltp: float) -> float:
        with self._lock:
            pos = self._paper_positions.get(symbol.key())
            if not pos or pos.net_qty == 0:
                return 0.0
            if pos.net_qty > 0:
                return (ltp - pos.avg_price) * pos.net_qty
            return (pos.avg_price - ltp) * abs(pos.net_qty)

    def paper_realized_pnl(self, symbol: SymbolKey) -> float:
        with self._lock:
            pos = self._paper_positions.get(symbol.key())
            return float(pos.realized_pnl) if pos else 0.0

    def get_pnl(self, symbol: SymbolKey, ltp: float, trade_mode: TradeMode) -> float:
        if trade_mode == TradeMode.PAPER:
            return self.paper_realized_pnl(symbol) + self.paper_unrealized_pnl(symbol, ltp)
        # REAL (best-effort)
        pos = self._get_real_position(symbol)
        if not pos or pos.net_qty == 0:
            return 0.0
        # Use broker-reported realized if available; compute unrealized from ltp + avg_price.
        unreal = 0.0
        if pos.net_qty > 0:
            unreal = (ltp - pos.avg_price) * pos.net_qty
        else:
            unreal = (pos.avg_price - ltp) * abs(pos.net_qty)
        return float(pos.realized_pnl) + float(unreal)

    def _get_real_position(self, symbol: SymbolKey, max_age_s: float = 2.0) -> Optional[Position]:
        now = time.time()
        with self._lock:
            if now - self._real_positions_cache_ts <= max_age_s and self._real_positions_cache:
                return self._real_positions_cache.get(symbol.key())
        try:
            positions = self._broker.get_positions()
        except Exception:
            return None
        m: Dict[str, Position] = {}
        for p in positions:
            m[p.symbol.key()] = p
        with self._lock:
            self._real_positions_cache = m
            self._real_positions_cache_ts = now
        return m.get(symbol.key())

    def _paper_pos(self, symbol: SymbolKey) -> Position:
        with self._lock:
            k = symbol.key()
            if k not in self._paper_positions:
                self._paper_positions[k] = Position(symbol=symbol, net_qty=0, avg_price=0.0, realized_pnl=0.0)
            return self._paper_positions[k]

    def enter_trade(
        self,
        *,
        trade_mode: TradeMode,
        strategy_type: str,
        symbol: SymbolKey,
        side: Side,
        qty: int,
        ltp: float,
        product: Product = Product.MIS,
    ) -> ExecResult:
        if trade_mode == TradeMode.PAPER:
            # Simulate instant fill at ltp.
            pos = self._paper_pos(symbol)
            signed = qty if side == Side.BUY else -qty
            if pos.net_qty == 0 or (pos.net_qty > 0 and signed > 0) or (pos.net_qty < 0 and signed < 0):
                new_qty = pos.net_qty + signed
                if new_qty != 0:
                    pos.avg_price = (pos.avg_price * abs(pos.net_qty) + ltp * abs(signed)) / abs(new_qty)
                pos.net_qty = new_qty
            else:
                closing_qty = min(abs(pos.net_qty), abs(signed))
                if pos.net_qty > 0 and signed < 0:
                    pos.realized_pnl += (ltp - pos.avg_price) * closing_qty
                elif pos.net_qty < 0 and signed > 0:
                    pos.realized_pnl += (pos.avg_price - ltp) * closing_qty
                pos.net_qty = pos.net_qty + signed
                if pos.net_qty == 0:
                    pos.avg_price = 0.0
                else:
                    pos.avg_price = ltp

            self._logger.log_event(
                event="ENTRY",
                symbol=symbol,
                side=side,
                qty=qty,
                price=ltp,
                reason="Entry",
                strategy_type=strategy_type,
                trade_mode=trade_mode.value,
            )
            return ExecResult(ok=True, message="Paper entry filled.", fill_price=ltp)

        # REAL
        try:
            o = self._broker.place_order(symbol=symbol, side=side, qty=qty, product=product, order_type="MARKET", price=None)
        except Exception as e:
            return ExecResult(ok=False, message=f"Broker place_order failed: {e}")

        fill = self._poll_fill(o.order_id, timeout_s=12.0)
        if not fill:
            return ExecResult(ok=False, message="Order placed but fill not confirmed (check broker order book).", order_id=o.order_id)
        status, avg = fill
        if status == OrderStatus.REJECTED:
            return ExecResult(ok=False, message="Order rejected by broker.", order_id=o.order_id)

        px = avg if avg is not None else ltp
        self._logger.log_event(
            event="ENTRY",
            symbol=symbol,
            side=side,
            qty=qty,
            price=px,
            reason="Entry",
            strategy_type=strategy_type,
            trade_mode=trade_mode.value,
            extra=f"order_id={o.order_id}",
        )
        return ExecResult(ok=True, message="Real entry sent.", order_id=o.order_id, fill_price=px)

    def exit_trade(
        self,
        *,
        trade_mode: TradeMode,
        strategy_type: str,
        symbol: SymbolKey,
        side: Side,
        qty: int,
        ltp: float,
        reason: str,
        product: Product = Product.MIS,
    ) -> ExecResult:
        exit_side = Side.SELL if side == Side.BUY else Side.BUY
        if trade_mode == TradeMode.PAPER:
            # Apply the opposite to flatten (paper), but log as EXIT with reason.
            pos = self._paper_pos(symbol)
            signed = qty if exit_side == Side.BUY else -qty
            if pos.net_qty == 0:
                return ExecResult(ok=False, message="No paper position to exit.")

            closing_qty = min(abs(pos.net_qty), abs(signed))
            if pos.net_qty > 0 and signed < 0:
                pos.realized_pnl += (ltp - pos.avg_price) * closing_qty
            elif pos.net_qty < 0 and signed > 0:
                pos.realized_pnl += (pos.avg_price - ltp) * closing_qty
            pos.net_qty = pos.net_qty + signed
            if pos.net_qty == 0:
                pos.avg_price = 0.0
            else:
                pos.avg_price = ltp

            self._logger.log_event(
                event="EXIT",
                symbol=symbol,
                side=exit_side,
                qty=qty,
                price=ltp,
                reason=reason,
                strategy_type=strategy_type,
                trade_mode=trade_mode.value,
            )
            return ExecResult(ok=True, message="Paper exit filled.", fill_price=ltp)

        try:
            o = self._broker.place_order(symbol=symbol, side=exit_side, qty=qty, product=product, order_type="MARKET", price=None)
        except Exception as e:
            return ExecResult(ok=False, message=f"Broker exit order failed: {e}")

        fill = self._poll_fill(o.order_id, timeout_s=12.0)
        px = (fill[1] if fill and fill[1] is not None else ltp)
        self._logger.log_event(
            event="EXIT",
            symbol=symbol,
            side=exit_side,
            qty=qty,
            price=px,
            reason=reason,
            strategy_type=strategy_type,
            trade_mode=trade_mode.value,
            extra=f"order_id={o.order_id}",
        )
        return ExecResult(ok=True, message="Exit sent.", order_id=o.order_id, fill_price=px)

    def _poll_fill(self, order_id: str, timeout_s: float) -> Optional[Tuple[OrderStatus, Optional[float]]]:
        start = time.time()
        last_status = None
        while time.time() - start < timeout_s:
            try:
                orders = self._broker.get_orders()
            except Exception:
                time.sleep(0.5)
                continue
            for o in orders:
                if str(o.order_id) != str(order_id):
                    continue
                last_status = o.status
                if o.status in (OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED):
                    return o.status, (o.avg_price if o.avg_price else None)
            time.sleep(0.5)
        if last_status:
            return last_status, None
        return None

