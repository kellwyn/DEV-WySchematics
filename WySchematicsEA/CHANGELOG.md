# WySchematicsEA — Changelog

## v1.0.0 — 2026-04-20
**Initial Release**

### Strategy
- Wyckoff four-phase cycle: Accumulation → Markup → Distribution → Markdown
- Sub-phase detection for Accumulation: PS, SC, AR, ST, Spring, SOS, LPS
- Sub-phase detection for Distribution: PSY, BC, AR, UT/UTAD, SOW, LPSY
- Volume climax and dry-up analysis for phase confirmation

### Execution
- Scalp entries on sub-phase event bars (configurable per sub-phase via toggles)
- ATR-based or fixed-pip SL/TP sizing
- Risk-to-reward ratio enforcement (toggleable)
- Account-balance-based position sizing with hard max lot cap
- Higher timeframe trend confirmation filter (toggleable)
- Spread filter to avoid wide-spread conditions

### Parameters
- Per-phase and per-sub-phase trading toggles
- Configurable analysis and higher timeframe
- Max concurrent trades cap
- Magic number for multi-EA separation
