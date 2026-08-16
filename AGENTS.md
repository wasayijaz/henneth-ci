# Henneth — Agent Entry Point

Harness-neutral brief. Codex, Claude Code, and any other agent working in this repo start here.

Henneth is a personal trading-intelligence desk for the Pakistan Stock Exchange. It researches,
scores, and monitors signals. **It never places orders.** Execution is manual by the owner.

## Read in this order

| File | What it governs |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | **Governance.** The hard rules — risk limits, position sizing, veto authority, data provenance. Binding on every agent and every cycle. |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | **Operations.** The hybrid cloud/app model, the one publish path, safety gates, how to run each flow without breaking the live site. |
| [`docs/GOTCHAS.md`](docs/GOTCHAS.md) | **Sharp edges.** Traps that already cost debugging time — the auth gate, the CSS at-rule trap, encoding, frozen breakpoints. |

`CLAUDE.md` is auto-loaded by Claude Code but **not** by other harnesses. If you are not Claude Code,
read it explicitly before doing anything that touches signals, sizing, or published output.

## Non-negotiables (full text in `CLAUDE.md`)

1. **Long only.** No shorts, no leverage, no derivatives. Daily timeframe only.
2. **All prices, dates and dividends come from the data layer** (`state/` JSON produced by
   `scripts/`). Never quote one from model memory. Missing data is answered "unknown", never guessed.
3. **No advice language.** Output is research — "the setup", "the desk's read" — never "you should
   buy". No performance promises.
4. **Risk limits:** max 4 concurrent positions · max 20% total exposure · no two positions in the
   same sector. One sizing formula only:
   `shares = floor(min(risk_budget / (entry − stop), (capital × 8%) / entry))`, where
   `risk_budget = capital × risk_per_trade_pct` (default 1%). `entry ≤ stop` or `shares = 0` is invalid.
5. **Data health gates everything.** `state/health.json` `status != "ok"` → no new signals this cycle.
6. **The Auditor has veto.** Any mismatch against its independent re-derivation kills the setup.
7. **Live strategy files are immutable.** Add a new versioned file; never edit one in place.
8. **No lookahead in backtests.** A signal at bar *t* may use only data available at *t*'s close.
9. **`config/desk.json` must never be served.** It holds the owner's real trading capital and the
   Telegram bot token.

## Layout

```
scripts/         deterministic Python — fetch, indicators, quant, predictability, backtests,
                 health, publish, preflight, Desk Room + astro + sector pipelines
.claude/agents/  judgment agents (strategist, risk-officer, auditor, monitor, reviewer,
                 news-sentinel, macro-agent, market-analyst, room-* debate cast, sector-*)
prompts/         orchestrator prompts run via `claude -p`
strategies/      JSON rule templates; every setup must reference one
state/           all desk state, JSON only — the single source of truth
dashboard/       static visual layer; reads state/, writes nothing
site/ public/    marketing site; api/ask.js is the Groq-backed "ask the desk" endpoint
config/          desk.json — capital, risk params, alerts. Never served.
docs/            runbook and plans
logs/            one transcript per cycle run
```

## Engineering conventions

- Python 3.14; deps `requests`, `pandas`, `numpy`. Scripts must be idempotent and safe to re-run.
  A network failure writes a degraded health status and **exits 0** — never crash the cycle.
- No backward-compatibility layers. Remove obsolete paths rather than adding fallbacks or migrations.
- Simplest implementation that fully meets the current requirement. No speculative abstraction.
- Grow in layers: never trade a working product for unfinished complexity.
- Prefer existing dependencies over new ones or hand-rolled equivalents.

## Publishing

```bash
python scripts/publish.py "message"          # data only
python scripts/publish.py "message" --code   # plus pre-staged hand-authored files
```

Race-safe and preflight-gated. `--code` ships only what is already staged; it never runs `git add -A`.
Files under `state/` are committed automatically. Full detail in `docs/OPERATIONS.md`; the failure
modes are in `docs/GOTCHAS.md`.
