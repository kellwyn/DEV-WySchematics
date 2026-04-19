"""
Wyckoff Bot — automated trade execution scaffold

Reuses the signal-lab detection engine and routes qualifying setups
to manual confirmation before placing MT5 orders.

Usage:
  1. Copy .env.example to .env
  2. pip install -r requirements.txt
  3. python main.py
"""

import os
import time
from dotenv import load_dotenv

from bot.connection import connect, disconnect
from bot.strategy   import scan_all, print_dashboard
from bot.trader     import confirm_and_execute

load_dotenv()

SYMBOLS          = [s.strip() for s in os.getenv("SYMBOLS",         "BTCUSD").split(",")]
TIMEFRAMES       = [t.strip() for t in os.getenv("TIMEFRAMES",      "H1").split(",")]
HTF              = os.getenv("HTF",               "H4")
SCAN_INTERVAL    = int(os.getenv("SCAN_INTERVAL", "60"))
LOOKBACK         = int(os.getenv("LOOKBACK",      "200"))
RISK_PERCENT     = float(os.getenv("RISK_PERCENT","1.0"))
MAX_LOT          = float(os.getenv("MAX_LOT",     "0.5"))
MIN_PROBABILITY  = float(os.getenv("MIN_PROB",    "65.0"))

_alerted: set = set()


def _alert_key(setup) -> str:
    return f"{setup.symbol}|{setup.timeframe}|{setup.direction}|{setup.entry:.5f}"


def run():
    print(f"\n  Wyckoff Bot starting...")
    print(f"  Symbols    : {', '.join(SYMBOLS)}")
    print(f"  Timeframes : {', '.join(TIMEFRAMES)}  |  HTF: {HTF}")
    print(f"  Risk/trade : {RISK_PERCENT}%  |  Max lot: {MAX_LOT}")
    print(f"  Interval   : every {SCAN_INTERVAL}s  |  Ctrl+C to stop\n")

    while True:
        try:
            setups = scan_all(SYMBOLS, TIMEFRAMES, HTF, LOOKBACK, MIN_PROBABILITY)
            print_dashboard(setups, SYMBOLS, TIMEFRAMES)

            for setup in setups:
                key = _alert_key(setup)
                if key not in _alerted:
                    _alerted.add(key)
                    confirm_and_execute(setup, RISK_PERCENT, MAX_LOT)

            if not setups:
                _alerted.clear()

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\n  Stopped.")
            break
        except Exception as e:
            print(f"  ERROR: {e}")
            time.sleep(SCAN_INTERVAL)


def main():
    try:
        connect()
        run()
    finally:
        disconnect()


if __name__ == "__main__":
    main()
