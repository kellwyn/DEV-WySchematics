# DEV-WySchematics

**Wyckoff Theory Schematics — Trading System**

A complete trading system built on Richard Wyckoff's cause-and-effect market theory.
Identifies the four major market phases and their sub-events, scores them with confluences,
and provides automated execution via both a Python bot and a MetaTrader 5 Expert Advisor.

---

## Repository Structure

```
DEV-WySchematics/
├── WySchematicsEA/     — MetaTrader 5 Expert Advisor (MQ5)
├── signal-lab/         — Wyckoff phase detection & signal engine (Python)
└── wyckoff-bot/        — Automated trade execution bot (Python + MT5)
```

---

## Strategy Overview

### The Four Market Phases

| Phase        | Description                              | Key Events                        |
|--------------|------------------------------------------|-----------------------------------|
| Accumulation | Institutional absorption at lows         | PS, SC, AR, ST, Spring, SOS, LPS  |
| Markup       | Price appreciation / trending up         | SOS breakout, LPS re-entries      |
| Distribution | Institutional offloading at highs        | PSY, BC, AR, UT/UTAD, SOW, LPSY   |
| Markdown     | Price depreciation / trending down       | SOW momentum, LPSY entries        |

### Core Principles

- **Supply and Demand** — Price moves when one side overwhelms the other
- **Cause and Effect** — Time in a trading range (cause) determines the magnitude of the move (effect)
- **Effort vs Result** — Volume is effort; price movement is result. Divergence signals absorption or exhaustion
- **Law of Effort vs Result** — Wide spread + high volume = strong effort; narrow spread + high volume = absorption

### Five-Step Approach (Wyckoff)

1. Determine present position and probable future trend
2. Select stocks/instruments in harmony with the trend
3. Select stocks with a sufficient cause
4. Determine readiness to move
5. Time commitment with the index

### Simplified Trading Strategy

1. Identify the trading range
2. Wait for Spring (accumulation) or Upthrust (distribution)
3. Confirm Sign of Strength / Sign of Weakness
4. Enter at demand/supply zone
5. Target the Markup / Markdown

---

## Directory Details

### `WySchematicsEA/`

MetaTrader 5 Expert Advisor for backtesting and automated execution.

**Features:**
- Full four-phase + sub-phase detection on any MT5 symbol/timeframe
- Per-phase and per-sub-phase trade toggles (e.g. only trade Springs and SOS)
- ATR-based or fixed-pip SL/TP
- Configurable risk % per trade with Risk:Reward ratio (toggleable)
- Hard max lot size cap
- Spread filter, max concurrent trades
- Higher timeframe confirmation (toggleable)
- Volume climax and dry-up detection

**Copy `WySchematicsEA.mq5` to your MT5 `Experts/` folder and compile.**

See [WySchematicsEA/CHANGELOG.md](WySchematicsEA/CHANGELOG.md) for version history.

---

### `signal-lab/`

Python-based signal engine. Connects to MT5, scans configured symbols,
and prints a live dashboard showing the current Wyckoff phase, sub-phase,
indicator readings, HTF confirmation, and a confluenced probability score.

**Architecture:**

```
signal-lab/
├── main.py
└── lab/
    ├── phases.py      — Four-phase detection (scoring model)
    ├── subphases.py   — Sub-phase event detection (SC, Spring, SOS, UT …)
    ├── indicators.py  — ATR, volume analysis, spread, effort/result, P&F cause
    ├── htf.py         — Higher timeframe confirmation
    ├── confluence.py  — Weighted probability scoring
    └── dashboard.py   — Terminal dashboard renderer
```

**Setup:**
```bash
cd signal-lab
cp .env.example .env   # edit SYMBOLS, TIMEFRAME, HTF
pip install -r requirements.txt
python main.py
```

---

### `wyckoff-bot/`

Scaffold for semi-automated execution. Reuses the signal-lab detection engine
and asks for manual confirmation before placing MT5 orders.

**Setup:**
```bash
cd wyckoff-bot
cp .env.example .env
pip install -r requirements.txt
python main.py
```

---

## Version History

| Version | Date       | Notes                                      |
|---------|------------|--------------------------------------------|
| 1.0.0   | 2026-04-20 | Initial release — all three components     |

---

## References

- Wyckoff Schematics chart: https://www.tradingview.com/chart/BTCUSDT/z7B2SlOy-Wyckoff-Schematics/
- Richard D. Wyckoff — "The Richard D. Wyckoff Method of Trading and Investing in Stocks"
