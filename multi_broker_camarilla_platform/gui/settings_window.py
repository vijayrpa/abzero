
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
