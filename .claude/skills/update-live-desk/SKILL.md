---
name: update-live-desk
description: Refresh the live PSX Trade Desk at wasayijaz.github.io/psx-trade-desk and push the update. Use when the user says "update the desk", "refresh the live site", "push new data", "run the desk", "update signals", or wants the public dashboard refreshed. Knows the token-cheap path (trigger the free cloud pipeline) vs the token-spending path (run LLM agents for commentary).
---

# Update the live PSX Trade Desk

Live site: https://wasayijaz.github.io/psx-trade-desk/ (GitHub Pages, repo `wasayijaz/psx-trade-desk`).
Repo root locally: `D:\PSX Trader X Claude`.

## Architecture recap (so you pick the cheapest path)
- **Deterministic desk** (prices, quant, 52 strategies, candidate signals, scorecards,
  geo-risk, dividends, calendar): rebuilt by **GitHub Actions every 30 min during market
  hours, FREE, zero tokens**. Also runnable on demand.
- **Agent commentary** (daily read, news tagging, macro narrative): needs LLM tokens.
  The cloud does NOT run agents — it reuses whatever agent JSON is committed. So agent
  data only changes when THIS chat runs the agents and pushes.

## TOKEN RULES — read before doing anything
1. **Never run the agents just to refresh prices.** Prices/strategies/signals refresh
   for free in the cloud. If the user only wants fresh market data, use Path A (a one-line
   cloud trigger) — it costs ~nothing.
2. **Only run agents when the user explicitly wants fresh commentary** (daily read / news /
   macro), and prefer **once per day** (pre-market), never every 30 min.
3. Run agents **sequentially and only the ones needed**, not the whole roster. news-sentinel
   + macro-agent + market-analyst is the daily set; skip strategist/risk/auditor unless the
   user wants audited signals (candidate signals are already generated deterministically).
4. Keep sessions lean — this skill is meant to run in a short fresh chat, not a giant one.

## Path A — cheap data-only refresh (no tokens)
Just trigger the free cloud pipeline; it rebuilds data and redeploys Pages:
```bash
gh workflow run desk.yml --repo wasayijaz/psx-trade-desk
```
Optionally confirm: `gh run list --repo wasayijaz/psx-trade-desk --limit 1`.
Done. Nothing else needed. Use this for "refresh the market data / signals".

## Path B — refresh agent commentary (spends tokens, do daily at most)
1. `cd "D:\PSX Trader X Claude"` and `git pull` (stay in sync).
2. Refresh the deterministic layer locally so agents read current numbers (fast, free):
   `python scripts/run_cloud.py` (single entrypoint; skips the slow deep-history refetch
   if `state/history_deep/` already populated).
3. Run ONLY the needed agents (each writes its JSON into `state/`):
   - **news-sentinel** → `state/newslog.json`
   - **macro-agent** → `state/macro.json` (reads `state/global.json`, `state/georisk.json`)
   - **market-analyst** → `state/daily_read.json`
   (For audited signals only if asked: strategist → risk-officer → auditor → `state/signals.json`.)
4. `python scripts/build_dashboard.py` (regenerates dashboard.json + candidate signals).
5. Commit + push so the cloud redeploys with the new commentary:
   ```bash
   git add -A && git commit -m "Desk update: <what changed>" && git push
   ```
   The push triggers the workflow → Pages redeploys within a few minutes.

## Notes / gotchas
- The gh token here lacks `workflow` scope — you CANNOT edit `.github/workflows/desk.yml`
  by push or API. If the workflow itself needs changing, the user edits it in the GitHub
  web UI (Actions tab).
- Agent JSON files (newslog, macro, daily_read) ARE committed; deterministic per-ticker
  history/intraday are gitignored and regenerated in the cloud each run.
- Market data is DPS end-of-cycle snapshots (≈30-min cadence during PSX hours), NOT
  tick-by-tick real time. On weekends the site holds Friday's last session.
- After pushing, verify: `curl -s https://wasayijaz.github.io/psx-trade-desk/state/dashboard.json | python -c "import sys,json;print(json.load(sys.stdin)['updated'])"`
