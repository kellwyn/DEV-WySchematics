"""
Technical Indicators for Wyckoff analysis.

Key analysis tools per the Wyckoff methodology:
  • Volume Analysis     — volume climax, dry-up, spread/volume divergence
  • Market Structure    — higher highs/lows, lower highs/lows, swing pivots
  • Point & Figure      — cause-and-effect count (simplified)
  • Bar Chart Analysis  — bar spread, close position, effort vs result
  • ATR                 — volatility for SL/TP sizing
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class IndicatorSnapshot:
    atr: float                = 0.0
    vol_ratio: float          = 1.0     # last vol / avg vol
    vol_trend: str            = "flat"  # rising / falling / flat
    spread_quality: str       = "normal"# wide / narrow / normal
    close_position: float     = 0.5    # 0=low of bar, 1=high of bar
    effort_vs_result: str     = "neutral"  # strong / weak / neutral
    swing_highs: list[float]  = field(default_factory=list)
    swing_lows: list[float]   = field(default_factory=list)
    pf_cause: float           = 0.0    # simplified P&F count
    notes: list[str]          = field(default_factory=list)


class Indicators:
    def __init__(
        self,
        atr_period: int = 14,
        vol_lookback: int = 20,
        swing_lookback: int = 5,
        vol_spike_mult: float = 2.0,
    ):
        self.atr_period    = atr_period
        self.vol_lookback  = vol_lookback
        self.swing_lookback = swing_lookback
        self.vol_spike_mult = vol_spike_mult

    def compute(self, df: pd.DataFrame) -> IndicatorSnapshot:
        df = df.copy()
        if "tick_volume" in df.columns and "volume" not in df.columns:
            df["volume"] = df["tick_volume"]
        df["volume"] = df["volume"].replace(0, np.nan).fillna(method="ffill").fillna(1)

        snap = IndicatorSnapshot()

        snap.atr           = self._atr(df)
        snap.vol_ratio     = self._vol_ratio(df)
        snap.vol_trend     = self._vol_trend(df)
        snap.spread_quality = self._spread_quality(df)
        snap.close_position = self._close_position(df)
        snap.effort_vs_result = self._effort_vs_result(df)
        snap.swing_highs   = self._swing_highs(df)
        snap.swing_lows    = self._swing_lows(df)
        snap.pf_cause      = self._pf_cause(df)
        snap.notes         = self._notes(snap)
        return snap

    # ── ATR ───────────────────────────────────────────────────────
    def _atr(self, df: pd.DataFrame) -> float:
        h, l, pc = df["high"], df["low"], df["close"].shift(1)
        tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
        return tr.tail(self.atr_period).mean()

    # ── Volume ────────────────────────────────────────────────────
    def _vol_ratio(self, df: pd.DataFrame) -> float:
        avg = df["volume"].tail(self.vol_lookback).mean()
        return df["volume"].iloc[-1] / avg if avg > 0 else 1.0

    def _vol_trend(self, df: pd.DataFrame) -> str:
        recent = df["volume"].tail(self.vol_lookback).values
        if len(recent) < 4:
            return "flat"
        slope = np.polyfit(range(len(recent)), recent, 1)[0]
        if slope > recent.mean() * 0.02:
            return "rising"
        if slope < -recent.mean() * 0.02:
            return "falling"
        return "flat"

    # ── Bar spread ────────────────────────────────────────────────
    def _spread_quality(self, df: pd.DataFrame) -> str:
        spreads = (df["high"] - df["low"]).tail(self.vol_lookback)
        avg_spread = spreads.mean()
        last_spread = spreads.iloc[-1]
        ratio = last_spread / avg_spread if avg_spread > 0 else 1.0
        if ratio > 1.5:
            return "wide"
        if ratio < 0.5:
            return "narrow"
        return "normal"

    def _close_position(self, df: pd.DataFrame) -> float:
        bar = df.iloc[-1]
        rng = bar["high"] - bar["low"]
        if rng == 0:
            return 0.5
        return (bar["close"] - bar["low"]) / rng

    # ── Effort vs Result ──────────────────────────────────────────
    def _effort_vs_result(self, df: pd.DataFrame) -> str:
        """High volume + small bar = absorption (weak result for effort)."""
        vol_ratio  = self._vol_ratio(df)
        spread_qual = self._spread_quality(df)
        if vol_ratio > self.vol_spike_mult and spread_qual == "narrow":
            return "absorption"   # Effort without result → reversal signal
        if vol_ratio > 1.5 and spread_qual == "wide":
            return "strong"       # Big move on big volume
        if vol_ratio < 0.7 and spread_qual == "wide":
            return "weak"         # Big move on low vol — unsustainable
        return "neutral"

    # ── Swing structure ───────────────────────────────────────────
    def _swing_highs(self, df: pd.DataFrame) -> list[float]:
        highs = df["high"].values
        pivots = []
        n = self.swing_lookback
        for i in range(n, len(highs) - n):
            if highs[i] == max(highs[i - n: i + n + 1]):
                pivots.append(float(highs[i]))
        return pivots[-5:]

    def _swing_lows(self, df: pd.DataFrame) -> list[float]:
        lows = df["low"].values
        pivots = []
        n = self.swing_lookback
        for i in range(n, len(lows) - n):
            if lows[i] == min(lows[i - n: i + n + 1]):
                pivots.append(float(lows[i]))
        return pivots[-5:]

    # ── Point & Figure simplified cause count ────────────────────
    def _pf_cause(self, df: pd.DataFrame) -> float:
        """
        Simplified P&F cause: counts sideways bars within the TR.
        Each bar within the trading range represents 'cause' being built.
        Multiply by ATR to get an approximate 'effect' target.
        """
        atr   = self._atr(df)
        tr_h  = df["high"].tail(self.vol_lookback).max()
        tr_l  = df["low"].tail(self.vol_lookback).min()
        rng   = tr_h - tr_l

        count = 0
        for _, row in df.tail(self.vol_lookback).iterrows():
            if tr_l <= row["close"] <= tr_h:
                count += 1
        return count * atr if atr > 0 else 0.0

    def _notes(self, snap: IndicatorSnapshot) -> list[str]:
        notes = []
        if snap.effort_vs_result == "absorption":
            notes.append("Absorption: high vol, narrow spread — potential reversal zone")
        if snap.effort_vs_result == "weak":
            notes.append("Weak move: wide bar, low volume — unsustainable push")
        if snap.vol_ratio > self.vol_spike_mult:
            notes.append(f"Volume spike: {snap.vol_ratio:.1f}x avg — climax possible")
        if snap.vol_ratio < 0.5:
            notes.append("Volume dry-up — institutional interest waning")
        if snap.close_position > 0.75:
            notes.append("Strong close: near bar high — bulls in control")
        if snap.close_position < 0.25:
            notes.append("Weak close: near bar low — bears in control")
        if snap.pf_cause > 0:
            notes.append(f"P&F cause count ≈ {snap.pf_cause:.4f} — projected effect range")
        return notes
