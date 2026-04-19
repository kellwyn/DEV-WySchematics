"""
Strategy scanner — iterates symbols/timeframes and collects Wyckoff setups.
"""
from __future__ import annotations
from .signals import Setup, scan


def scan_all(
    symbols: list[str],
    timeframes: list[str],
    htf: str,
    lookback: int,
    min_probability: float,
) -> list[Setup]:
    setups = []
    for symbol in symbols:
        for tf in timeframes:
            setup = scan(symbol, tf, htf, lookback, min_probability)
            if setup:
                setups.append(setup)
    return setups


def print_dashboard(setups: list[Setup], symbols: list[str], timeframes: list[str]) -> None:
    print(f"\n  {'─'*56}")
    print(f"  {'WYCKOFF BOT — SCAN RESULTS':^56}")
    print(f"  {'─'*56}")
    if not setups:
        print("  No qualifying setups found.\n")
        return
    for s in setups:
        print(
            f"  {s.symbol:<10} {s.timeframe:<5}"
            f"  {s.direction:<5}  Phase: {s.phase:<14}"
            f"  Sub: {s.subphase:<8}  Prob: {s.probability:.1f}%"
        )
    print(f"  {'─'*56}\n")
