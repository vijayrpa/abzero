from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from PySide6 import QtCore, QtWidgets

from algo_platform.brokers.aliceblue import AliceBlueBroker
from algo_platform.brokers.paper import PaperBroker
from algo_platform.brokers.shoonya import ShoonyaBroker
from algo_platform.brokers.zerodha import ZerodhaKiteBroker
from algo_platform.utils.secure_store import SecureStore, redact_dict
from algo_platform.utils.settings import Settings


@dataclass(frozen=True)
class LoginOutcome:
    broker_name: str
    broker: Any
    creds: Dict[str, Any]


BROKER_CHOICES = ["AliceBlue", "Zerodha", "Shoonya", "Paper"]


def _default_creds_template(broker_name: str) -> Dict[str, Any]:
    if broker_name == "AliceBlue":
        return {"user_id": "", "api_key": "", "access_token": ""}
    if broker_name == "Zerodha":
        return {"api_key": "", "api_secret": "", "access_token": "", "request_token": ""}
    if broker_name == "Shoonya":
        return {"user": "", "password": "", "twofa": "", "vendor_code": "", "api_secret": "", "imei": ""}
    return {}


def _make_broker(broker_name: str):
    if broker_name == "AliceBlue":
        return AliceBlueBroker()
    if broker_name == "Zerodha":
        return ZerodhaKiteBroker()
    if broker_name == "Shoonya":
        return ShoonyaBroker()
    return PaperBroker()


class LoginDialog(QtWidgets.QDialog):
    def __init__(self, settings: Settings, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{settings.app_name} - Login")
        self.setMinimumWidth(720)

        self._settings = settings
        self._store = SecureStore(path=settings.credentials_file, iterations=settings.kdf_iterations)
        self._outcome: Optional[LoginOutcome] = None

        self.broker_combo = QtWidgets.QComboBox()
        self.broker_combo.addItems(BROKER_CHOICES)

        self.passphrase = QtWidgets.QLineEdit()
        self.passphrase.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.passphrase.setPlaceholderText("Encryption passphrase (required to load/save creds)")

        self.creds_text = QtWidgets.QPlainTextEdit()
        self.creds_text.setPlaceholderText("Broker credentials JSON (will be encrypted locally)")

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)

        self.btn_load = QtWidgets.QPushButton("Load Saved")
        self.btn_save = QtWidgets.QPushButton("Save Encrypted")
        self.btn_login = QtWidgets.QPushButton("Login")

        self.btn_load.clicked.connect(self.on_load)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_login.clicked.connect(self.on_login)
        self.broker_combo.currentTextChanged.connect(self.on_broker_change)

        form = QtWidgets.QFormLayout()
        form.addRow("Broker", self.broker_combo)
        form.addRow("Passphrase", self.passphrase)
        form.addRow("Credentials JSON", self.creds_text)

        btns = QtWidgets.QHBoxLayout()
        btns.addWidget(self.btn_load)
        btns.addWidget(self.btn_save)
        btns.addStretch(1)
        btns.addWidget(self.btn_login)

        root = QtWidgets.QVBoxLayout()
        root.addLayout(form)
        root.addWidget(self.status)
        root.addLayout(btns)
        self.setLayout(root)

        self.on_broker_change(self.broker_combo.currentText())

    def outcome(self) -> Optional[LoginOutcome]:
        return self._outcome

    def on_broker_change(self, broker_name: str) -> None:
        tpl = _default_creds_template(broker_name)
        self.creds_text.setPlainText(json.dumps(tpl, indent=2))
        if broker_name == "Paper":
            self.creds_text.setPlainText("{}")

    def _get_passphrase(self) -> str:
        p = self.passphrase.text().strip()
        if not p:
            raise ValueError("Passphrase is required (for encrypted local storage).")
        return p

    def _get_creds(self) -> Dict[str, Any]:
        txt = self.creds_text.toPlainText().strip()
        if not txt:
            return {}
        try:
            d = json.loads(txt)
        except Exception as e:
            raise ValueError(f"Invalid credentials JSON: {e}") from e
        if not isinstance(d, dict):
            raise ValueError("Credentials JSON must be an object/dict.")
        return d

    def on_load(self) -> None:
        broker_name = self.broker_combo.currentText()
        try:
            passphrase = self._get_passphrase()
            d = self._store.get_broker_creds(passphrase, broker_name)
            if not d:
                d = _default_creds_template(broker_name)
            self.creds_text.setPlainText(json.dumps(d, indent=2))
            self.status.setText(f"Loaded saved credentials for {broker_name}: {redact_dict(d)}")
        except Exception as e:
            self.status.setText(f"Load failed: {e}")

    def on_save(self) -> None:
        broker_name = self.broker_combo.currentText()
        try:
            passphrase = self._get_passphrase()
            creds = self._get_creds()
            self._store.set_broker_creds(passphrase, broker_name, creds)
            self.status.setText(f"Saved encrypted credentials for {broker_name}.")
        except Exception as e:
            self.status.setText(f"Save failed: {e}")

    def on_login(self) -> None:
        broker_name = self.broker_combo.currentText()
        try:
            passphrase = self._get_passphrase()
            creds = self._get_creds()
        except Exception as e:
            self.status.setText(str(e))
            return

        broker = _make_broker(broker_name)
        try:
            res = broker.login(creds)
        except Exception as e:
            self.status.setText(f"Login error: {e}")
            return

        if not res.ok:
            self.status.setText(res.message)
            return

        # Auto download contract master at login (best-effort).
        try:
            fp = broker.download_contract_master(self._settings.contract_master_dir)
            if fp:
                # For Zerodha, load instruments immediately.
                if broker_name == "Zerodha" and hasattr(broker, "load_instruments_csv"):
                    broker.load_instruments_csv(fp)
        except Exception as e:
            # Non-fatal; still allow login.
            self.status.setText(f"{res.message} (Contract master warning: {e})")
        else:
            self.status.setText(res.message)

        # Save creds (including access_token if user pasted it).
        try:
            self._store.set_broker_creds(passphrase, broker_name, creds)
        except Exception:
            pass

        self._outcome = LoginOutcome(broker_name=broker_name, broker=broker, creds=creds)
        self.accept()

