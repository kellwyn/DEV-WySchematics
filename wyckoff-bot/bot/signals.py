"""
Wyckoff signal bridge — imports the signal lab and converts results
into simple Setup objects that the trader can act on.
"""
from __future__ import annotations
from dataclasses import dataclass
import sys
import os

# Allow importing signal-lab without installing it as a package
_lab_path = os.path.join(os.path.dirname(__file__), "..", "..", "signal-lab")
if _lab_path not in sys.path:
    sys.path.insert(0, _lab_path)

import MetaTrader5 as mt5
import pandas as pd

from lab.phases     import PhaseDetector
from lab.subphases  import SubPhaseDetector
from lab.indicators import Indicators
from lab.htf        import HTFConfirmation
from lab.confluence import ConfluenceEngine

TF_MAP = {
    "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


@dataclass
class Setup:
    symbol:    str
    timeframe: str
    direction: str   # "BUY" | "SELL"
    phase:     str
    subphase:  str
    probability: float
    entry:     float
    atr:       float


def _fetch_df(symbol: str, tf: int, n: int) -> pd.DataFrame | None:
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.set_index("time", inplace=True)
    df.rename(columns={"tick_volume": "volume"}, inplace=True, errors="ignore")
    return df


def scan(
    symbol: str,
    timeframe: str,
    htf: str,
    lookback: int = 200,
    min_probability: float = 60.0,
) -> Setup | None:
    tf     = TF_MAP.get(timeframe, mt5.TIMEFRAME_H1)
    htf_tf = TF_MAP.get(htf,       mt5.TIMEFRAME_H4)

    df     = _fetch_df(symbol, tf, lookback)
    htf_df = _fetch_df(symbol, htf_tf, 100)
    if df is None or htf_df is None:
        return None

    phase_result    = PhaseDetector().detect(df)
    subphase_result = SubPhaseDetector().detect(df, phase_result)
    indicator_snap  = Indicators().compute(df)
    htf_result      = HTFConfirmation().confirm(htf_df, subphase_result.signal)
    confluence      = ConfluenceEngine().score(
        phase_result, subphase_result, indicator_snap, htf_result
    )

    if confluence.probability < min_probability or confluence.signal == 0:
        return None

    direction = "BUY" if confluence.signal == 1 else "SELL"
    entry     = mt5.symbol_info_tick(symbol)
    if entry is None:
        return None
    entry_price = entry.ask if direction == "BUY" else entry.bid

    return Setup(
        symbol      = symbol,
        timeframe   = timeframe,
        direction   = direction,
        phase       = phase_result.phase.value,
        subphase    = subphase_result.subphase.value,
        probability = confluence.probability,
        entry       = entry_price,
        atr         = indicator_snap.atr,
    )
