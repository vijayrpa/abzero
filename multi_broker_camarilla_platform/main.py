
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.logging_config import configure_logging
from gui.app import TradingApp
from backtest.engine import run_csv_backtest
from config.defaults import AppSettings, Segment


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Multi-broker Advanced Camarilla Trading Platform")
    p.add_argument("--backtest", action="store_true", help="Run CSV backtest instead of GUI.")
    p.add_argument("--csv", type=str, default="", help="CSV file for backtest.")
    p.add_argument("--symbol", type=str, default="NIFTY", help="Symbol for backtest.")
    p.add_argument("--segment", type=str, default="NSE_FNO", help="Segment (e.g., NSE_CASH, BSE_CASH, NSE_FNO, MCX, CDS).")
    p.add_argument("--paper", action="store_true", help="Force paper mode for backtest run.")
    return p.parse_args()


def main() -> int:
    configure_logging()
    args = _parse_args()

    if args.backtest:
        if not args.csv:
            print("Missing --csv path", file=sys.stderr)
            return 2
        seg = Segment.from_str(args.segment)
        settings = AppSettings.default()
        settings.trade_mode = "PAPER" if args.paper else settings.trade_mode
        csv_path = Path(args.csv)
        report = run_csv_backtest(
            csv_path=csv_path,
            symbol=args.symbol,
            segment=seg,
            settings=settings,
        )
        print(report.to_text())
        return 0

    app = TradingApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
