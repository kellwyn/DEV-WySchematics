"""
Signal Lab Dashboard
Renders a formatted terminal output of the current Wyckoff analysis.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from .phases import Phase, PhaseResult
from .subphases import SubPhase, SubPhaseResult
from .indicators import IndicatorSnapshot
from .htf import HTFResult
from .confluence import ConfluenceResult

PHASE_COLOUR = {
    Phase.ACCUMULATION: "\033[92m",   # green
    Phase.MARKUP:       "\033[96m",   # cyan
    Phase.DISTRIBUTION: "\033[93m",   # yellow
    Phase.MARKDOWN:     "\033[91m",   # red
    Phase.NONE:         "\033[0m",
}
RESET = "\033[0m"
BOLD  = "\033[1m"


class Dashboard:
    def __init__(self, symbol: str, timeframe: str, htf: str):
        self.symbol    = symbol
        self.timeframe = timeframe
        self.htf       = htf

    def render(
        self,
        phase_result:    PhaseResult,
        subphase_result: SubPhaseResult,
        indicator_snap:  IndicatorSnapshot,
        htf_result:      HTFResult,
        confluence:      ConfluenceResult,
        timestamp:       datetime | None = None,
    ) -> str:
        ts  = (timestamp or datetime.utcnow()).strftime("%Y-%m-%d %H:%M UTC")
        col = PHASE_COLOUR.get(phase_result.phase, RESET)
        sig = {1: "▲ LONG", -1: "▼ SHORT", 0: "— WAIT"}.get(confluence.signal, "— WAIT")

        lines = [
            "",
            f"{BOLD}{'─'*60}{RESET}",
            f"{BOLD}  WYCKOFF SIGNAL LAB  {ts}{RESET}",
            f"{'─'*60}",
            f"  Symbol    : {BOLD}{self.symbol}{RESET}",
            f"  Timeframe : {self.timeframe}  |  HTF: {self.htf}",
            f"{'─'*60}",
            f"  {BOLD}Phase{RESET}     : {col}{BOLD}{phase_result.phase.value}{RESET}"
            f"  (confidence: {phase_result.confidence:.1f}%)",
            f"  {BOLD}Sub-Phase{RESET} : {subphase_result.subphase.value}"
            f"  (confidence: {subphase_result.confidence:.1f}%)",
            f"  TR Range  : {phase_result.tr_low:.5f} – {phase_result.tr_high:.5f}",
            f"{'─'*60}",
            f"  {BOLD}SIGNAL{RESET}    : {BOLD}{sig}{RESET}",
            f"  Probability: {BOLD}{confluence.probability:.1f}%{RESET}"
            f"  Grade: {BOLD}{confluence.grade}{RESET}",
            f"{'─'*60}",
            f"  {BOLD}Indicators{RESET}",
            f"    ATR           : {indicator_snap.atr:.5f}",
            f"    Volume ratio  : {indicator_snap.vol_ratio:.2f}x avg",
            f"    Volume trend  : {indicator_snap.vol_trend}",
            f"    Bar spread    : {indicator_snap.spread_quality}",
            f"    Close position: {indicator_snap.close_position:.0%} (0=low, 1=high)",
            f"    Effort/Result : {indicator_snap.effort_vs_result}",
            f"    P&F cause     : {indicator_snap.pf_cause:.5f}",
            f"{'─'*60}",
            f"  {BOLD}HTF ({self.htf}){RESET} : {htf_result.htf_phase.value}"
            f" / {htf_result.htf_bias}"
            f" | Aligned: {'✓' if htf_result.aligned else '✗'}",
            f"{'─'*60}",
            f"  {BOLD}Confluences{RESET}",
        ]
        for c in confluence.confluences:
            lines.append(f"    ✓ {c}")
        if confluence.warnings:
            lines.append(f"  {BOLD}Warnings{RESET}")
            for w in confluence.warnings:
                lines.append(f"    ⚠ {w}")
        lines.append(f"{'─'*60}")
        lines.append("")
        return "\n".join(lines)
