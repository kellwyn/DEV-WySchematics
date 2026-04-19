"""
Wyckoff Phase Detector
Identifies the current major market phase from OHLCV data.

Four phases (Richard Wyckoff):
  ACCUMULATION  — institutional absorption of supply at lows
  MARKUP        — price appreciation / trending up
  DISTRIBUTION  — institutional offloading of supply at highs
  MARKDOWN      — price depreciation / trending down
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np
import pandas as pd


class Phase(str, Enum):
    NONE         = "None"
    ACCUMULATION = "Accumulation"
    MARKUP       = "Markup"
    DISTRIBUTION = "Distribution"
    MARKDOWN     = "Markdown"


@dataclass
class PhaseResult:
    phase: Phase = Phase.NONE
    confidence: float = 0.0          # 0–100
    tr_high: float = 0.0             # Trading range high
    tr_low: float = 0.0              # Trading range low
    trend_slope: float = 0.0
    vol_ratio: float = 0.0           # Recent vol / avg vol
    notes: list[str] = field(default_factory=list)


class PhaseDetector:
    """
    Determines the current Wyckoff phase from a price DataFrame.

    Required DataFrame columns: open, high, low, close, volume (or tick_volume)
    Index: datetime

    Usage:
        detector = PhaseDetector(lookback=100, vol_lookback=20)
        result   = detector.detect(df)
        print(result.phase, result.confidence)
    """

    def __init__(
        self,
        lookback: int = 100,
        vol_lookback: int = 20,
        trend_bars: int = 20,
        vol_spike_mult: float = 2.0,
        vol_dryup_ratio: float = 0.5,
    ):
        self.lookback       = lookback
        self.vol_lookback   = vol_lookback
        self.trend_bars     = trend_bars
        self.vol_spike_mult = vol_spike_mult
        self.vol_dryup_ratio = vol_dryup_ratio

    # ──────────────────────────────────────────────────────────────
    def detect(self, df: pd.DataFrame) -> PhaseResult:
        df = df.tail(self.lookback).copy()
        if len(df) < self.trend_bars + 5:
            return PhaseResult(notes=["Insufficient data"])

        df = self._normalise_columns(df)
        result = PhaseResult()

        # ── Trading Range ──
        tr_high, tr_low = self._trading_range(df)
        result.tr_high = tr_high
        result.tr_low  = tr_low
        range_size     = tr_high - tr_low or 1e-10

        # ── Trend slope ──
        slope = self._trend_slope(df)
        result.trend_slope = slope

        # ── Volume ratios ──
        avg_vol = df["volume"].tail(self.vol_lookback).mean()
        last_vol = df["volume"].iloc[-1]
        result.vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0

        recent_close = df["close"].iloc[-1]
        range_pos    = (recent_close - tr_low) / range_size  # 0=bottom, 1=top

        # ── Score each phase (0–1 per criterion) ──
        scores = self._score_phases(df, slope, range_pos, result.vol_ratio, avg_vol)

        best_phase = max(scores, key=scores.get)
        raw_score  = scores[best_phase]

        result.phase      = Phase(best_phase)
        result.confidence = round(raw_score * 100, 1)
        result.notes      = self._build_notes(scores, range_pos, slope, result.vol_ratio)
        return result

    # ──────────────────────────────────────────────────────────────
    def _normalise_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "tick_volume" in df.columns and "volume" not in df.columns:
            df["volume"] = df["tick_volume"]
        df["volume"] = df["volume"].replace(0, np.nan).fillna(method="ffill").fillna(1)
        return df

    def _trading_range(self, df: pd.DataFrame):
        tr_high = df["high"].max()
        tr_low  = df["low"].min()
        return tr_high, tr_low

    def _trend_slope(self, df: pd.DataFrame) -> float:
        closes = df["close"].tail(self.trend_bars).values
        x      = np.arange(len(closes))
        if len(x) < 2:
            return 0.0
        slope  = np.polyfit(x, closes, 1)[0]
        # Normalise by average price so it's scale-agnostic
        return slope / (closes.mean() or 1)

    def _score_phases(
        self,
        df: pd.DataFrame,
        slope: float,
        range_pos: float,
        vol_ratio: float,
        avg_vol: float,
    ) -> dict[str, float]:
        """
        Returns a score 0–1 for each phase using weighted criteria.
        """
        scores: dict[str, float] = {p.value: 0.0 for p in Phase if p != Phase.NONE}

        # ── ACCUMULATION ──────────────────────────────────────────
        acc = 0.0
        # Price in lower half of range
        acc += max(0.0, (0.5 - range_pos) * 2) * 0.30
        # Slope flat-to-negative (bottoming)
        acc += max(0.0, -slope * 200) * 0.20 if slope < 0 else 0
        acc += 0.15 if abs(slope) < 0.001 else 0
        # Volume drying up (absorption complete)
        acc += 0.20 if vol_ratio < self.vol_dryup_ratio else 0
        # Recent higher lows
        acc += 0.15 if self._has_higher_lows(df) else 0
        scores[Phase.ACCUMULATION.value] = min(1.0, acc)

        # ── MARKUP ────────────────────────────────────────────────
        mup = 0.0
        mup += max(0.0, slope * 200) * 0.35 if slope > 0 else 0
        mup += (range_pos - 0.5) * 0.30 if range_pos > 0.5 else 0
        mup += 0.20 if vol_ratio > 1.2 else 0
        mup += 0.15 if self._has_higher_highs_and_lows(df) else 0
        scores[Phase.MARKUP.value] = min(1.0, mup)

        # ── DISTRIBUTION ──────────────────────────────────────────
        dis = 0.0
        dis += max(0.0, (range_pos - 0.5) * 2) * 0.30
        dis += max(0.0, -slope * 200) * 0.20 if slope < 0 else 0
        dis += 0.15 if abs(slope) < 0.001 else 0
        dis += 0.20 if vol_ratio < self.vol_dryup_ratio else 0
        dis += 0.15 if self._has_lower_highs(df) else 0
        scores[Phase.DISTRIBUTION.value] = min(1.0, dis)

        # ── MARKDOWN ──────────────────────────────────────────────
        mdn = 0.0
        mdn += max(0.0, -slope * 200) * 0.35 if slope < 0 else 0
        mdn += max(0.0, (0.5 - range_pos) * 0.30) if range_pos < 0.5 else 0
        mdn += 0.20 if vol_ratio > 1.2 else 0
        mdn += 0.15 if self._has_lower_highs_and_lows(df) else 0
        scores[Phase.MARKDOWN.value] = min(1.0, mdn)

        return scores

    # ── Structure helpers ──────────────────────────────────────────
    def _has_higher_lows(self, df: pd.DataFrame, n: int = 3) -> bool:
        lows = df["low"].tail(n * 5).rolling(5).min().dropna().values[-n:]
        return all(lows[i] < lows[i + 1] for i in range(len(lows) - 1))

    def _has_lower_highs(self, df: pd.DataFrame, n: int = 3) -> bool:
        highs = df["high"].tail(n * 5).rolling(5).max().dropna().values[-n:]
        return all(highs[i] > highs[i + 1] for i in range(len(highs) - 1))

    def _has_higher_highs_and_lows(self, df: pd.DataFrame, n: int = 3) -> bool:
        return self._has_higher_lows(df, n) and not self._has_lower_highs(df, n)

    def _has_lower_highs_and_lows(self, df: pd.DataFrame, n: int = 3) -> bool:
        return self._has_lower_highs(df, n) and not self._has_higher_lows(df, n)

    def _build_notes(
        self,
        scores: dict[str, float],
        range_pos: float,
        slope: float,
        vol_ratio: float,
    ) -> list[str]:
        notes = []
        notes.append(f"Range position: {range_pos:.1%} (0=bottom, 1=top)")
        notes.append(f"Trend slope: {'▲' if slope > 0.0005 else '▼' if slope < -0.0005 else '→'} ({slope:.5f})")
        notes.append(f"Volume ratio vs avg: {vol_ratio:.2f}x")
        for phase, score in sorted(scores.items(), key=lambda x: -x[1]):
            notes.append(f"  {phase:<14} score: {score:.2f}")
        return notes
