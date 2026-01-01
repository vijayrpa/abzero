from __future__ import annotations

import csv
import io
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from algo_platform.brokers.base import BrokerBase, BrokerLoginResult, OHLC, TickCallback
from algo_platform.models import Order, Position, Product, Side, SymbolKey, Tick

log = logging.getLogger(__name__)


class ZerodhaKiteBroker(BrokerBase):
    """
    Zerodha Kite implementation using `kiteconnect`.

    Credentials supported:
    - api_key: str
    - api_secret: str
    - access_token: str (preferred if already generated)
    - request_token: str (one-time daily; used to generate access_token)
    """

    name = "Zerodha"

    def __init__(self) -> None:
        super().__init__()
        self._kite = None
        self._ticker = None
        self._token_by_key: Dict[str, int] = {}
        self._exchange_by_key: Dict[str, str] = {}
        self._on_tick: Optional[TickCallback] = None

    def _require_sdk(self) -> Any:
        try:
            from kiteconnect import KiteConnect  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency: kiteconnect. Install with: pip install kiteconnect"
            ) from e
        return KiteConnect

    def _require_ticker(self) -> Any:
        try:
            from kiteconnect import KiteTicker  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency: kiteconnect. Install with: pip install kiteconnect"
            ) from e
        return KiteTicker

    def login(self, creds: Dict[str, Any]) -> BrokerLoginResult:
        KiteConnect = self._require_sdk()
        api_key = creds.get("api_key")
        api_secret = creds.get("api_secret")
        access_token = creds.get("access_token")
        request_token = creds.get("request_token")
        if not api_key:
            return BrokerLoginResult(ok=False, message="Missing api_key for Zerodha.")
        self._kite = KiteConnect(api_key=api_key)
        if access_token:
            self._kite.set_access_token(access_token)
            return BrokerLoginResult(ok=True, message="Zerodha login OK (access_token).")
        if not (api_secret and request_token):
            return BrokerLoginResult(
                ok=False,
                message="Provide access_token OR (api_secret + request_token) for Zerodha.",
            )
        try:
            data = self._kite.generate_session(request_token, api_secret=api_secret)
            self._kite.set_access_token(data["access_token"])
        except Exception as e:
            return BrokerLoginResult(ok=False, message=f"Zerodha login failed: {e}")
        return BrokerLoginResult(ok=True, message="Zerodha login OK (generated access_token).")

    def logout(self) -> None:
        self.websocket_disconnect()
        self._kite = None

    def download_contract_master(self, out_dir: str) -> str:
        os.makedirs(out_dir, exist_ok=True)
        url = "https://api.kite.trade/instruments"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        fn = os.path.join(out_dir, f"zerodha_instruments_{date.today().isoformat()}.csv")
        with open(fn, "wb") as f:
            f.write(r.content)
        return fn

    def _load_tokens_from_instruments_csv(self, csv_path: str) -> None:
        self._token_by_key.clear()
        self._exchange_by_key.clear()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                exch = row.get("exchange")
                tsym = row.get("tradingsymbol")
                token = row.get("instrument_token")
                segment = row.get("segment") or ""
                if not (exch and tsym and token):
                    continue
                # segment normalization
                seg = "CASH"
                if "NFO" in segment:
                    seg = "NFO"
                elif "MCX" in segment:
                    seg = "MCX"
                elif "CDS" in segment:
                    seg = "CDS"
                elif exch == "BSE":
                    seg = "CASH"
                k = SymbolKey(exchange=exch, segment=seg, tradingsymbol=tsym).key()
                self._token_by_key[k] = int(token)
                self._exchange_by_key[k] = exch

    def load_instruments_csv(self, csv_path: str) -> None:
        self._load_tokens_from_instruments_csv(csv_path)

    def ensure_symbol(self, symbol: SymbolKey) -> None:
        if symbol.key() in self._token_by_key:
            return
        # If token cache empty, user hasn't downloaded contract master via UI yet.
        raise RuntimeError(
            "Zerodha instruments not loaded. Login triggers contract master download; retry after login."
        )

    def get_previous_day_ohlc(self, symbol: SymbolKey) -> OHLC:
        if not self._kite:
            raise RuntimeError("Zerodha not logged in.")
        self.ensure_symbol(symbol)
        token = self._token_by_key[symbol.key()]
        # Fetch last 2 trading days; take the last complete candle (yesterday).
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=7)
        candles = self._kite.historical_data(token, from_dt, to_dt, interval="day", continuous=False, oi=False)
        if not candles:
            raise RuntimeError("No historical candles returned.")
        last = candles[-2] if len(candles) >= 2 else candles[-1]
        d = datetime.fromisoformat(last["date"]).date() if isinstance(last["date"], str) else last["date"].date()
        return OHLC(d=d, open=float(last["open"]), high=float(last["high"]), low=float(last["low"]), close=float(last["close"]))

    def place_order(
        self,
        symbol: SymbolKey,
        side: Side,
        qty: int,
        product: Product,
        order_type: str,
        price: Optional[float] = None,
    ) -> Order:
        if not self._kite:
            raise RuntimeError("Zerodha not logged in.")
        self.ensure_symbol(symbol)
        from kiteconnect import KiteConnect  # type: ignore

        ttype = order_type.upper()
        variety = self._kite.VARIETY_REGULAR
        exchange = symbol.exchange
        tsym = symbol.tradingsymbol
        trans = self._kite.TRANSACTION_TYPE_BUY if side == Side.BUY else self._kite.TRANSACTION_TYPE_SELL
        prod = getattr(self._kite, f"PRODUCT_{product.value}", self._kite.PRODUCT_MIS)
        otype = self._kite.ORDER_TYPE_MARKET if ttype == "MARKET" else self._kite.ORDER_TYPE_LIMIT

        oid = self._kite.place_order(
            variety=variety,
            exchange=exchange,
            tradingsymbol=tsym,
            transaction_type=trans,
            quantity=int(qty),
            product=prod,
            order_type=otype,
            price=price if otype == self._kite.ORDER_TYPE_LIMIT else None,
        )
        # Best-effort map to unified Order; status will be refreshed via get_orders.
        return Order(
            order_id=str(oid),
            symbol=symbol,
            side=side,
            qty=int(qty),
            product=product,
            order_type=ttype,
            price=price,
        )

    def modify_order(self, order_id: str, qty: Optional[int] = None, price: Optional[float] = None) -> Order:
        if not self._kite:
            raise RuntimeError("Zerodha not logged in.")
        self._kite.modify_order(variety=self._kite.VARIETY_REGULAR, order_id=order_id, quantity=qty, price=price)
        return Order(order_id=order_id, symbol=SymbolKey("NSE", "UNKNOWN", "CASH"), side=Side.BUY, qty=0, product=Product.MIS, order_type="UNKNOWN")

    def cancel_order(self, order_id: str) -> Order:
        if not self._kite:
            raise RuntimeError("Zerodha not logged in.")
        self._kite.cancel_order(variety=self._kite.VARIETY_REGULAR, order_id=order_id)
        return Order(order_id=order_id, symbol=SymbolKey("NSE", "UNKNOWN", "CASH"), side=Side.BUY, qty=0, product=Product.MIS, order_type="UNKNOWN")

    def get_positions(self) -> List[Position]:
        if not self._kite:
            raise RuntimeError("Zerodha not logged in.")
        out: List[Position] = []
        pos = self._kite.positions()
        for p in pos.get("net", []):
            sym = SymbolKey(exchange=p.get("exchange", "NSE"), segment="CASH", tradingsymbol=p.get("tradingsymbol", ""))
            out.append(
                Position(
                    symbol=sym,
                    net_qty=int(p.get("quantity", 0)),
                    avg_price=float(p.get("average_price", 0.0) or 0.0),
                    realized_pnl=float(p.get("pnl", 0.0) or 0.0),
                    unrealized_pnl=float(p.get("unrealised", 0.0) or 0.0),
                )
            )
        return out

    def get_orders(self) -> List[Order]:
        if not self._kite:
            raise RuntimeError("Zerodha not logged in.")
        out: List[Order] = []
        for o in self._kite.orders():
            sym = SymbolKey(exchange=o.get("exchange", "NSE"), segment="CASH", tradingsymbol=o.get("tradingsymbol", ""))
            side = Side.BUY if o.get("transaction_type") == "BUY" else Side.SELL
            out.append(
                Order(
                    order_id=str(o.get("order_id")),
                    symbol=sym,
                    side=side,
                    qty=int(o.get("quantity", 0)),
                    product=Product(o.get("product", "MIS")) if o.get("product") in ("CNC", "MIS", "NRML") else Product.MIS,
                    order_type=str(o.get("order_type", "MARKET")),
                    price=float(o.get("price", 0.0) or 0.0),
                    status=OrderStatusFromKite(o.get("status")),
                    filled_qty=int(o.get("filled_quantity", 0)),
                    avg_price=float(o.get("average_price", 0.0) or 0.0),
                    broker_message=str(o.get("status_message", "") or ""),
                )
            )
        return out

    def websocket_connect(self, on_tick: TickCallback) -> None:
        if not self._kite:
            raise RuntimeError("Zerodha not logged in.")
        KiteTicker = self._require_ticker()
        self._on_tick = on_tick
        self._ticker = KiteTicker(self._kite.api_key, self._kite.access_token)

        def _on_ticks(ws, ticks):
            now = datetime.utcnow()
            for t in ticks:
                token = t.get("instrument_token")
                ltp = float(t.get("last_price", 0.0) or 0.0)
                # Reverse lookup token->SymbolKey where possible.
                sym = None
                for k, tok in self._token_by_key.items():
                    if tok == token:
                        # parse k
                        _, _, tsym = k.split(":", 2)
                        exch, seg, _ = k.split(":", 2)
                        sym = SymbolKey(exchange=exch, segment=seg, tradingsymbol=tsym)
                        break
                if not sym:
                    continue
                self._on_tick(
                    Tick(
                        symbol=sym,
                        ltp=ltp,
                        ts=now,
                        open=float(t.get("ohlc", {}).get("open", 0.0) or 0.0),
                        high=float(t.get("ohlc", {}).get("high", 0.0) or 0.0),
                        low=float(t.get("ohlc", {}).get("low", 0.0) or 0.0),
                        prev_close=float(t.get("ohlc", {}).get("close", 0.0) or 0.0),
                    )
                )

        def _on_connect(ws, response):
            log.info("Zerodha websocket connected")

        def _on_close(ws, code, reason):
            log.warning("Zerodha websocket closed: %s %s", code, reason)

        self._ticker.on_ticks = _on_ticks
        self._ticker.on_connect = _on_connect
        self._ticker.on_close = _on_close
        self._ticker.connect(threaded=True)

    def websocket_disconnect(self) -> None:
        if self._ticker:
            try:
                self._ticker.close()
            except Exception:
                pass
        self._ticker = None
        self._on_tick = None

    def websocket_subscribe(self, symbols: List[SymbolKey]) -> None:
        if not self._ticker:
            raise RuntimeError("Websocket not connected.")
        tokens: List[int] = []
        for s in symbols:
            self.ensure_symbol(s)
            tokens.append(self._token_by_key[s.key()])
        if tokens:
            self._ticker.subscribe(tokens)
            self._ticker.set_mode(self._ticker.MODE_FULL, tokens)

    def websocket_unsubscribe(self, symbols: List[SymbolKey]) -> None:
        if not self._ticker:
            return
        tokens: List[int] = []
        for s in symbols:
            tok = self._token_by_key.get(s.key())
            if tok:
                tokens.append(tok)
        if tokens:
            self._ticker.unsubscribe(tokens)


def OrderStatusFromKite(status: Any) -> Any:
    from algo_platform.models import OrderStatus

    s = str(status or "").upper()
    if s in ("COMPLETE", "COMPLETED", "FILLED"):
        return OrderStatus.FILLED
    if s in ("OPEN", "TRIGGER PENDING", "AMO REQ RECEIVED", "PUT ORDER REQ RECEIVED"):
        return OrderStatus.OPEN
    if s in ("CANCELLED", "CANCELED"):
        return OrderStatus.CANCELLED
    if s in ("REJECTED",):
        return OrderStatus.REJECTED
    return OrderStatus.NEW

