
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
