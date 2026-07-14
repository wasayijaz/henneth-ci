---
name: update-live-desk
description: Refresh the live PSX Trade Desk (psx-trade-desk.vercel.app) and push the update. Use when the user says "update the desk", "refresh the live site", "push new data", "run the desk", "update signals", or wants the dashboard refreshed. Knows the token-cheap path (deterministic data only) vs the token-spending path (LLM agents for commentary).
---

# Update the live PSX Trade Desk

**Live:** https://psx-trade-desk.vercel.app/ · repo `wasayijaz/psx-trade-desk` (**PRIVATE**, hosted on **Vercel**).
Local root: `D:\PSX Trader X Claude`. **A `git push` to `main` = a Vercel deploy** (auto, ~60s). There is no
GitHub Pages and no GitHub Actions cron anymore — do NOT run `gh workflow run` or expect a cloud rebuild.

## Architecture recap (pick the cheapest path)
- **Deterministic desk** (prices, quant, 52 strategies, signals, fair value, dossiers, scorecards, geo-risk,
  dividends, calendar, verify, design-lint): rebuilt by `scripts/run_cloud.py` — **FREE, zero tokens**.
- **Agent commentary** (daily read, news tagging, macro, Desk Room debates): needs LLM tokens. These only
  change when a chat/task runs the agents and pushes. Vercel just serves whatever is committed.

## TOKEN RULES — read first
1. **Never run agents just to refresh prices.** Data-only = Path A (deterministic, ~free).
2. Only run agents when the user wants fresh **commentary/debates**, and at most **once/day**.
3. Run only the agents needed, sequentially — not the whole roster.
4. Keep the session lean; this is a short focused refresh, not a big chat.

## Path A — data-only refresh (no tokens)
```bash
cd "D:\PSX Trader X Claude" && git pull --rebase
python scripts/run_cloud.py     # fetch → quant → signals → dossiers → gate → verify → build → PREFLIGHT
```
If preflight passes, publish (see below). Use this for "refresh the market data / signals".

## Path B — refresh agent commentary (spends tokens, daily at most)
1. `cd "D:\PSX Trader X Claude"` · `git pull --rebase` · `python scripts/run_cloud.py` (so agents read current numbers).
2. Run ONLY the needed agents (each writes its JSON into `state/`):
   - **news-sentinel** → `state/newslog.json`
   - **macro-agent** → `state/macro.json`
   - **market-analyst** → `state/daily_read.json`
   (Desk Room debates are their own scheduled loop — don't run them here unless asked.)
3. `python scripts/build_dashboard.py` (folds commentary + regenerates signals; runs the preflight gate).

## Publish (the efficient push — same for both paths)
Only push if something actually changed, and only if preflight is green:
```bash
python scripts/preflight.py || { echo "preflight FAILED — not publishing"; exit 1; }
git add -A
git diff --cached --quiet && echo "nothing changed" || (git commit -m "Desk update: <what changed>" && git push)
```
The push auto-deploys to Vercel. Verify after ~60s:
```bash
curl -s "https://psx-trade-desk.vercel.app/state/dashboard.json" | python -c "import sys,json;print(json.load(sys.stdin)['updated'])"
```

## Notes / gotchas
- `state/history_deep`, `state/history`, `state/intraday` are now COMMITTED (repo is self-contained for
  Vercel). `run_cloud` regenerates them; `git add -A` re-commits the small deltas.
- Data is DPS end-of-cycle snapshots (~30-min cadence in PSX hours), not tick real-time. Weekends hold Friday.
- Auth/accounts: Supabase (publishable key in app.js, RLS-protected). Nothing to touch here for a data refresh.
- If a push seems not to deploy, check the Vercel project `psx-trade-desk` (team Jobintel) — the git
  integration auto-builds on push; no manual step.
