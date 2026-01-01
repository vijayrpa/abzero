from __future__ import annotations

import os
import sys

from PySide6 import QtWidgets

from algo_platform.gui.dashboard import DashboardWindow
from algo_platform.gui.login import LoginDialog
from algo_platform.utils.logging_setup import setup_logging
from algo_platform.utils.settings import load_settings


def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    settings_path = os.path.join(repo_root, "algo_platform", "config", "settings.json")
    settings = load_settings(settings_path)

    # Ensure data dirs exist early.
    os.makedirs(settings.contract_master_dir, exist_ok=True)
    os.makedirs(settings.trade_logs_dir, exist_ok=True)

    setup_logging(log_dir=settings.trade_logs_dir, level=settings.log_level)

    app = QtWidgets.QApplication(sys.argv)
    login = LoginDialog(settings=settings)
    if login.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return 0
    outcome = login.outcome()
    if not outcome:
        return 1

    w = DashboardWindow(settings=settings, broker=outcome.broker)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

