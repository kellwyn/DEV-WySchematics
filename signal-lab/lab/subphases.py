"""
Wyckoff Sub-Phase Detector
Identifies specific events within each major phase.

Accumulation sub-phases:
  PS   — Preliminary Support        (first support after downtrend)
  SC   — Selling Climax             (high-volume bear bar, reversal close)
  AR   — Automatic Rally            (short covering bounce off SC)
  ST   — Secondary Test             (low-vol retest of SC low)
  SPR  — Spring / Sweep             (false break below TR low)
  SOS  — Sign of Strength           (strong bull bar on rising volume)
  LPS  — Last Point of Support      (low-vol pullback after SOS)

Distribution sub-phases:
  PSY  — Preliminary Supply         (first supply after uptrend)
  BC   — Buying Climax              (high-volume bull bar, reversal close)
  AR   — Automatic Reaction         (selling pressure drop from BC)
  UT   — Upthrust / UTAD            (false break above TR high)
  SOW  — Sign of Weakness           (strong bear bar, expanding volume)
  LPSY — Last Point of Supply       (low-vol rally after SOW)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np
import pandas as pd

from .phases import Phase, PhaseResult


class SubPhase(str, Enum):
    NONE  = "—"
    # Accumulation
    PS    = "PS"
    SC    = "SC"
    AR    = "AR"
    ST    = "ST"
    SPR   = "Spring"
    SOS   = "SOS"
    LPS   = "LPS"
    # Distribution
    PSY   = "PSY"
    BC    = "BC"
    AR_D  = "AR-D"
    UT    = "UT"
    SOW   = "SOW"
    LPSY  = "LPSY"


@dataclass
class SubPhaseResult:
    subphase: SubPhase = SubPhase.NONE
    confidence: float  = 0.0
    signal: int        = 0     # 1=long, -1=short, 0=none
    notes: list[str]   = field(default_factory=list)


class SubPhaseDetector:
    """
    Given a PhaseResult and the OHLCV DataFrame, identifies the current
    sub-phase event and whether it generates a trade signal.
    """

    def __init__(
        self,
        vol_lookback: int = 20,
        vol_spike_mult: float = 2.0,
        vol_dryup_ratio: float = 0.5,
    ):
        self.vol_lookback    = vol_lookback
        self.vol_spike_mult  = vol_spike_mult
        self.vol_dryup_ratio = vol_dryup_ratio

    def detect(self, df: pd.DataFrame, phase_result: PhaseResult) -> SubPhaseResult:
        df = df.copy()
        if "tick_volume" in df.columns and "volume" not in df.columns:
            df["volume"] = df["tick_volume"]
        df["volume"] = df["volume"].replace(0, np.nan).ffill().fillna(1)

        if len(df) < self.vol_lookback + 2:
            return SubPhaseResult(notes=["Insufficient data"])

        avg_vol   = df["volume"].tail(self.vol_lookback).mean()
        last_bar  = df.iloc[-1]
        prev_bar  = df.iloc[-2]

        c, o, h, l = last_bar["close"], last_bar["open"], last_bar["high"], last_bar["low"]
        bar_range  = h - l or 1e-10
        body       = abs(c - o)
        upper_wick = h - max(c, o)
        lower_wick = min(c, o) - l
        bull_bar   = c > o
        bear_bar   = c < o
        vol        = last_bar["volume"]
        vol_above  = vol > avg_vol
        vol_spike  = vol > avg_vol * self.vol_spike_mult
        vol_dryup  = vol < avg_vol * self.vol_dryup_ratio

        tr_high = phase_result.tr_high
        tr_low  = phase_result.tr_low
        tr_mid  = (tr_high + tr_low) / 2

        result = SubPhaseResult()

        if phase_result.phase == Phase.ACCUMULATION:
            result = self._detect_accumulation_sub(
                c, o, h, l, prev_bar, bull_bar, bear_bar,
                vol, vol_above, vol_spike, vol_dryup,
                body, bar_range, upper_wick, lower_wick,
                tr_high, tr_low, tr_mid
            )

        elif phase_result.phase == Phase.DISTRIBUTION:
            result = self._detect_distribution_sub(
                c, o, h, l, prev_bar, bull_bar, bear_bar,
                vol, vol_above, vol_spike, vol_dryup,
                body, bar_range, upper_wick, lower_wick,
                tr_high, tr_low, tr_mid
            )

        elif phase_result.phase == Phase.MARKUP:
            result.subphase   = SubPhase.SOS
            result.signal     = 1 if bull_bar and vol_above else 0
            result.confidence = 70.0 if vol_above and bull_bar else 40.0
            result.notes      = ["Markup: trend-follow on SOS momentum"]

        elif phase_result.phase == Phase.MARKDOWN:
            result.subphase   = SubPhase.SOW
            result.signal     = -1 if bear_bar and vol_above else 0
            result.confidence = 70.0 if vol_above and bear_bar else 40.0
            result.notes      = ["Markdown: trend-follow on SOW momentum"]

        return result

    # ── Accumulation ──────────────────────────────────────────────
    def _detect_accumulation_sub(
        self, c, o, h, l, prev, bull, bear,
        vol, vol_above, vol_spike, vol_dryup,
        body, rng, upper_wick, lower_wick,
        tr_h, tr_l, tr_m
    ) -> SubPhaseResult:
        r = SubPhaseResult()

        # SC: wide bear bar, high vol, closes near lows but above extreme
        if bear and vol_spike and lower_wick < body * 0.5:
            r.subphase   = SubPhase.SC
            r.signal     = 1   # Potential long reversal
            r.confidence = 75.0
            r.notes      = ["SC: high-vol bear bar — selling climax"]

        # Spring: price sweeps below TR low then closes back inside
        elif l < tr_l and c > tr_l and bull:
            r.subphase   = SubPhase.SPR
            r.signal     = 1
            r.confidence = 85.0
            r.notes      = ["Spring: swept below TR low, bullish close"]

        # ST: low-vol retest of SC area, finds support
        elif not vol_above and c > tr_l and bull and c < tr_m:
            r.subphase   = SubPhase.ST
            r.signal     = 1
            r.confidence = 60.0
            r.notes      = ["ST: low-vol test finding support"]

        # SOS: strong bull bar, high vol, close near high
        elif bull and vol > vol * 1.5 and c > (h - rng * 0.25) and c > tr_m:
            r.subphase   = SubPhase.SOS
            r.signal     = 1
            r.confidence = 80.0
            r.notes      = ["SOS: wide bull bar on expanding volume"]

        # LPS: low-vol pullback above TR midpoint after SOS
        elif bull and vol_dryup and c > tr_m:
            r.subphase   = SubPhase.LPS
            r.signal     = 1
            r.confidence = 70.0
            r.notes      = ["LPS: low-vol pullback holding above mid — entry"]

        # AR: automatic rally after SC
        elif bull and vol_above and c > prev["close"]:
            r.subphase   = SubPhase.AR
            r.signal     = 0   # AR is informational, wait for ST
            r.confidence = 55.0
            r.notes      = ["AR: automatic rally — wait for secondary test"]

        # PS: first support below recent lows
        elif bear and vol_above and c < tr_l * 1.005:
            r.subphase   = SubPhase.PS
            r.signal     = 0
            r.confidence = 50.0
            r.notes      = ["PS: preliminary support — phase A beginning"]

        else:
            r.notes = ["Accumulation: no clear sub-phase event on this bar"]

        return r

    # ── Distribution ──────────────────────────────────────────────
    def _detect_distribution_sub(
        self, c, o, h, l, prev, bull, bear,
        vol, vol_above, vol_spike, vol_dryup,
        body, rng, upper_wick, lower_wick,
        tr_h, tr_l, tr_m
    ) -> SubPhaseResult:
        r = SubPhaseResult()

        # BC: wide bull bar, high vol, closes near highs with long upper wick
        if bull and vol_spike and upper_wick < body * 0.5:
            r.subphase   = SubPhase.BC
            r.signal     = -1
            r.confidence = 75.0
            r.notes      = ["BC: high-vol bull bar — buying climax"]

        # UT / UTAD: sweeps above TR high, closes back inside
        elif h > tr_h and c < tr_h and bear:
            r.subphase   = SubPhase.UT
            r.signal     = -1
            r.confidence = 85.0
            r.notes      = ["UT: upthrust swept above TR high, bearish close"]

        # SOW: strong bear bar on high vol, closes near lows
        elif bear and vol_above and c < (l + rng * 0.25) and c < tr_m:
            r.subphase   = SubPhase.SOW
            r.signal     = -1
            r.confidence = 80.0
            r.notes      = ["SOW: wide bear bar on expanding volume"]

        # LPSY: low-vol rally holding below TR midpoint after SOW
        elif bear and vol_dryup and c < tr_m:
            r.subphase   = SubPhase.LPSY
            r.signal     = -1
            r.confidence = 70.0
            r.notes      = ["LPSY: low-vol rally failing below mid — short entry"]

        elif bear and vol_above and c < prev["close"]:
            r.subphase   = SubPhase.AR_D
            r.signal     = 0
            r.confidence = 55.0
            r.notes      = ["AR-D: automatic reaction — wait for UT"]

        elif bull and vol_above and c > tr_h * 0.995:
            r.subphase   = SubPhase.PSY
            r.signal     = 0
            r.confidence = 50.0
            r.notes      = ["PSY: preliminary supply — phase A distribution"]

        else:
            r.notes = ["Distribution: no clear sub-phase event on this bar"]

        return r
