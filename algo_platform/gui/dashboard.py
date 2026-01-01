from __future__ import annotations

import math
from dataclasses import replace
from typing import Dict, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from algo_platform.brokers.base import BrokerBase
from algo_platform.execution.order_manager import OrderManager
from algo_platform.models import (
    EntryType,
    PerSymbolConfig,
    StrategyRow,
    StrategyType,
    SymbolKey,
    TradeMode,
)
from algo_platform.risk.risk_manager import RiskManager
from algo_platform.strategies.camarilla import compute_advanced_camarilla_levels
from algo_platform.strategies.strategy_engine import StrategyEngine
from algo_platform.utils.excel_loader import load_manual_strategy_excel
from algo_platform.utils.settings import Settings
from algo_platform.websocket.tick_engine import TickEngine


COLS = [
    "Symbol",
    "Strategy Type",
    "LTP",
    "Open",
    "High",
    "Low",
    "Prev Close",
    "Buy Level",
    "Buy T1",
    "Buy T2",
    "Buy SL",
    "Sell Level",
    "Sell T1",
    "Sell T2",
    "Sell SL",
    "Qty",
    "Entry Type",
    "Buy Count",
    "Sell Count",
    "Trailing SL",
    "Trail Value",
    "Strategy ON/OFF",
    "Risk ON/OFF",
    "Daily Loss (₹)",
    "Daily Profit (₹)",
    "Manual Exit",
    "Restart",
    "Trade Mode",
    "PnL",
    "Trades Count",
    "Status",
]


def _row_key(r: StrategyRow) -> str:
    return r.symbol.key() + "|" + r.strategy_type.value


class AddSymbolDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Symbol (Camarilla)")
        self.setMinimumWidth(420)

        self.symbol = QtWidgets.QLineEdit()
        self.exchange = QtWidgets.QComboBox()
        self.exchange.addItems(["NSE", "BSE", "NFO", "MCX", "CDS"])
        self.segment = QtWidgets.QComboBox()
        self.segment.addItems(["CASH", "NFO", "MCX", "CDS", "INDEX"])

        self.qty = QtWidgets.QSpinBox()
        self.qty.setRange(1, 10_000_000)
        self.qty.setValue(1)

        self.btn_ok = QtWidgets.QPushButton("Add")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        form = QtWidgets.QFormLayout()
        form.addRow("Symbol", self.symbol)
        form.addRow("Exchange", self.exchange)
        form.addRow("Segment", self.segment)
        form.addRow("Qty", self.qty)

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_ok)

        root = QtWidgets.QVBoxLayout()
        root.addLayout(form)
        root.addLayout(btns)
        self.setLayout(root)

    def get(self) -> Optional[SymbolKey]:
        if self.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return None
        sym = self.symbol.text().strip().upper()
        if not sym:
            return None
        return SymbolKey(exchange=self.exchange.currentText(), segment=self.segment.currentText(), tradingsymbol=sym)


