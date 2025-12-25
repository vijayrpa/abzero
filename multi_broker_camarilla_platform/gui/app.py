
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
