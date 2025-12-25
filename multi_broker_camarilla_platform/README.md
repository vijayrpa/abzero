
## Multi-Broker Advanced Camarilla Trading Platform (Desktop / Tkinter)

This project is a **production-style, desktop-based algorithmic trading platform** for Indian markets using an **Advanced Camarilla strategy** on **5-minute candles**.

### Segments supported (architecture is segment-agnostic)
- **NSE Cash (Equity)**, **BSE Cash**
- **NSE F&O** (Index & Stock options)
- **MCX** (Commodity futures & options)
- **CDS** (Currency derivatives)
- Indices: **NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY**

### Multi-broker support (via unified abstraction layer)
- Zerodha (Kite Connect)
- AliceBlue (pya3)
- Shoonya / Finvasia (Noren API)
- Angel One (SmartAPI)

### Key capabilities
- **Live trading** (broker SDKs + credentials required)
- **Paper trading** (works out of the box)
- **Websocket-first tick engine** (no market polling) with auto-reconnect
- Tick-to-5m candle aggregation
- Advanced Camarilla: **H3/H4/L3/L4**
- Options execution: auto weekly expiry, ATM strike, CE/PE selection, lot size
- Risk: 1% max risk per trade, daily loss limit, max trades/day, one active trade/symbol, global kill switch
- Telegram alerts + Telegram **STOP** kill switch
- CSV backtesting using the same strategy logic

### Install

From the repo root:

```bash
python generate_project.py --force
python -m venv .venv
source .venv/bin/activate
pip install -r multi_broker_camarilla_platform/requirements.txt
```

### Run (GUI)

```bash
python multi_broker_camarilla_platform/main.py
```

### Run (Backtest)

Put a CSV into `multi_broker_camarilla_platform/data/` with at least:
`timestamp,open,high,low,close,volume`

Example:

```bash
python multi_broker_camarilla_platform/main.py --backtest --csv multi_broker_camarilla_platform/data/sample_5m.csv --symbol NIFTY --segment NSE_FNO --paper
```

### Credentials / Security
- Credentials are stored locally in an **encrypted vault** using a GUI-managed **master password**.
- Broker access tokens and Telegram tokens are **not hardcoded** in strategy code.

### Important
- Live trading requires correct broker credentials and may require enabling your broker's websocket / market data permissions.
- This platform includes **hard risk controls** but you are responsible for compliance, connectivity, broker limitations, and operational monitoring.
