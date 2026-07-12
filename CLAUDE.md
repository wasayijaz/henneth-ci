# PSX Trade Desk — Desk Rules

Every agent and every cycle in this repo obeys these rules. They are not suggestions.

## Identity
Personal trading intelligence desk for the Pakistan Stock Exchange (PSX). It researches,
scores, and monitors signals. It NEVER places orders. Execution is manual by the owner.

## Hard rules
1. **Long only.** No shorts, no leverage, no derivatives.
2. **All prices come from the data layer** (`state/` JSON files produced by `scripts/`).
   No agent may quote a price, date, or dividend from its own memory. If the data layer
   doesn't have it, the answer is "unknown", not a guess.
3. **Daily timeframe only.** 30-minute cycles are monitoring frequency, not day trading.
   No intraday scalping setups, ever.
4. **Risk limits** (enforced by Risk Officer, checked by Auditor):
   - Max 4 concurrent positions
   - Max 8% of capital per trade
   - Max 20% total exposure
   - No two positions in the same sector
   - Circuit breaker: 2 stop-outs within 5 sessions → signal-only mode for 3 sessions
5. **No advice language.** Output is research ("the setup", "the desk's read"), never
   "you should buy". No performance promises. Losses are expected and documented.
6. **Data health gates everything.** If `state/health.json` says `status != "ok"`,
   no new signals are generated that cycle. Monitoring of existing positions continues.
7. **Auditor has veto.** Any mismatch between Auditor's independent re-derivation and
   the Strategist's numbers kills the setup. No overrides.

## Market context
- PSX hours (verified 2026-07): Mon–Thu 09:32–15:30 PKT; Fri two sessions 09:17–12:00 and
  14:32–16:30 PKT (Jumma break between). Ramadan timings differ — update when SBP/PSX announce.
- Trading calendar: `state/calendar.json`. If today is listed as a holiday, cycles exit quietly.
- All timestamps in state files are PKT unless suffixed `_utc`.
- **TradingView PSX data is ~15 min delayed.** TV (tradingview-ta, MCP) is for EOD cross-checks
  and global context ONLY. Intraday decisions use DPS (`state/live.json`) exclusively.
  Never compare TV live price to DPS live price and call the mismatch an error.

## Layout
- `scripts/` — deterministic Python. Data fetch, indicators, predictability, backtests, health.
- `.claude/agents/` — judgment agents (news, macro, strategist, risk, auditor, monitor, reviewer).
- `prompts/` — orchestrator prompts run via `claude -p`.
- `strategies/` — strategy templates (JSON rule files). Setups MUST reference one.
- `state/` — all desk state. JSON only. This is the single source of truth.
- `dashboard/` — local visual layer. Reads `state/`, writes nothing.
- `logs/` — one transcript per cycle run.
- `config/desk.json` — capital, risk params, alert config.

## Cycle discipline
- Pre-market run (~08:45 PKT): full pipeline (data refresh → quant → predictability →
  backtests → news → macro → strategist → risk → auditor → report).
- Intraday runs (every 30 min): light pipeline (snapshot → news sentinel → monitor → report).
  Full pipeline re-triggers only if Sentinel flags impact ≥ 4 news.
- Every run appends one line to `state/runlog.json` (started, mode, ended, outcome).

## Python
- Python 3.14, deps: requests, pandas, numpy (already installed).
- Scripts must be idempotent and safe to re-run. Network failures → write degraded
  health status, exit 0. Never crash the cycle.
