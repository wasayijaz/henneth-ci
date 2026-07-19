# Henneth AI — Desk Rules

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
   - Max 4 concurrent positions · Max 20% total exposure · No two positions in the same sector.
   - **Position sizing — the ONLY formula. Strategist and Auditor both compute it this way, so a
     mismatch is a data/error bug, never a disagreement:**
     `risk_budget = capital × risk_per_trade_pct` (config, default **1%**).
     `risk_per_share = entry − stop`.
     `shares = floor( min( risk_budget / risk_per_share , (capital × 8%) / entry ) )`.
     That is: size by stop distance, then hard-cap position VALUE at **8% of capital**. A setup
     with `entry ≤ stop` or `shares = 0` is invalid. (The 8% cap in Rule 4 is a position-value
     cap, not the sizing method.)
   - **Circuit breaker + re-entry:** 2 stop-outs within 5 sessions → signal-only mode. Resume ONLY
     when BOTH hold: (a) ≥ 3 sessions have passed, AND (b) the macro regime score has recovered to
     ≥ its level before the stop-outs, OR the Reviewer explicitly signs off in `learnings.json`.
     Time alone never auto-resumes into the same regime that caused the stops.
   - **Stale-position time-stop:** a pending setup that has not triggered entry within **10
     sessions** is void — re-derive fresh or drop it. An open position flat (within ±3%) after
     **20 sessions** is closed as `THESIS_STALLED` (capital redeployed). Monitor emits `TIME_STOP`.
5. **No advice language.** Output is research ("the setup", "the desk's read"), never
   "you should buy". No performance promises. Losses are expected and documented.
6. **Data health gates everything.** If `state/health.json` says `status != "ok"`,
   no new signals are generated that cycle. Monitoring of existing positions continues.
7. **Auditor has veto.** Any mismatch between Auditor's independent re-derivation and
   the Strategist's numbers kills the setup. No overrides.
8. **Strategy files are immutable once live.** A file in `strategies/` that has produced a
   published backtest is FROZEN. To change a rule, add a NEW versioned file
   (`golden_cross_v2.json`) whose backtest starts fresh — never edit a live strategy in place, or
   old backtests silently become invalid. The `strategy_id`/`version` carries the version; the
   Auditor may veto a setup referencing a strategy whose file changed after its backtest.
9. **No lookahead in backtests.** A signal at bar *t* may use ONLY data available at *t*'s close
   (indicators over closes ≤ *t*; no future bar; no same-bar high/low the signal couldn't have
   known at entry). Fills use the next bar's open or *t*'s close per the strategy, never a price
   from *t*+n. The Auditor may veto any setup whose backtest cannot demonstrate this.
10. **News impact scale (1–5)** — the escalation trigger depends on it, so it is fixed here, not
    left to Sentinel's discretion: **1** routine/administrative · **2** minor company item ·
    **3** notable (results date, mgmt change, sector news) · **4** material (earnings surprise,
    regulatory action, major contract, index reconstitution, sharp commodity/FX move) · **5**
    severe (default, trading halt, fraud, war, macro shock). The full pipeline re-triggers on any
    tagged item **≥ 4**. Sentinel MUST apply these criteria; drift here silently changes full-cycle
    frequency.

## Market context
- PSX hours (verified 2026-07): Mon–Thu 09:32–15:30 PKT; Fri two sessions 09:17–12:00 and
  14:32–16:30 PKT (Jumma break between). Ramadan timings differ.
- **Calendar freshness (the Ramadan guard — "update when announced" is not a plan):**
  `calendar.json` carries a `session_times_updated` date. `data_health.py` checks it every cycle;
  if it is older than **60 days**, health degrades to `stale_calendar` (a real degraded status,
  not "ok"), which by Rule 6 halts new signals until a human re-verifies the session times against
  the latest SBP/PSX notice. The desk fails loud, never trades silently on wrong hours.
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
- `docs/OPERATIONS.md` — **operations runbook**: hybrid cloud/app model, the one publish path
  (`scripts/publish.py`, race-safe + preflight-gated), safety gates, and how to run every flow without
  breaking the live site. Any session operating the desk reads this first.

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
