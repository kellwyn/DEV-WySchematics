@../Dev-RZY/AGENT.md
@../Dev-RZY/SKILLS.md

<!-- DEV-WySchematics — strategy-specific overrides -->

## Strategy

**Wyckoff Theory Schematics** — multi-symbol, multi-timeframe, phase-based.  
Identifies four phases (Accumulation, Markup, Distribution, Markdown) and their sub-events (SC, Spring, SOS, UT, SOW…), scores them with a probability confluence model, and executes at high-confidence setups.  
See `README.md` for full phase/sub-phase reference.

## Critical Rules

- MANUAL_CONFIRM=true — semi-automated; confluence score must exceed MIN_PROBABILITY (default 65%) before prompting
- Multi-symbol: `SYMBOLS` env var accepts comma-separated list — scan all before entering any
- HTF confirmation required — always check the higher timeframe phase aligns with the execution TF
- Volume is essential for Wyckoff — effort/result divergence signals absorption or exhaustion; do not skip volume analysis
- Spring and Upthrust are the highest-conviction entries — prioritise these over momentum entries

## Repo Structure

```
DEV-WySchematics/
├── WySchematicsEA/
│   ├── WySchematicsEA.mq5
│   └── CHANGELOG.md
├── signal-lab/
│   ├── main.py
│   └── lab/       phases, subphases, indicators, htf, confluence, dashboard
└── wyckoff-bot/
    ├── main.py
    └── bot/       connection, strategy, trader
```

Note: naming convention differs from other repos — `WySchematicsEA/` not `wyschema-mq5-ea/`.

## Key Differences from Standard Pattern

- Multi-symbol scanner — `SYMBOLS` and `TIMEFRAMES` are comma-separated env vars, not single values
- Probability scoring system in `signal-lab/lab/confluence.py` — weighted score across all Wyckoff criteria
- HTF confirmation module (`htf.py`) is a required check, not an optional filter
- `signal-lab/` and `wyckoff-bot/` share the same detection engine — `wyckoff-bot` calls signal-lab directly
- EA has per-phase and per-sub-phase trade toggles — test each independently

## Verification

| Change | Verify with |
|---|---|
| Phase detection | Check known Wyckoff chart examples (Wyckoff Mind Map.png in Dev/) |
| Confluence scoring | Confirm Spring + SOS scores ≥ 80%; LPSY after Distribution ≥ 65% |
| Multi-symbol scan | Run signal-lab with 3+ symbols; verify dashboard renders all |
| EA toggle | Enable one sub-phase at a time; confirm only that sub-phase fires |

## Subagents

| Task | Command |
|---|---|
| Review code | `use the code-reviewer subagent` |
| Security scan | `use the security-reviewer subagent` |
| Bot health | `use the bot-health-check subagent` |
| Deploy EA | `use the ea-deployer subagent` |
| Commit + push | `use the git-push subagent` |
