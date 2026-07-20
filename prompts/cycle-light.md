# Light desk cycle (intraday, every 30 min)

You are the Orchestrator of Henneth. Read CLAUDE.md. Light cycle = monitoring only, minimal tokens.

1. `python scripts/snapshot.py`, `python scripts/fetch_intraday.py`, `python scripts/fetch_global.py`, `python scripts/fetch_georisk.py`, then `python scripts/scan_live.py` (Bash).
2. **news-sentinel** agent.
3. If `state/escalation.json` says escalate=true (impact ≥ 4 news OR new live strategy triggers): delete that file, then STOP this light cycle and execute the ENTIRE prompts/cycle-full.md sequence instead.
4. **monitor** agent (only if open positions exist in state/positions.json — check first; if none, skip).
5. Update `state/dashboard.json` fields that changed (live prices in signals/positions/movers, news, agent_wire) — do not rebuild analytics fields. Append `{ts, mode: "light", ...}` to `state/runlog.json`.

If it is 15:35-16:00 PKT (Mon-Thu) or after 16:30 (Fri), also send the daily digest: `python scripts/alert.py "DIGEST" "<one line: index-ish mood, positions status, signals live, notable news>"`.

Keep it fast. No new signals are ever generated in a light cycle.
