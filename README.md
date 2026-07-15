# PSX Trade Desk

**A multi-agent research & analytics terminal for the Pakistan Stock Exchange.**
It researches, values, backtests, debates, and monitors — then puts every call on the record and grades it.
It **never places orders**; execution is manual on your broker.

> ⚠️ **This is a research & analytics tool, not an investment adviser.** Everything here is educational
> information — never personalized advice, a recommendation, or a promise of returns. Past performance
> does not predict future results. Investing in PSX carries risk, including the loss of capital. You make
> your own decisions. (A platform-wide footer + a "Research · not advice" badge repeat this on every page.)

**Live:** https://psx-trade-desk.vercel.app/  ·  private repo, hosted on Vercel
Docs: [`CLAUDE.md`](CLAUDE.md) (desk rules) · [`docs/SYSTEM-REGISTRY.md`](docs/SYSTEM-REGISTRY.md) (system map)
· [`docs/PRODUCT-ROADMAP.md`](docs/PRODUCT-ROADMAP.md) (path to a subscription product)

---

## What it does

A single-page terminal (collapsible sidebar, hard-cornered mono "Bloomberg-lite" design) over the whole PSX universe:

- **Today** — the desk's plain-English daily read: tone, favoured/avoided sectors, a short watchlist.
- **Board** — live universe heatmap, backtest-proven signals, predictability ranks, positions, news + agent wire.
- **Value** — every stock valued four ways (peer P/E, earnings-power vs bond yield, Graham, DDM); the
  median is the model fair value, with the full working expandable per row.
- **Strategies** — 52 transparent, rule-based strategies, each backtested on every stock's ~19-year history
  (win rate, expectancy after costs, out-of-sample) — you see what *actually* worked, not theory.
- **The Desk Room** (on every ticker) — named AI analyst personas research and **debate** the stock:
  a technical desk and a fundamental desk (kept separate), a bull vs a bear, and a Chair who synthesises a
  house view with an explicit dissent and dated, falsifiable calls.
- **Scores** — track records. Every dated call — the desk's own analysts **and** the brokers — is scored
  against what prices actually did. Brokers are ranked overall and per sector.
- **Research** — broker notes and company filings (results / AGM / corporate-briefing), digested and tagged.
- **Macro / Dividends / Earnings / News** — the global tape that moves PSX, a geo-risk radar, dividend
  timing (buy-by / ex-date), the earnings calendar, and a permanent news log.

Each ticker page also carries a **risk profile** (volatility, real max-drawdown with era context, liquidity,
valuation, dividend reliability), a **"questions before buying"** checklist, and **"what the brokers say."**

- **Accounts** — sign-up / sign-in (Supabase Auth), a short onboarding quiz + guided wizard, and a personal
  **watchlist** that overlays the shared research. Per-user data is row-level-secured; the research layer is
  shared and read-only to users.

## Principles (locked — see `CLAUDE.md`)

- **Long-only, daily timeframe.** No shorts, no leverage, no intraday scalping.
- **All numbers come from the data layer.** No agent quotes a price from memory; unknown ≠ guessed.
- **Research, never advice.** No "buy/strong buy/guaranteed" language anywhere. Losses are expected.
- **Brokers are audited, never trusted** — every broker call is scored on the leaderboard.
- **The Auditor keeps veto**; the Room only informs the strategist.

## Architecture — free layer does the heavy lifting; agents only judge

```
DETERMINISTIC PYTHON (free, no tokens)                 AGENTS (tokens, right-sized model)
  data fetch  → quant/predictability/backtest            news · macro · market-analyst (commentary)
  fair value  → signals → dossiers → coverage gate        Desk Room: chartist · fundamentalist ·
  scoring     → leaderboards → QA (verify + design lint)   debate(bull+bear) · chair · librarian · verifier
  build_dashboard → preflight gate → deploy               broker-harvester · design-reviewer
```

**The efficiency engine.** A per-ticker *material hash* (valuation verdict, scorecard, new documents,
high-impact news, earnings proximity — **not** price) drives a coverage gate that tiers every ticker each
cycle: **reaffirm** (unchanged → last view stands, 0 tokens) · **delta** (price moved → cheap refresh) ·
**full** (material change or never covered → the ≤3/day debate). So the whole universe stays current at a
small fraction of naive cost, and new AGM/broker/news data *targets* exactly the ticker that changed.

