"""
Higher Timeframe (HTF) Confirmation
Validates signal direction against the broader trend using a higher timeframe.

Rules (Wyckoff Five-Step Approach):
  1. Determine present position — match with HTF structure
  2. Trend of the index/market — HTF must confirm direction
  3. Time commitment — trend must have been in place a minimum number of bars
"""

from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from .phases import Phase, PhaseDetector


@dataclass
class HTFResult:
    htf_phase: Phase    = Phase.NONE
    htf_bias: str       = "neutral"  # bullish / bearish / neutral
    aligned: bool       = False      # True if HTF aligns with current signal
    confidence: float   = 0.0
    notes: list[str]    = field(default_factory=list)


class HTFConfirmation:
    """
    Fetches the HTF OHLCV data and determines whether it confirms a trade.

    Usage with MT5:
        htf_df = <fetch H4 data>
        htf_conf = HTFConfirmation()
        result = htf_conf.confirm(htf_df, signal=1)  # 1=long, -1=short
    """

    def __init__(self, trend_bars: int = 20, vol_lookback: int = 20):
        self.trend_bars  = trend_bars
        self.vol_lookback = vol_lookback
        self._detector   = PhaseDetector(lookback=100, trend_bars=trend_bars)

    def confirm(self, htf_df: pd.DataFrame, signal: int) -> HTFResult:
        """
        signal: 1 = long bias, -1 = short bias
        Returns HTFResult with .aligned telling if HTF agrees.
        """
        result = HTFResult()
        if len(htf_df) < self.trend_bars + 5:
            result.notes = ["HTF: insufficient data — skipping confirmation"]
            result.aligned = True  # Don't block trade when no HTF data
            return result

        phase_result = self._detector.detect(htf_df)
        result.htf_phase = phase_result.phase

        # Derive HTF bias from slope
        slope = phase_result.trend_slope
        if slope > 0.0005:
            result.htf_bias = "bullish"
        elif slope < -0.0005:
            result.htf_bias = "bearish"
        else:
            result.htf_bias = "neutral"

        # Alignment check
        if signal == 1 and result.htf_bias in ("bullish", "neutral"):
            result.aligned    = True
            result.confidence = 80.0 if result.htf_bias == "bullish" else 55.0
            result.notes      = [f"HTF confirms long: {result.htf_phase.value} / {result.htf_bias}"]
        elif signal == -1 and result.htf_bias in ("bearish", "neutral"):
            result.aligned    = True
            result.confidence = 80.0 if result.htf_bias == "bearish" else 55.0
            result.notes      = [f"HTF confirms short: {result.htf_phase.value} / {result.htf_bias}"]
        else:
            result.aligned    = False
            result.confidence = 20.0
            result.notes      = [
                f"HTF CONTRA: signal={signal}, HTF={result.htf_bias} — trade blocked"
            ]

        return result