class DashboardWindow(QtWidgets.QMainWindow):
    def __init__(self, settings: Settings, broker: BrokerBase) -> None:
        super().__init__()
        self._settings = settings
        self._broker = broker

        self._tick_engine = TickEngine(broker)
        self._om = OrderManager(broker, trade_logs_dir=settings.trade_logs_dir)
        self._risk = RiskManager()
        self._engine = StrategyEngine(self._tick_engine, self._om, self._risk)

        self.setWindowTitle(settings.app_name)
        self.resize(1500, 720)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

        toolbar = QtWidgets.QToolBar("Main")
        self.addToolBar(toolbar)

        self.btn_add = QtWidgets.QAction("Add Camarilla Symbol", self)
        self.btn_excel = QtWidgets.QAction("Load Manual Excel", self)
        self.btn_exit_sel = QtWidgets.QAction("Manual Exit Selected", self)
        self.btn_start_ticks = QtWidgets.QAction("Start Ticks", self)
        self.btn_stop_ticks = QtWidgets.QAction("Stop Ticks", self)
        toolbar.addAction(self.btn_add)
        toolbar.addAction(self.btn_excel)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_exit_sel)
        toolbar.addSeparator()
        toolbar.addAction(self.btn_start_ticks)
        toolbar.addAction(self.btn_stop_ticks)

        self.btn_add.triggered.connect(self.on_add_symbol)
        self.btn_excel.triggered.connect(self.on_load_excel)
        self.btn_exit_sel.triggered.connect(self.on_manual_exit_selected)
        self.btn_start_ticks.triggered.connect(self._tick_engine.start)
        self.btn_stop_ticks.triggered.connect(self._tick_engine.stop)

        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)

        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.table)
        root.setLayout(layout)
        self.setCentralWidget(root)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.refresh_view)
        self._timer.start()

        self._tick_engine.start()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        try:
            self._tick_engine.stop()
        except Exception:
            pass
        try:
            self._broker.logout()
        except Exception:
            pass
        super().closeEvent(event)

    def on_add_symbol(self) -> None:
        dlg = AddSymbolDialog(self)
        sym = dlg.get()
        if not sym:
            return

        try:
            prev = self._broker.get_previous_day_ohlc(sym)
            levels = compute_advanced_camarilla_levels(prev)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Camarilla Error", f"Failed to compute Camarilla levels: {e}")
            return

        cfg = PerSymbolConfig(qty=1)
        row = StrategyRow(symbol=sym, strategy_type=StrategyType.CAMARILLA, levels=levels, config=cfg)
        row.state.running = True
        row.state.status = "Running"

        self._engine.upsert_row(row)
        try:
            self._tick_engine.subscribe([sym])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Subscribe Error", str(e))
        self._add_or_update_table_row(row)

    def on_load_excel(self) -> None:
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Manual Strategy Excel", filter="Excel (*.xlsx *.xls)")
        if not fp:
            return
        try:
            res = load_manual_strategy_excel(fp)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Excel Error", str(e))
            return
        for row in res.rows:
            row.state.running = True
            row.state.status = "Running"
            self._engine.upsert_row(row)
            try:
                self._tick_engine.subscribe([row.symbol])
            except Exception:
                # Some brokers need token mapping; still show row.
                pass
            self._add_or_update_table_row(row)

    def on_manual_exit_selected(self) -> None:
        sel = self.table.selectionModel().selectedRows()
        for idx in sel:
            rk = self._row_key_at_row(idx.row())
            if not rk:
                continue
            sym = self._row_symbol_from_key(rk)
            ltp = self._tick_engine.get_snapshot(sym).ltp
            if ltp:
                self._engine.manual_exit(rk, ltp, reason="ManualMulti")

    def _row_symbol_from_key(self, row_key: str) -> SymbolKey:
        # row_key format: exchange:segment:tradingsymbol|StrategyType
        left = row_key.split("|", 1)[0]
        exch, seg, tsym = left.split(":", 2)
        return SymbolKey(exchange=exch, segment=seg, tradingsymbol=tsym)

    def _row_key_at_row(self, r: int) -> Optional[str]:
        it = self.table.item(r, 0)
        if not it:
            return None
        return it.data(QtCore.Qt.ItemDataRole.UserRole)

    def _find_table_row(self, row_key: str) -> Optional[int]:
        for r in range(self.table.rowCount()):
            if self._row_key_at_row(r) == row_key:
                return r
        return None

    def _add_or_update_table_row(self, row: StrategyRow) -> None:
        rk = _row_key(row)
        ridx = self._find_table_row(rk)
        if ridx is None:
            ridx = self.table.rowCount()
            self.table.insertRow(ridx)

        def set_text(col: int, text: str) -> None:
            it = QtWidgets.QTableWidgetItem(text)
            if col == 0:
                it.setData(QtCore.Qt.ItemDataRole.UserRole, rk)
            it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(ridx, col, it)

        set_text(COLS.index("Symbol"), row.symbol.tradingsymbol)
        set_text(COLS.index("Strategy Type"), row.strategy_type.value)
        for c in ("LTP", "Open", "High", "Low", "Prev Close"):
            set_text(COLS.index(c), "0.00")
        set_text(COLS.index("Buy Level"), f"{row.levels.buy_level:.2f}")
        set_text(COLS.index("Buy T1"), f"{row.levels.buy_t1:.2f}")
        set_text(COLS.index("Buy T2"), f"{row.levels.buy_t2:.2f}")
        set_text(COLS.index("Buy SL"), f"{row.levels.buy_sl:.2f}")
        set_text(COLS.index("Sell Level"), f"{row.levels.sell_level:.2f}")
        set_text(COLS.index("Sell T1"), f"{row.levels.sell_t1:.2f}")
        set_text(COLS.index("Sell T2"), f"{row.levels.sell_t2:.2f}")
        set_text(COLS.index("Sell SL"), f"{row.levels.sell_sl:.2f}")

        # Qty
        qty = QtWidgets.QSpinBox()
        qty.setRange(1, 10_000_000)
        qty.setValue(int(row.config.qty))
        qty.valueChanged.connect(lambda v, rk=rk: self._update_cfg(rk, qty=v))
        self.table.setCellWidget(ridx, COLS.index("Qty"), qty)

        # Entry Type
        et = QtWidgets.QComboBox()
        et.addItems([EntryType.BUY_ONLY.value, EntryType.SELL_ONLY.value, EntryType.BOTH.value])
        et.setCurrentText(row.config.entry_type.value)
        et.currentTextChanged.connect(lambda v, rk=rk: self._update_cfg(rk, entry_type=v))
        self.table.setCellWidget(ridx, COLS.index("Entry Type"), et)

        # Counts
        bc = QtWidgets.QSpinBox()
        bc.setRange(0, 1000)
        bc.setValue(int(row.config.max_buy_trades))
        bc.valueChanged.connect(lambda v, rk=rk: self._update_cfg(rk, max_buy_trades=v))
        self.table.setCellWidget(ridx, COLS.index("Buy Count"), bc)

        sc = QtWidgets.QSpinBox()
        sc.setRange(0, 1000)
        sc.setValue(int(row.config.max_sell_trades))
        sc.valueChanged.connect(lambda v, rk=rk: self._update_cfg(rk, max_sell_trades=v))
        self.table.setCellWidget(ridx, COLS.index("Sell Count"), sc)

        # Trailing
        tr_on = QtWidgets.QCheckBox()
        tr_on.setChecked(bool(row.config.trailing_on))
        tr_on.stateChanged.connect(lambda _, rk=rk: self._update_cfg(rk, trailing_on=tr_on.isChecked()))
        self.table.setCellWidget(ridx, COLS.index("Trailing SL"), tr_on)

        tr_val = QtWidgets.QDoubleSpinBox()
        tr_val.setDecimals(2)
        tr_val.setRange(0.0, 1e9)
        tr_val.setValue(float(row.config.trail_value))
        tr_val.valueChanged.connect(lambda v, rk=rk: self._update_cfg(rk, trail_value=v))
        self.table.setCellWidget(ridx, COLS.index("Trail Value"), tr_val)

        # Strategy ON/OFF -> also controls running state.
        st_on = QtWidgets.QCheckBox()
        st_on.setChecked(bool(row.config.strategy_on))
        st_on.stateChanged.connect(lambda _, rk=rk: self._toggle_strategy(rk, st_on.isChecked()))
        self.table.setCellWidget(ridx, COLS.index("Strategy ON/OFF"), st_on)

        # Risk
        rk_on = QtWidgets.QCheckBox()
        rk_on.setChecked(bool(row.config.risk_on))
        rk_on.stateChanged.connect(lambda _, rk=rk: self._update_cfg(rk, risk_on=rk_on.isChecked()))
        self.table.setCellWidget(ridx, COLS.index("Risk ON/OFF"), rk_on)

        dl = QtWidgets.QDoubleSpinBox()
        dl.setDecimals(2)
        dl.setRange(0.0, 1e12)
        dl.setValue(float(row.config.daily_loss_limit))
        dl.valueChanged.connect(lambda v, rk=rk: self._update_cfg(rk, daily_loss_limit=v))
        self.table.setCellWidget(ridx, COLS.index("Daily Loss (₹)"), dl)

        dp = QtWidgets.QDoubleSpinBox()
        dp.setDecimals(2)
        dp.setRange(0.0, 1e12)
        dp.setValue(float(row.config.daily_profit_limit))
        dp.valueChanged.connect(lambda v, rk=rk: self._update_cfg(rk, daily_profit_limit=v))
        self.table.setCellWidget(ridx, COLS.index("Daily Profit (₹)"), dp)

        # Manual exit
        btn_exit = QtWidgets.QPushButton("Exit")
        btn_exit.clicked.connect(lambda _, rk=rk: self._manual_exit(rk))
        self.table.setCellWidget(ridx, COLS.index("Manual Exit"), btn_exit)

        # Restart
        btn_restart = QtWidgets.QPushButton("Restart")
        btn_restart.clicked.connect(lambda _, rk=rk: self._engine.restart(rk))
        self.table.setCellWidget(ridx, COLS.index("Restart"), btn_restart)

        # Trade mode
        tm = QtWidgets.QComboBox()
        tm.addItems([TradeMode.PAPER.value, TradeMode.REAL.value])
        tm.setCurrentText(row.config.trade_mode.value)
        tm.currentTextChanged.connect(lambda v, rk=rk: self._update_cfg(rk, trade_mode=v))
        self.table.setCellWidget(ridx, COLS.index("Trade Mode"), tm)

        # Derived fields
        for c in ("PnL", "Trades Count", "Status"):
            set_text(COLS.index(c), "0")

    def _toggle_strategy(self, row_key: str, on: bool) -> None:
        # Turn on/off and start/stop engine for this row.
        self._update_cfg(row_key, strategy_on=on)
        self._engine.set_running(row_key, on)

    def _manual_exit(self, row_key: str) -> None:
        sym = self._row_symbol_from_key(row_key)
        ltp = self._tick_engine.get_snapshot(sym).ltp
        if ltp:
            self._engine.manual_exit(row_key, ltp, reason="Manual")

    def _update_cfg(self, row_key: str, **kwargs) -> None:
        rows = {(_row_key(r)): r for r in self._engine.list_rows()}
        r = rows.get(row_key)
        if not r:
            return
        cfg = r.config

        if "qty" in kwargs:
            cfg.qty = int(kwargs["qty"])
        if "entry_type" in kwargs:
            cfg.entry_type = EntryType(kwargs["entry_type"])
        if "max_buy_trades" in kwargs:
            cfg.max_buy_trades = int(kwargs["max_buy_trades"])
        if "max_sell_trades" in kwargs:
            cfg.max_sell_trades = int(kwargs["max_sell_trades"])
        if "trailing_on" in kwargs:
            cfg.trailing_on = bool(kwargs["trailing_on"])
        if "trail_value" in kwargs:
            cfg.trail_value = float(kwargs["trail_value"])
        if "strategy_on" in kwargs:
            cfg.strategy_on = bool(kwargs["strategy_on"])
        if "trade_mode" in kwargs:
            cfg.trade_mode = TradeMode(kwargs["trade_mode"])
        if "risk_on" in kwargs:
            cfg.risk_on = bool(kwargs["risk_on"])
        if "daily_loss_limit" in kwargs:
            cfg.daily_loss_limit = float(kwargs["daily_loss_limit"])
        if "daily_profit_limit" in kwargs:
            cfg.daily_profit_limit = float(kwargs["daily_profit_limit"])

        self._engine.set_row_config(row_key, cfg)

    def refresh_view(self) -> None:
        # Update tick/pnl/status columns.
        rows = self._engine.list_rows()
        for r in rows:
            rk = _row_key(r)
            ridx = self._find_table_row(rk)
            if ridx is None:
                continue

            snap = self._tick_engine.get_snapshot(r.symbol)
            self._set_num(ridx, "LTP", snap.ltp)
            self._set_num(ridx, "Open", snap.open)
            self._set_num(ridx, "High", snap.high)
            self._set_num(ridx, "Low", snap.low)
            self._set_num(ridx, "Prev Close", snap.prev_close)

            pnl = self._om.paper_realized_pnl(r.symbol) + self._om.paper_unrealized_pnl(r.symbol, snap.ltp)
            self._set_text(ridx, "PnL", f"{pnl:.2f}")
            trades = r.state.buy_trades_done + r.state.sell_trades_done
            self._set_text(ridx, "Trades Count", str(trades))
            st = r.state.status
            if r.state.last_status_msg:
                st = f"{st} | {r.state.last_status_msg}"
            self._set_text(ridx, "Status", st)

        st = self._tick_engine.status()
        self.status_bar.showMessage(f"TickEngine connected={st.connected} last_error={st.last_error} last_tick={st.last_tick_at}")

    def _set_text(self, row: int, col_name: str, text: str) -> None:
        c = COLS.index(col_name)
        it = self.table.item(row, c)
        if not it:
            it = QtWidgets.QTableWidgetItem("")
            it.setFlags(it.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, c, it)
        it.setText(text)

    def _set_num(self, row: int, col_name: str, val: float) -> None:
        if val is None:
            return
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            return
        self._set_text(row, col_name, f"{float(val):.2f}")

