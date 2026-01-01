from __future__ import annotations

import logging
import os
import zipfile
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from algo_platform.brokers.base import BrokerBase, BrokerLoginResult, OHLC, TickCallback
from algo_platform.models import Order, Product, Side, SymbolKey, Tick

log = logging.getLogger(__name__)


class ShoonyaBroker(BrokerBase):
    """
    Shoonya (Finvasia) implementation using NorenRestApiPy when installed.

    Typical creds:
    - user: str
    - password: str
    - twofa: str
    - vendor_code: str
    - api_secret: str
    - imei: str
    """

    name = "Shoonya"

    def __init__(self) -> None:
        super().__init__()
        self._api = None
        self._on_tick: Optional[TickCallback] = None
        self._subscribed: Dict[str, SymbolKey] = {}
        self._token_by_key: Dict[str, str] = {}
        self._exch_by_key: Dict[str, str] = {}

    def _require_sdk(self) -> Any:
        try:
            from NorenRestApiPy.NorenApi import NorenApi  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Missing dependency: NorenRestApiPy. Install from the official Shoonya/Finvasia package."
            ) from e
        return NorenApi

    def login(self, creds: Dict[str, Any]) -> BrokerLoginResult:
        NorenApi = self._require_sdk()
        user = creds.get("user")
        password = creds.get("password")
        twofa = creds.get("twofa")
        vc = creds.get("vendor_code")
        api_secret = creds.get("api_secret")
        imei = creds.get("imei")
        if not all([user, password, twofa, vc, api_secret, imei]):
            return BrokerLoginResult(
                ok=False,
                message="Provide user,password,twofa,vendor_code,api_secret,imei for Shoonya.",
            )

        class _Api(NorenApi):  # type: ignore
            def __init__(self):
                super().__init__(
                    host="https://api.shoonya.com/NorenWClientTP/",
                    websocket="wss://api.shoonya.com/NorenWSTP/",
                )

        self._api = _Api()
        try:
            ret = self._api.login(userid=user, password=password, twoFA=twofa, vendor_code=vc, api_secret=api_secret, imei=imei)  # type: ignore
            if not ret or ret.get("stat") != "Ok":
                return BrokerLoginResult(ok=False, message=f"Shoonya login failed: {ret}")
        except Exception as e:
            return BrokerLoginResult(ok=False, message=f"Shoonya login failed: {e}")
        return BrokerLoginResult(ok=True, message="Shoonya login OK.")

    def logout(self) -> None:
        self.websocket_disconnect()
        try:
            if self._api and hasattr(self._api, "logout"):
                self._api.logout()  # type: ignore
        except Exception:
            pass
        self._api = None

    def download_contract_master(self, out_dir: str) -> str:
        """
        Downloads Shoonya scrip masters (NSE/BSE/NFO/MCX/CDS) from the public endpoints.
        Stores as extracted text files and builds token mapping for websocket/ohlc.
        """
        os.makedirs(out_dir, exist_ok=True)
        base = "https://api.shoonya.com"
        endpoints = {
            "NSE": f"{base}/NSE_symbols.txt.zip",
            "BSE": f"{base}/BSE_symbols.txt.zip",
            "NFO": f"{base}/NFO_symbols.txt.zip",
            "MCX": f"{base}/MCX_symbols.txt.zip",
            "CDS": f"{base}/CDS_symbols.txt.zip",
        }
        downloaded_any = False
        for exch, url in endpoints.items():
            try:
                r = requests.get(url, timeout=60)
                r.raise_for_status()
            except Exception as e:
                log.warning("Shoonya scrip master download failed for %s: %s", exch, e)
                continue
            zpath = os.path.join(out_dir, f"shoonya_{exch}_{date.today().isoformat()}.zip")
            with open(zpath, "wb") as f:
                f.write(r.content)
            try:
                with zipfile.ZipFile(zpath) as zf:
                    for name in zf.namelist():
                        if not name.lower().endswith(".txt"):
                            continue
                        out_fp = os.path.join(out_dir, f"shoonya_{exch}_{date.today().isoformat()}_{os.path.basename(name)}")
                        with open(out_fp, "wb") as of:
                            of.write(zf.read(name))
                        self._load_scrip_master_txt(out_fp, exch=exch)
                        downloaded_any = True
            except Exception as e:
                log.warning("Shoonya scrip master unzip failed for %s: %s", exch, e)

        if not downloaded_any:
            raise RuntimeError("Could not download Shoonya scrip masters from public endpoints.")
        return out_dir

    def _load_scrip_master_txt(self, path: str, exch: str) -> None:
        # Pipe-separated with header line. Common columns: Exchange|Token|LotSize|Symbol|TradingSymbol|...
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            header = f.readline().strip().split("|")
            idx = {h.strip(): i for i, h in enumerate(header)}

            def get(cols, key, default=""):
                i = idx.get(key)
                return cols[i].strip() if i is not None and i < len(cols) else default

            for line in f:
                cols = line.strip().split("|")
                tsym = get(cols, "TradingSymbol") or get(cols, "TSym") or get(cols, "Tsym")
                token = get(cols, "Token") or get(cols, "token")
                if not tsym or not token:
                    continue
                sym = SymbolKey(exchange=exch, segment=("CASH" if exch in ("NSE", "BSE") else exch), tradingsymbol=tsym)
                self._token_by_key[sym.key()] = token
                self._exch_by_key[sym.key()] = exch

    def ensure_symbol(self, symbol: SymbolKey) -> None:
        if symbol.key() in self._token_by_key:
            return
        raise RuntimeError("Shoonya symbol token not found. Download contract master at login.")

    def get_previous_day_ohlc(self, symbol: SymbolKey) -> OHLC:
        if not self._api:
            raise RuntimeError("Shoonya not logged in.")
        # Requires token mapping; best-effort using time price series if available.
        if not hasattr(self._api, "get_time_price_series"):
            raise RuntimeError("Shoonya historical OHLC not available via installed SDK.")
        self.ensure_symbol(symbol)
        exch = self._exch_by_key[symbol.key()]
        token = self._token_by_key[symbol.key()]
        to_dt = datetime.now()
        from_dt = to_dt - timedelta(days=7)
        # API expects unix epoch seconds (string) for starttime/endtime in many builds.
        start = int(from_dt.timestamp())
        end = int(to_dt.timestamp())
        raw = self._api.get_time_price_series(exchange=exch, token=token, starttime=str(start), endtime=str(end), interval="1D")  # type: ignore
        if not raw:
            raise RuntimeError("No candles returned.")
        last = raw[-2] if len(raw) >= 2 else raw[-1]
        # keys: time, into, inth, intl, intc depending on build
        d = datetime.fromtimestamp(int(last.get("time", end))).date()
        return OHLC(
            d=d,
            open=float(last.get("into", last.get("open", 0.0)) or 0.0),
            high=float(last.get("inth", last.get("high", 0.0)) or 0.0),
            low=float(last.get("intl", last.get("low", 0.0)) or 0.0),
            close=float(last.get("intc", last.get("close", 0.0)) or 0.0),
        )

    def place_order(
        self,
        symbol: SymbolKey,
        side: Side,
        qty: int,
        product: Product,
        order_type: str,
        price: Optional[float] = None,
    ) -> Order:
        if not self._api:
            raise RuntimeError("Shoonya not logged in.")
        # Shoonya requires exchange, tradingsymbol/token, product, price type.
        try:
            buy_sell = "B" if side == Side.BUY else "S"
            prd = product.value
            prctype = "MKT" if order_type.upper() == "MARKET" else "LMT"
            ret = self._api.place_order(  # type: ignore
                buy_or_sell=buy_sell,
                product_type=prd,
                exchange=symbol.exchange,
                tradingsymbol=symbol.tradingsymbol,
                quantity=int(qty),
                discloseqty=0,
                price_type=prctype,
                price=price if prctype == "LMT" else 0,
                trigger_price=0,
                retention="DAY",
                remarks="algo_platform",
            )
            oid = ret.get("norenordno") if isinstance(ret, dict) else None
            if not oid:
                raise RuntimeError(f"Unexpected response: {ret}")
            return Order(order_id=str(oid), symbol=symbol, side=side, qty=int(qty), product=product, order_type=order_type.upper(), price=price)
        except Exception as e:
            raise RuntimeError(f"Shoonya place_order failed: {e}") from e

    def modify_order(self, order_id: str, qty: Optional[int] = None, price: Optional[float] = None) -> Order:
        if not self._api:
            raise RuntimeError("Shoonya not logged in.")
        try:
            if hasattr(self._api, "modify_order"):
                self._api.modify_order(norenordno=order_id, newquantity=qty, newprice=price)  # type: ignore
            return Order(order_id=str(order_id), symbol=SymbolKey("NSE", "UNKNOWN", "CASH"), side=Side.BUY, qty=0, product=Product.MIS, order_type="UNKNOWN")
        except Exception as e:
            raise RuntimeError(f"Shoonya modify_order failed: {e}") from e

    def cancel_order(self, order_id: str) -> Order:
        if not self._api:
            raise RuntimeError("Shoonya not logged in.")
        try:
            if hasattr(self._api, "cancel_order"):
                self._api.cancel_order(norenordno=order_id)  # type: ignore
            return Order(order_id=str(order_id), symbol=SymbolKey("NSE", "UNKNOWN", "CASH"), side=Side.BUY, qty=0, product=Product.MIS, order_type="UNKNOWN")
        except Exception as e:
            raise RuntimeError(f"Shoonya cancel_order failed: {e}") from e

    def get_positions(self):
        if not self._api:
            raise RuntimeError("Shoonya not logged in.")
        from algo_platform.models import Position

        out = []
        if hasattr(self._api, "get_positions"):
            raw = self._api.get_positions()  # type: ignore
            for p in raw or []:
                sym = SymbolKey(exchange=p.get("exch", "NSE"), segment="CASH", tradingsymbol=p.get("tsym", ""))
                out.append(
                    Position(
                        symbol=sym,
                        net_qty=int(p.get("netqty", 0) or 0),
                        avg_price=float(p.get("netavgprc", 0.0) or 0.0),
                        realized_pnl=float(p.get("rpnl", 0.0) or 0.0),
                        unrealized_pnl=float(p.get("urmtom", 0.0) or 0.0),
                    )
                )
        return out

    def get_orders(self):
        if not self._api:
            raise RuntimeError("Shoonya not logged in.")
        out = []
        if hasattr(self._api, "get_order_book"):
            raw = self._api.get_order_book()  # type: ignore
            for o in raw or []:
                sym = SymbolKey(exchange=o.get("exch", "NSE"), segment="CASH", tradingsymbol=o.get("tsym", ""))
                side = Side.BUY if o.get("trantype") == "B" else Side.SELL
                out.append(
                    Order(
                        order_id=str(o.get("norenordno")),
                        symbol=sym,
                        side=side,
                        qty=int(o.get("qty", 0) or 0),
                        product=Product.MIS,
                        order_type=str(o.get("prctyp", "MKT")),
                    )
                )
        return out

    def websocket_connect(self, on_tick: TickCallback) -> None:
        if not self._api:
            raise RuntimeError("Shoonya not logged in.")
        self._on_tick = on_tick
        if not hasattr(self._api, "start_websocket"):
            raise RuntimeError("Shoonya websocket not available via installed SDK.")

        def _on_open():
            log.info("Shoonya websocket connected")

        def _on_close():
            log.warning("Shoonya websocket closed")

        def _on_tick(msg):
            try:
                ltp = float(msg.get("lp", 0.0) or 0.0)
                tsym = msg.get("tsym") or msg.get("ts") or ""
                exch = msg.get("e") or msg.get("exch") or "NSE"
                sym = SymbolKey(exchange=exch, segment="CASH", tradingsymbol=str(tsym))
                self._on_tick(Tick(symbol=sym, ltp=ltp, ts=datetime.utcnow()))
            except Exception:
                log.exception("Shoonya tick parse error")

        self._api.start_websocket(order_update_callback=lambda *_: None, subscribe_callback=_on_tick, socket_open_callback=_on_open, socket_close_callback=_on_close)  # type: ignore

    def websocket_disconnect(self) -> None:
        self._on_tick = None
        try:
            if self._api and hasattr(self._api, "close_websocket"):
                self._api.close_websocket()  # type: ignore
        except Exception:
            pass

    def websocket_subscribe(self, symbols: List[SymbolKey]) -> None:
        if not self._api:
            raise RuntimeError("Shoonya not logged in.")
        if not hasattr(self._api, "subscribe"):
            return
        toks = []
        for s in symbols:
            self.ensure_symbol(s)
            exch = self._exch_by_key[s.key()]
            token = self._token_by_key[s.key()]
            toks.append(f"{exch}|{token}")
            self._subscribed[s.key()] = s
        if toks:
            self._api.subscribe(toks)  # type: ignore

    def websocket_unsubscribe(self, symbols: List[SymbolKey]) -> None:
        for s in symbols:
            self._subscribed.pop(s.key(), None)

