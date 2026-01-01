## Algo Trading Platform (India) – Advanced Camarilla + Manual Excel

This repo contains a desktop trading dashboard + backend Python engine with:
- **Advanced Camarilla** auto-levels from previous day H/L/C
- **Manual Excel strategy** (upload rows in predefined format)
- **Live tick fan-out engine** (one connection per broker; paper broker simulates ticks)
- **Paper trading** (realistic: LTP-driven entries/exits, SL/TGT, trailing SL, PnL, trade logs)
- **Real trading** via broker adapters (AliceBlue / Zerodha Kite / Shoonya), using the same engine
- **Encrypted local credential storage** (`algo_platform/config/credentials.enc`)

### Project layout

```text
algo_platform/
  brokers/ (AliceBlue / Zerodha / Shoonya / Paper)
  websocket/ (central tick engine)
  strategies/ (camarilla + manual excel + runtime)
  risk/ (per-symbol daily limits)
  execution/ (order + trade logging)
  gui/ (login + dashboard)
  data/contract_master/ (downloaded instruments/masters)
  data/trade_logs/ (CSV trade logs + app.log)
  utils/
  config/settings.json
main.py
```

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Optional broker SDKs (for REAL trading):**
- **Zerodha**: `pip install kiteconnect`
- **AliceBlue**: `pip install alice-blue`
- **Shoonya**: install `NorenRestApiPy` as per Shoonya/Finvasia official docs (package name differs by distribution).

### Run

```bash
python main.py
```

### Login (Encrypted credentials)

On first run:
- choose a **passphrase** (used to encrypt/decrypt `credentials.enc`)
- paste credentials JSON for your broker
- click **Save Encrypted** (optional) then **Login**

### Manual Excel format (required columns)

The Excel must contain these exact headers:

```text
Symbol, Buy Level, Buy T1, Buy T2, Buy SL, Sell Level, Sell T1, Sell T2, Sell SL, Quantity
```

### Trailing SL behavior (exact)

Buy example:
- Entry 100, initial SL 90, Trail Value 5
- LTP hits 105 → SL becomes 95
- LTP hits 110 → SL becomes 100

(Sell logic is reversed.)

### Logs

- Trade CSV: `algo_platform/data/trade_logs/trades_YYYY-MM-DD.csv`
- App log: `algo_platform/data/trade_logs/app.log`
