"""
Wyckoff Signal Lab — main entry point

Connects to MetaTrader 5, fetches OHLCV data on the configured timeframe
and higher timeframe, runs the full Wyckoff analysis pipeline, and prints
a live dashboard to the terminal on each new bar.

Usage:
  1. Copy .env.example to .env and fill in your symbols / settings
  2. pip install -r requirements.txt
  3. python main.py
"""

import os
import time
from datetime import datetime
from dotenv import load_dotenv
import MetaTrader5 as mt5
import pandas as pd

from lab.phases     import PhaseDetector
from lab.subphases  import SubPhaseDetector
from lab.indicators import Indicators
from lab.htf        import HTFConfirmation
from lab.confluence import ConfluenceEngine
from lab.dashboard  import Dashboard

load_dotenv()

SYMBOLS        = [s.strip() for s in os.getenv("SYMBOLS",        "BTCUSD").split(",")]
TIMEFRAME_STR  = os.getenv("TIMEFRAME",   "H1")
HTF_STR        = os.getenv("HTF",         "H4")
SCAN_INTERVAL  = int(os.getenv("SCAN_INTERVAL",  "60"))
LOOKBACK       = int(os.getenv("LOOKBACK",       "200"))
VOL_LOOKBACK   = int(os.getenv("VOL_LOOKBACK",   "20"))
VOL_SPIKE      = float(os.getenv("VOL_SPIKE_MULT", "2.0"))
VOL_DRYUP      = float(os.getenv("VOL_DRYUP_RATIO","0.5"))

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1,
}

# Phase history per symbol (tracks last confirmed phases for sequence scoring)
_phase_history: dict[str, list[str]] = {s: [] for s in SYMBOLS}
_last_bar:      dict[str, int]       = {s: 0   for s in SYMBOLS}


def fetch_df(symbol: str, tf: int, n: int) -> pd.DataFrame | None:
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df.rename(columns={"tick_volume": "volume"}, inplace=True, errors="ignore")
    return df


def analyse_symbol(symbol: str, tf: int, htf: int) -> None:
    df     = fetch_df(symbol, tf, LOOKBACK)
    htf_df = fetch_df(symbol, htf, 100)
    if df is None or htf_df is None:
        print(f"  [{symbol}] No data — skipping")
        return

    # Skip if same bar as last scan
    last_ts = int(df.index[-1].timestamp())
    if last_ts == _last_bar[symbol]:
        return
    _last_bar[symbol] = last_ts

    phase_det    = PhaseDetector(lookback=LOOKBACK, vol_lookback=VOL_LOOKBACK,
                                  vol_spike_mult=VOL_SPIKE, vol_dryup_ratio=VOL_DRYUP)
    sub_det      = SubPhaseDetector(vol_lookback=VOL_LOOKBACK,
                                     vol_spike_mult=VOL_SPIKE, vol_dryup_ratio=VOL_DRYUP)
    ind          = Indicators(vol_lookback=VOL_LOOKBACK, vol_spike_mult=VOL_SPIKE)
    htf_conf     = HTFConfirmation(trend_bars=20, vol_lookback=VOL_LOOKBACK)
    engine       = ConfluenceEngine()
    dash         = Dashboard(symbol, TIMEFRAME_STR, HTF_STR)

    phase_result    = phase_det.detect(df)
    subphase_result = sub_det.detect(df, phase_result)
    indicator_snap  = ind.compute(df)
    htf_result      = htf_conf.confirm(htf_df, subphase_result.signal)
    confluence      = engine.score(
        phase_result, subphase_result, indicator_snap, htf_result,
        phase_history=_phase_history[symbol]
    )

    # Track phase history (store only when phase changes)
    ph = phase_result.phase.value
    if not _phase_history[symbol] or _phase_history[symbol][-1] != ph:
        _phase_history[symbol].append(ph)
        if len(_phase_history[symbol]) > 8:
            _phase_history[symbol].pop(0)

    print(dash.render(
        phase_result, subphase_result, indicator_snap, htf_result, confluence,
        timestamp=datetime.utcnow()
    ))


def main():
    if not mt5.initialize():
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return

    tf  = TF_MAP.get(TIMEFRAME_STR, mt5.TIMEFRAME_H1)
    htf = TF_MAP.get(HTF_STR,       mt5.TIMEFRAME_H4)

    print(f"\n  Wyckoff Signal Lab starting...")
    print(f"  Symbols    : {', '.join(SYMBOLS)}")
    print(f"  Timeframe  : {TIMEFRAME_STR}  |  HTF: {HTF_STR}")
    print(f"  Interval   : every {SCAN_INTERVAL}s  |  Ctrl+C to stop\n")

    try:
        while True:
            for symbol in SYMBOLS:
                analyse_symbol(symbol, tf, htf)
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