**Four self-checking systems** watch different failure classes:
1. **Data QA** — flags glitchy/inconsistent numbers (e.g. a bad "-83% drop") → verifier web-checks, can block.
2. **Deploy QA** — `preflight.py` gates the build; a structurally broken cycle can never publish.
3. **Design QA** — flags corner/padding/token/typography drift → design-reviewer fixes surgically.
4. **Code QA** — weekly `/code-review` pass (8-angle finder + verify) on the week's code changes; fixes
   clear-cut correctness/security bugs, flags judgment calls. The repo has no tests or linter, so this is
   the only recurring check on the CODE itself (the other three watch data/build/design, not logic).

## Automation (loops)

Loops run locally (while the Claude app is open) and `push` to `main`; each push auto-deploys on Vercel.

| Loop | When | Cost | Does |
|---|---|---|---|
| Market checkpoints | weekdays 11:00 & 17:00 PKT | cheap | data + news sentinel + position monitor → push |
| Daily | weekdays 17:20 PKT | ~3 agents | macro + analyst read → push |
| Room-loop | weekdays 17:47 PKT | ≤3 debates | Desk Room debates + QA + scoring → push |
| Weekly-harvest | Sat 11:00 PKT | 1 haiku agent | broker calls (Profit/Dawn/Mettis) + filings → push |

Every push runs the same gate (`preflight.py`) before it publishes, so a broken cycle never reaches the live site. `scripts/publish.py "<msg>"` is the one push helper all loops use.

## Run it locally

```bash
python scripts/serve.py           # → http://localhost:8877/dashboard/
python scripts/run_cloud.py       # the whole free pipeline (fetch → quant → … → preflight)
python scripts/preflight.py       # deploy gate: exits non-zero if the data would render broken
```

Hosted on **Vercel** (private repo, auto-deploys on every `push` to `main`; `vercel.json` assembles the
static site + committed `state/` data). The refresh loops push fresh data → Vercel redeploys.

## Data & stack

- **Prices:** PSX DPS portal (EOD `[ts, close, volume, open]` — no high/low, so ATR is a close-to-close
  proxy); **Yahoo Finance `.KA`** for ~19-year adjusted history (auto de-glitched) used on charts + long-run stats.
- **Fundamentals:** stockanalysis.com (P/E, EPS, margins, dividends, earnings dates).
- **Cross-check:** `tradingview-ta` (screener=pakistan) verifies the quant layer; a mismatch blocks signals.
- **Stack:** Python 3.14 (requests/pandas/numpy) · vanilla JS SPA (hash router, canvas charts, no framework)
  · JetBrains Mono + Pixelify Sans · **Supabase** (auth + per-user profiles/watchlist) · **Vercel** hosting.

## Governance (the desk can't quietly disagree with itself)
`CLAUDE.md` is enforced, not aspirational: one **position-sizing formula** (risk by stop distance,
capped at 8% position value — Strategist and Auditor compute it identically), a **circuit breaker**
that won't auto-resume into a bad regime, **stale-position time-stops**, **immutable live strategy
files** (edits create a new version + fresh backtest), an explicit **no-lookahead** rule the Auditor
can veto on, a fixed **news impact 1–5 scale**, and a **calendar-freshness guard** (`data_health.py`
degrades if session times go 60 days unverified, halting new signals). The **Auditor keeps veto**.

## Docs
- [`CLAUDE.md`](CLAUDE.md) — the desk rules every agent obeys.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — **operations runbook**: the hybrid cloud/app model, the one publish path, safety gates, and how to run every flow without breaking live. Read this first when operating the desk.
- [`docs/SYSTEM-REGISTRY.md`](docs/SYSTEM-REGISTRY.md) — index of every agent, loop, script, and state file.
- [`docs/DESK-ROOM-PLAN.md`](docs/DESK-ROOM-PLAN.md) — the multi-agent analyst design.
- [`docs/AUTOMATION-PLAN.md`](docs/AUTOMATION-PLAN.md) — the whole-product loop map.
- [`docs/PRODUCT-ROADMAP.md`](docs/PRODUCT-ROADMAP.md) — single-tenant → subscription product (auth, delivery, billing, compliance).
- [`CHANGELOG.md`](CHANGELOG.md) — what changed and why.

---
*Educational and informational research only — not personalized investment advice. Past performance does
not guarantee future results. Investing in PSX carries risk, including the possible loss of capital.*
