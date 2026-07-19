# Henneth AI — Automation & Population Plan

Status: PROPOSED — awaiting owner go-ahead. Written 2026-07-14.
Goal: every part of the product that should stay current fetches and updates itself, on the
cheapest cadence that keeps a user's information fresh. Scores and Research pages fill with
real data. Nothing over-runs; everything is event-driven where it can be.

---

## 1. What already loops today (built, running)

| Loop | Cadence | Cost | Does |
|---|---|---|---|
| Cloud GitHub Actions | every 30 min (cron) + on every push | free | deterministic data: prices, quant, backtests, fair value, geo-risk, dossiers, gate, verify → deploy |
| Hourly task | weekdays hourly, market hours | cheap | run_cloud + news-sentinel + position monitor; escalates on impact≥4 |
| Daily task | weekdays 17:20 PKT | ~3 agents | news + macro + market-analyst commentary; GH self-heal nudge |
| Room-loop task | weekdays 17:47 PKT | ≤3 debates | reaffirm free / delta cheap / full debate for gate's picks; verifier QA gate; scores calls |

The material-hash gate means a covered ticker only re-debates when something *material* changes.
The whole universe stays current at a fraction of naive cost.

---

## 2. The gap: Scores & Research pages are thin

They render correctly but have little data because:
- **Persona calls** (Scores → our analysts): flowing, but only 1 ticker covered so far — fills as the Room loop rotates the universe (~4 weeks).
- **Broker calls** (Scores → brokers, Research → broker notes): **nothing yet** — no harvester.
- **Filings** (Research → company filings): only what news-sentinel happened to tag.

## 3. The one new loop to build — the Broker-Call Harvester

Smart approach (no gated-PDF scraping, which isn't freely available): **capture each research house's
PUBLIC calls as reported in the business press.** Mettis Global, Profit, Business Recorder and Dawn
Business routinely quote broker targets and ratings ("AKD raises UBL target to Rs X", "Topline
downgrades cement"). Those are free and legal to index.

**`fetch_broker_calls.py` (light agent, runs in the daily loop):**
1. Deterministic pre-filter (free): scan the news log + a few press RSS/index pages for items whose
   text matches a broker alias from `config/brokers.json` AND a call keyword (target price, rating,
   overweight, buy/sell/hold, initiate, PT).
2. A cheap agent pass (Haiku) over ONLY those matched items extracts the structured call:
   `{broker, ticker, kind: target|rating|thesis, value, horizon, date, source_url}`.
3. Each call → `research_index.json` (a broker note) + `claims.json` (source_type "broker", tagged to
   the broker's sector) → scored by `room_score.py` → **broker leaderboard fills**, and a new broker
   call flips the ticker's material-hash → the Room re-debates it (so the desk reacts to broker moves).

Cost: only the matched items get an agent, a handful per day. Deterministic filter does the heavy lifting.

## 4. Filings/AGM/results — make coverage active, not passive

Today filings appear only if the sentinel tags them. Add a **rotation sweep**: the daily loop asks the
news-sentinel to specifically check, for the ~5 stalest-covered tickers, their latest results /
corporate-briefing / AGM notice. Cheap (rides the sentinel already running), and guarantees every name's
filings refresh on a rotation rather than by luck.

## 5. Unified loop map after this plan

```
CLOUD (free, 30-min)         → prices, quant, fair value, dossiers, gate, verify, deploy
HOURLY (cheap)               → + news sentinel + monitor + escalation
DAILY 17:20 (few agents)     → + macro + analyst read
  └─ NEW: broker-call harvest (deterministic filter → Haiku extract → score)
  └─ NEW: filing rotation sweep (sentinel checks 5 stalest names' results/AGM)
ROOM-LOOP 17:47 (≤3 debates) → analyst research, verifier QA, persona scoring
WEEKLY                       → reviewer lessons + broker-scorecard recency decay + PM backlog pass
```

Every arrow is either free or hard-capped. New data (broker call, AGM, results) is what *triggers*
a re-debate — so updates are targeted, and the Scores/Research pages fill continuously from real,
sourced, scored calls.

## 6. What I'd build if you approve

1. `config/brokers.json` ✅ (already seeded — 10 PSX houses).
2. `fetch_broker_calls.py` — deterministic press/news filter → matched-item queue.
3. `room-broker-harvester` agent (Haiku) — extracts structured calls from matched items only.
4. Wire both into the daily task + the filing rotation sweep.
5. Weekly `broker-scorecard` recency decay + a reviewer sweep.
6. Verify Scores/Research fill with real calls; keep the verifier QA gate on everything.

## 7. Decisions for you
1. Approve the broker-call harvester (press-reported calls, not gated PDFs)?
2. Cadence for harvesting — daily (recommended) or twice-weekly to save tokens?
3. Any specific press sources you trust most (Mettis / Profit / BR / Dawn)?
