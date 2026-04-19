"""
Confluence Engine
Combines scores from:
  1. Phase detection (probability from current phase context)
  2. Sub-phase event quality
  3. Technical indicators (volume, spread, effort/result)
  4. Higher timeframe confirmation
  5. Phase sequence validation (prior completed phases increase confidence)

Output: overall probability score 0–100, trade recommendation, key confluences.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd

from .phases import Phase, PhaseResult
from .subphases import SubPhase, SubPhaseResult
from .indicators import IndicatorSnapshot
from .htf import HTFResult


PHASE_SEQUENCE_BULLISH = [Phase.ACCUMULATION, Phase.MARKUP]
PHASE_SEQUENCE_BEARISH = [Phase.DISTRIBUTION, Phase.MARKDOWN]

# Weight table per confluence factor
WEIGHTS = {
    "phase_score":    0.25,
    "subphase_score": 0.25,
    "indicator":      0.20,
    "htf":            0.20,
    "sequence":       0.10,
}


@dataclass
class ConfluenceResult:
    probability: float       = 0.0   # 0–100
    signal: int              = 0     # 1=long, -1=short, 0=none
    grade: str               = "—"   # A/B/C/D/F
    confluences: list[str]   = field(default_factory=list)
    warnings: list[str]      = field(default_factory=list)


class ConfluenceEngine:
    """
    Fuses all analysis layers into a single probability score.

    Usage:
        engine = ConfluenceEngine()
        result = engine.score(
            phase_result, subphase_result, indicator_snap, htf_result,
            phase_history=["Accumulation"]  # list of previously identified phases
        )
    """

    def score(
        self,
        phase_result:    PhaseResult,
        subphase_result: SubPhaseResult,
        indicator_snap:  IndicatorSnapshot,
        htf_result:      HTFResult,
        phase_history:   list[str] | None = None,
    ) -> ConfluenceResult:
        phase_history = phase_history or []
        out = ConfluenceResult()

        # ── 1. Phase score ────────────────────────────────────────
        phase_score = phase_result.confidence / 100.0
        if phase_result.phase != Phase.NONE:
            out.confluences.append(
                f"Phase {phase_result.phase.value} ({phase_result.confidence:.0f}%)"
            )

        # ── 2. Sub-phase score ────────────────────────────────────
        sub_score = subphase_result.confidence / 100.0
        if subphase_result.subphase != SubPhase.NONE:
            out.confluences.append(
                f"Sub-phase {subphase_result.subphase.value} ({subphase_result.confidence:.0f}%)"
            )
        signal = subphase_result.signal

        # ── 3. Indicator score ────────────────────────────────────
        ind_score = self._indicator_score(indicator_snap, signal, out)

        # ── 4. HTF alignment ──────────────────────────────────────
        htf_score = htf_result.confidence / 100.0 if htf_result.aligned else 0.2
        if htf_result.aligned:
            out.confluences.append(
                f"HTF confirms: {htf_result.htf_phase.value} / {htf_result.htf_bias}"
            )
        else:
            out.warnings.append("HTF does not confirm — reduce position or skip")

        # ── 5. Phase sequence score ───────────────────────────────
        seq_score = self._sequence_score(
            phase_result.phase, phase_history, signal, out
        )

        # ── Weighted total ────────────────────────────────────────
        total = (
            WEIGHTS["phase_score"]    * phase_score +
            WEIGHTS["subphase_score"] * sub_score   +
            WEIGHTS["indicator"]      * ind_score   +
            WEIGHTS["htf"]            * htf_score   +
            WEIGHTS["sequence"]       * seq_score
        )

        out.probability = round(min(100.0, total * 100), 1)
        out.signal      = signal
        out.grade       = self._grade(out.probability)

        # Absorption warning
        if indicator_snap.effort_vs_result == "absorption" and signal != 0:
            out.warnings.append("Absorption bar detected — confirm next bar before entry")

        return out

    # ── Indicator scoring ─────────────────────────────────────────
    def _indicator_score(
        self,
        snap: IndicatorSnapshot,
        signal: int,
        out: ConfluenceResult,
    ) -> float:
        score = 0.5  # neutral base

        if snap.effort_vs_result == "strong":
            score += 0.25
            out.confluences.append("Strong effort-vs-result")
        elif snap.effort_vs_result == "absorption":
            score += 0.15  # absorption is bullish/bearish reversal context
            out.confluences.append("Absorption: institutional activity")
        elif snap.effort_vs_result == "weak":
            score -= 0.10
            out.warnings.append("Weak effort-vs-result — unsustainable move")

        if snap.vol_ratio > 2.0:
            score += 0.15
            out.confluences.append(f"Volume spike {snap.vol_ratio:.1f}x")
        elif snap.vol_ratio < 0.5:
            score += 0.10  # dry-up can be bullish (no selling) in accumulation
            out.confluences.append("Volume dry-up (low supply/demand)")

        if signal == 1 and snap.close_position > 0.7:
            score += 0.10
            out.confluences.append("Bullish close: strong close position")
        elif signal == -1 and snap.close_position < 0.3:
            score += 0.10
            out.confluences.append("Bearish close: weak close position")

        return max(0.0, min(1.0, score))

    # ── Phase sequence ────────────────────────────────────────────
    def _sequence_score(
        self,
        current_phase: Phase,
        history: list[str],
        signal: int,
        out: ConfluenceResult,
    ) -> float:
        if not history:
            return 0.5

        if current_phase == Phase.MARKUP:
            if Phase.ACCUMULATION.value in history:
                out.confluences.append("Prior Accumulation confirmed Markup")
                return 0.9
        elif current_phase == Phase.MARKDOWN:
            if Phase.DISTRIBUTION.value in history:
                out.confluences.append("Prior Distribution confirmed Markdown")
                return 0.9
        elif current_phase == Phase.ACCUMULATION:
            if Phase.MARKDOWN.value in history:
                out.confluences.append("Prior Markdown — Accumulation well-placed")
                return 0.8
        elif current_phase == Phase.DISTRIBUTION:
            if Phase.MARKUP.value in history:
                out.confluences.append("Prior Markup — Distribution well-placed")
                return 0.8
        return 0.5

    def _grade(self, prob: float) -> str:
        if prob >= 80: return "A"
        if prob >= 65: return "B"
        if prob >= 50: return "C"
        if prob >= 35: return "D"
        return "F"
