from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from algo_platform.brokers.base import BrokerBase, BrokerLoginResult, OHLC, TickCallback
from algo_platform.models import Order, Product, Side, SymbolKey, Tick

log = logging.getLogger(__name__)


class AliceBlueBroker(BrokerBase):
    """
    AliceBlue implementation.

    Supports the community `alice_blue` SDK if installed.

    Credentials supported (common stable approach):
    - user_id: str
    - api_key: str
    - access_token: str  (session id / access token obtained from AliceBlue login flow)
    """

    name = "AliceBlue"

    def __init__(self) -> None:
        super().__init__()
        self._ab = None
        self._ws_connected = False
        self._on_tick: Optional[TickCallback] = None
        self._token_by_key: Dict[str, str] = {}

    def _require_sdk(self) -> Any:
        try:
            from alice_blue import Aliceblue  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency: alice-blue. Install with: pip install alice-blue"
            ) from e
        return Aliceblue

    def login(self, creds: Dict[str, Any]) -> BrokerLoginResult:
        Aliceblue = self._require_sdk()
        user_id = creds.get("user_id")
        api_key = creds.get("api_key")
        access_token = creds.get("access_token")
        if not (user_id and api_key and access_token):
            return BrokerLoginResult(
                ok=False,
                message="Provide user_id, api_key, access_token for AliceBlue.",
            )
        try:
            self._ab = Aliceblue(user_id=user_id, api_key=api_key)
            # alice_blue uses set_session
            if hasattr(self._ab, "set_session"):
                self._ab.set_session(user_id=user_id, api_key=api_key, session_id=access_token)
            elif hasattr(self._ab, "session_id"):
                self._ab.session_id = access_token
            else:
                return BrokerLoginResult(ok=False, message="Unsupported alice_blue SDK version.")
        except Exception as e:
            return BrokerLoginResult(ok=False, message=f"AliceBlue login failed: {e}")
        return BrokerLoginResult(ok=True, message="AliceBlue login OK.")

    def logout(self) -> None:
        self.websocket_disconnect()
        self._ab = None

    def download_contract_master(self, out_dir: str) -> str:
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        os.makedirs(out_dir, exist_ok=True)
        # Best-effort: some SDK versions expose `get_contract_master`.
        if hasattr(self._ab, "get_contract_master"):
            fp = os.path.join(out_dir, f"aliceblue_contract_master_{date.today().isoformat()}.csv")
            try:
                # Try common segments
                master = self._ab.get_contract_master("NSE")  # type: ignore
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(master if isinstance(master, str) else str(master))
                return fp
            except Exception as e:
                raise RuntimeError(f"Failed to download contract master: {e}") from e
        raise RuntimeError("AliceBlue SDK does not expose contract master download in this environment.")

    def ensure_symbol(self, symbol: SymbolKey) -> None:
        # Many AliceBlue APIs accept exchange+tradingsymbol directly; token mapping optional.
        self._token_by_key.setdefault(symbol.key(), symbol.tradingsymbol)

    def get_previous_day_ohlc(self, symbol: SymbolKey) -> OHLC:
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        self.ensure_symbol(symbol)
        # Best-effort using get_historical
        if hasattr(self._ab, "get_historical"):
            to_dt = datetime.now()
            from_dt = to_dt - timedelta(days=7)
            try:
                data = self._ab.get_historical(  # type: ignore
                    exchange=symbol.exchange,
                    symbol=symbol.tradingsymbol,
                    from_datetime=from_dt,
                    to_datetime=to_dt,
                    interval="1D",
                )
                if not data:
                    raise RuntimeError("No candles returned.")
                last = data[-2] if len(data) >= 2 else data[-1]
                d = last.get("datetime")
                if isinstance(d, str):
                    d = datetime.fromisoformat(d)
                d0 = d.date() if hasattr(d, "date") else date.today() - timedelta(days=1)
                return OHLC(
                    d=d0,
                    open=float(last.get("open", 0.0)),
                    high=float(last.get("high", 0.0)),
                    low=float(last.get("low", 0.0)),
                    close=float(last.get("close", 0.0)),
                )
            except Exception as e:
                raise RuntimeError(f"OHLC fetch failed: {e}") from e
        raise RuntimeError("AliceBlue historical OHLC not available via installed SDK.")

    def place_order(
        self,
        symbol: SymbolKey,
        side: Side,
        qty: int,
        product: Product,
        order_type: str,
        price: Optional[float] = None,
    ) -> Order:
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        self.ensure_symbol(symbol)
        # Common SDK: place_order(transaction_type, instrument, quantity, order_type, product_type, price)
        try:
            transaction_type = "BUY" if side == Side.BUY else "SELL"
            otype = order_type.upper()
            prod = product.value
            if hasattr(self._ab, "get_instrument_by_symbol"):
                inst = self._ab.get_instrument_by_symbol(symbol.exchange, symbol.tradingsymbol)  # type: ignore
            else:
                inst = symbol.tradingsymbol
            oid = self._ab.place_order(  # type: ignore
                transaction_type=transaction_type,
                instrument=inst,
                quantity=int(qty),
                order_type=otype,
                product_type=prod,
                price=price,
            )
            return Order(order_id=str(oid), symbol=symbol, side=side, qty=int(qty), product=product, order_type=otype, price=price)
        except Exception as e:
            raise RuntimeError(f"AliceBlue place_order failed: {e}") from e

    def modify_order(self, order_id: str, qty: Optional[int] = None, price: Optional[float] = None) -> Order:
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        try:
            if hasattr(self._ab, "modify_order"):
                self._ab.modify_order(order_id=order_id, quantity=qty, price=price)  # type: ignore
            return Order(order_id=str(order_id), symbol=SymbolKey("NSE", "UNKNOWN", "CASH"), side=Side.BUY, qty=0, product=Product.MIS, order_type="UNKNOWN")
        except Exception as e:
            raise RuntimeError(f"AliceBlue modify_order failed: {e}") from e

    def cancel_order(self, order_id: str) -> Order:
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        try:
            if hasattr(self._ab, "cancel_order"):
                self._ab.cancel_order(order_id=order_id)  # type: ignore
            return Order(order_id=str(order_id), symbol=SymbolKey("NSE", "UNKNOWN", "CASH"), side=Side.BUY, qty=0, product=Product.MIS, order_type="UNKNOWN")
        except Exception as e:
            raise RuntimeError(f"AliceBlue cancel_order failed: {e}") from e

    def get_positions(self):
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        if hasattr(self._ab, "get_netwise_positions"):
            raw = self._ab.get_netwise_positions()  # type: ignore
            from algo_platform.models import Position

            out = []
            for p in raw or []:
                sym = SymbolKey(exchange=p.get("exchange", "NSE"), segment="CASH", tradingsymbol=p.get("trading_symbol", ""))
                out.append(
                    Position(
                        symbol=sym,
                        net_qty=int(p.get("net_quantity", 0) or 0),
                        avg_price=float(p.get("average_price", 0.0) or 0.0),
                        realized_pnl=float(p.get("realized_pnl", 0.0) or 0.0),
                        unrealized_pnl=float(p.get("unrealized_pnl", 0.0) or 0.0),
                    )
                )
            return out
        return []

    def get_orders(self):
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        if hasattr(self._ab, "get_order_history"):
            raw = self._ab.get_order_history()  # type: ignore
            from algo_platform.models import OrderStatus, Position

            out = []
            for o in raw or []:
                sym = SymbolKey(exchange=o.get("exchange", "NSE"), segment="CASH", tradingsymbol=o.get("trading_symbol", ""))
                side = Side.BUY if str(o.get("transaction_type", "")).upper() == "BUY" else Side.SELL
                out.append(
                    Order(
                        order_id=str(o.get("order_id")),
                        symbol=sym,
                        side=side,
                        qty=int(o.get("quantity", 0) or 0),
                        product=Product.MIS,
                        order_type=str(o.get("order_type", "MARKET")),
                        price=float(o.get("price", 0.0) or 0.0),
                        status=OrderStatus.NEW,
                    )
                )
            return out
        return []

    def websocket_connect(self, on_tick: TickCallback) -> None:
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        self._on_tick = on_tick
        self._ws_connected = True

        # SDK styles vary; implement common callback-based start_websocket if available.
        if hasattr(self._ab, "start_websocket"):
            from alice_blue import LiveFeedType  # type: ignore

            def _socket_open():
                log.info("AliceBlue websocket connected")

            def _socket_close():
                log.warning("AliceBlue websocket closed")

            def _socket_error(message):
                log.error("AliceBlue websocket error: %s", message)

            def _feed_update(message):
                try:
                    # message contains `lp` (last price) and `tk` (token) etc
                    ltp = float(message.get("lp", 0.0) or 0.0)
                    tsym = message.get("ts", "")
                    exch = message.get("e", "NSE")
                    sym = SymbolKey(exchange=exch, segment="CASH", tradingsymbol=tsym)
                    self._on_tick(Tick(symbol=sym, ltp=ltp, ts=datetime.utcnow()))
                except Exception:
                    log.exception("AliceBlue tick parse error")

            self._ab.start_websocket(  # type: ignore
                socket_open_callback=_socket_open,
                socket_close_callback=_socket_close,
                socket_error_callback=_socket_error,
                subscription_callback=_feed_update,
                run_in_background=True,
            )
            return

        raise RuntimeError("AliceBlue websocket not available via installed SDK.")

    def websocket_disconnect(self) -> None:
        self._ws_connected = False
        self._on_tick = None
        try:
            if self._ab and hasattr(self._ab, "stop_websocket"):
                self._ab.stop_websocket()  # type: ignore
        except Exception:
            pass

    def websocket_subscribe(self, symbols: List[SymbolKey]) -> None:
        if not self._ab:
            raise RuntimeError("AliceBlue not logged in.")
        if not hasattr(self._ab, "subscribe"):
            return
        try:
            from alice_blue import LiveFeedType  # type: ignore

            for s in symbols:
                self.ensure_symbol(s)
                inst = self._ab.get_instrument_by_symbol(s.exchange, s.tradingsymbol)  # type: ignore
                self._ab.subscribe(inst, LiveFeedType.MARKET_DATA)  # type: ignore
        except Exception as e:
            raise RuntimeError(f"AliceBlue subscribe failed: {e}") from e

    def websocket_unsubscribe(self, symbols: List[SymbolKey]) -> None:
        if not self._ab or not hasattr(self._ab, "unsubscribe"):
            return
        try:
            for s in symbols:
                inst = self._ab.get_instrument_by_symbol(s.exchange, s.tradingsymbol)  # type: ignore
                self._ab.unsubscribe(inst)  # type: ignore
        except Exception:
            pass

