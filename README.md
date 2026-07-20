# Henneth

**A multi-agent research & analytics terminal for the Pakistan Stock Exchange.**
It researches, values, backtests, debates, and monitors — then puts every call on the record and grades it.
It **never places orders**; execution is manual on your broker.

> ⚠️ **This is a research & analytics tool, not an investment adviser.** Everything here is educational
> information — never personalized advice, a recommendation, or a promise of returns. Past performance
> does not predict future results. Investing in PSX carries risk, including the loss of capital. You make
> your own decisions. (A platform-wide footer + a "Research · not advice" badge repeat this on every page.)

**Live:** https://desk.henneth.app/  ·  private repo, hosted on Vercel
Docs: [`CLAUDE.md`](CLAUDE.md) (desk rules) · [`docs/SYSTEM-REGISTRY.md`](docs/SYSTEM-REGISTRY.md) (system map)
· [`docs/PRODUCT-ROADMAP.md`](docs/PRODUCT-ROADMAP.md) (path to a subscription product)

> **Reviewing this repo?** Start with [`CHANGELOG.md`](CHANGELOG.md) — newest first, and every entry states
> what changed, why, and for bugs how recurrence is prevented (including bugs introduced during a build and
> caught before shipping). Then read **Entitlements & security posture** and **Known gaps** below; both are
> written for audit rather than for marketing. Nothing is billed yet, and `state/legal.json` has not been
> reviewed by a lawyer.

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
  house view with an explicit dissent and dated, falsifiable calls. A **"watch the desk analyse" replay**
  plays the whole debate back as a staged, animated walkthrough (it animates the *saved* session — no
  agents run per view, so it's free and always available).
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

### The personal astrology pillar (`#/astro`, `#/mychart`, `#/cast`)

A Vedic (sidereal) financial-astrology layer, shipped as **exploration and cultural interest — explicitly
not an edge claim.** It exists because it is engaging and differentiated; it is framed honestly because
the desk tested it and it failed.

- **The desk's own test result, stated plainly:** `astro_backtest.py` ran **2,589 hypotheses across 101
  subjects** (99 stocks + KSE100 + KMI30) over ~19 years, and `astro_natal_test.py` ran **379** natal-method
  hypotheses across **27** verified company birth charts. **Zero survivors** in both after Bonferroni and
  Benjamini-Hochberg correction, on market-adjusted returns (`r − β·r_mkt`, so beta isn't mistaken for
  signal). At p<0.05 you would expect ~129.5 false positives from 2,589 tests by luck; 143 came back.
  The same machinery pointed at ordinary macro factors (`sector_macro.py`) *did* find real effects —
  **17 Bonferroni / 34 FDR survivors of 98**, e.g. oil→E&P at p=2e-5, joint R² ≤2.6%. That contrast is the
  point, and it is published in `state/astro_backtest.json` rather than summarised away.
  **The natal test carries an explicit power caveat:** with company charts this young it is weakly powered,
  so the result is *"not demonstrated"* — **not** *"disproved."* The desk keeps that distinction because
  claiming disproof would be a verdict it has not earned.
- **Your chart.** A user enters birth date/time/place; the browser casts their sidereal (Lahiri) natal
  chart from a committed 552 KB packed ephemeris (`state/natal_ephem.bin`, 1950–2035, daily, `<9H`
  tenths-of-a-degree) and scores every PSX name against it with classical techniques (Tara koota, Moon-lord
  friendship, benefic placement, dasha resonance). Ascendant is computed live from LST + latitude, and is
  **never invented** when birth time is unknown — the reading falls back to Chandra lagna, a real Vedic
  technique.
- **The daily layer.** The natal chart is static, so the product is the *moving* sky: gochara placed from
  the natal Moon and recomputed every day, a transit ring on the orrery, and dated "worth another look"
  shifts (ingresses, dasha/antardasha turnovers) — computed client-side from data already shipped, so it
  costs nothing per user.
- **Visuals.** An isometric-feel natal orrery (foreshortened orbits, native SVG pixel glyphs — *not*
  `foreignObject`, which breaks in Safari), a Vimshottari dasha ribbon with an antardasha sub-period strip,
  per-stock timing windows, and 8 commodities read through their traditional rulers.
- **Scored like anything else.** `astro_claims.py` files dated, **market-relative** astro claims with a
  stamped benchmark level, graded on the same public scorecard as every broker call.

### Three plans, one data layer (`#/plans`)

**Free → Investor → Pro → Broker.** The tier above Free is named **Investor** deliberately — a paid tier
named for what the customer *lacks* ("Learner") reads as a label on the customer.

| Plan | For | Adds |
|---|---|---|
| **Free** | anyone | Cast your chart, the daily desk note, the public track record |
| **Investor** | people new to investing | The guided path, full astro reading, dividends, earnings |
| **Pro** | TA/FA-literate investors | Model fair value, running the strategy library, research library |
| **Broker** | research houses | *Not built.* Plan defined; their own calls scored in public |

- **The Investor desk** (`#/learn`) — 4 levels that unlock in order, 17 lessons, played **one card per
  screen** in a focused player rather than as a long scroller. Card kinds are visually unmistakable:
  lesson · watch out · the point · interactive · check yourself. Progress persists per user.
  Level 2 ("The documents") covers every document a Pakistani listed company publishes — annual report,
  the three financial statements, auditor's report, pattern of shareholding, related-party transactions,
  AGM notices, material information — with **tap-to-learn labelled statements**, a 12-document map, and a
  dividend-date timeline.
- **Rule 2 inside the teaching.** `fundamentals.json` holds revenue, net income and EPS but **not** gross
  profit, opex or finance cost. So the labelled income statement shows real reported figures **only on the
  lines the desk actually holds** (anchored to a real, named company), and every other line reads
  *"in the filing"* — teaching the reader to go find it. No statement line is ever fabricated.
- **The acquisition funnel.** Casting a chart requires **no account** (it is client-side maths over an
  ephemeris the browser already fetches). A guest casts free, the chart is held in `localStorage`, and
  `migrateGuestChart()` lifts it into their profile on sign-in — birth details are never entered twice.
  Free users see their real chart plus their strongest 3 matches; the rest sits behind one shared
  `planWall()` component with fixed, honest language.

## Principles (locked — see `CLAUDE.md`)

- **Long-only, daily timeframe.** No shorts, no leverage, no intraday scalping.
- **All numbers come from the data layer.** No agent quotes a price from memory; unknown ≠ guessed.
- **Research, never advice.** No "buy/strong buy/guaranteed" language anywhere. Losses are expected.
- **Brokers are audited, never trusted** — every broker call is scored on the leaderboard.
- **The Auditor keeps veto**; the Room only informs the strategist.

## Repo layout — one repo, two sites, two domains

Both the marketing site and the terminal live in **this single repo**. They are two *separate
Vercel projects* pointed at the same GitHub repository but different root directories, so one
`git push` can deploy either or both depending on what changed.

| surface | source | build config | domain |
|---|---|---|---|
| **Marketing site** | `site/` (Astro) | `site/vercel.json` | **henneth.app** — the root domain |
| **The terminal** | `dashboard/` + `state/` | `vercel.json` (repo root) | **desk.henneth.app** |

The root `vercel.json` copies `dashboard/index.html`, `app.js`, `themes.css` and the whole
`state/` tree into `public/` — that is the entire terminal build (no bundler, no framework).
`site/` is a normal Astro project with its own `package.json`; its `node_modules` is gitignored,
so only ~30 source files of it are tracked.

**Why the split.** The terminal used to own the root domain. Marketing needs the root (that is
what people type and what a link preview shows), so the terminal moved to a subdomain. Anything
pointed at the apex expecting `/state/*.json` will now 404 — the marketing site has no `state/`.
`watchdog.py` therefore targets `desk.henneth.app` explicitly, and says so in a comment, because
a watchdog silently checking the wrong surface is worse than no watchdog.

**Naming convention** (the single source of truth is `site/src/site.config.ts`): the product is
**Henneth** everywhere public — the brand, the domain, this README. It is **Henneth Desk** only
*inside* the app, where the distinction between the company and the tool actually matters.

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
**full** (material change or never covered → a budget-capped debate). So the whole universe stays current at a
small fraction of naive cost, and new AGM/broker/news data *targets* exactly the ticker that changed.

**Two liquidity gates, deliberately separate** (`scripts/liquidity.py` → `state/liquidity.json`).
Coverage reaches the whole KSE All Share (554 symbols), which made ~350 thin names visible, so
"is this worth analysing" and "would the desk ever trade it" became different questions:

| gate | threshold | decides | count |
|---|---|---|---|
| **research** | ≥ Rs 5M ADTV + ≥ 500 bars | what gets backtests, fundamentals, predictability | 208 |
| **signal** | ≥ Rs 30M ADTV | what can ever produce a published setup | 100 |

A name can be fully researched and still never produce a setup — the ticker page says so out loud
rather than showing an empty signal section. Liquidity is measured with the published estimators, not
a turnover rule of thumb: **Amihud (2002)** price impact, **Corwin-Schultz (2012)** high-low spread
(with the overnight adjustment and per-observation zero floor), **Fong-Holden-Trzcinka (2017)** for
cost magnitude where no quote data exists, **Roll (1984)**, and **SEC Rule 22e-4** days-to-liquidate
classified at the *stressed* participation rate.

**Backtests pay a per-symbol spread, not a flat fee.** Each name is charged
`max(config floor, estimated round-trip cost)`. Lesmond, Schill & Zhou (2004) showed the stocks
producing the largest momentum returns are the same stocks that cost the most to trade — and most of
this 70-strategy library is breakout/momentum, so a constant cost assumption flatters exactly the names
it should penalise. Switching it on removed 64 of 591 previously "eligible" strategy-ticker pairs.
Those were artefacts of an unrealistic cost assumption, not edges.

**Four self-checking systems** watch different failure classes:
1. **Data QA** — flags glitchy/inconsistent numbers (e.g. a bad "-83% drop") → verifier web-checks, can block.
2. **Deploy QA** — `preflight.py` gates the build; a structurally broken cycle can never publish.
3. **Design QA** — flags corner/padding/token/typography drift → design-reviewer fixes surgically.
4. **Code QA** — two tiers: an instant free syntax gate inside `preflight.py` on *every* publish, plus a
   weekly `/code-review` deep pass (8-angle finder + verify) that fixes clear-cut correctness/security bugs
   and flags judgment calls. The repo has no tests or linter, so this is the only check on the CODE itself.

## Automation (loops)

Loops run locally (while the Claude app is open) and `push` to `main`; each push auto-deploys on Vercel.

| Loop | When | Cost | Does |
|---|---|---|---|
| Market checkpoints | weekdays 11:00 & 17:00 PKT | cheap | data + news sentinel + position monitor → push |
| Daily | weekdays 17:20 PKT | ~3 agents | macro + analyst read → push |
| Room-loop | weekdays 17:47 PKT | budget-capped debates | Desk Room debates + QA + scoring → push |
| Weekly-harvest | Sat 11:00 PKT | 1 haiku agent | broker calls (Profit/Dawn/Mettis) + filings → push |
| Code review | Sat 12:00 PKT | 1 review pass | `/code-review` on the week's diff; fixes clear-cut bugs → push |
| Product scout | Sun 12:10 PKT | 1 lean agent | ranks a product backlog. **Proposes only, never builds.** |

The Room loop is staged, not hand-orchestrated: `room_batch.py` splits the gate's plan into per-ticker
files, the persona agents **write their own output**, and `room_assemble.py` is the single writer of
`rooms.json`. Routing agent output back through the orchestrator's context was what previously capped
a batch at 3; agents writing directly cost ~10 orchestrator tokens each instead of ~800.

Every push runs the same gate (`preflight.py`) before it publishes, so a broken cycle never reaches the live site. `scripts/publish.py "<msg>"` is the one push helper all loops use.

**`publish.py` stages `state/` only.** It used to `git add -A`, which staged the whole working tree —
and since the cloud cron and every interactive session share one checkout, a routine data refresh could
sweep up another session's half-finished edits and ship them under an unrelated commit message. Shipping
code is now a deliberate `--code` opt-in; anything left unstaged is listed, never silently included or
silently dropped. The weekly code review is the only loop that needs the flag.

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
- **Sectors:** parsed from PSX's own screener (`fetch_sectors.py`), verified against 19 anchor tickers and
  kept at last-good on mismatch. This fixed two live bugs: Rule 4's same-sector limit and peer P/E, which
  had been comparing against the **whole-market** median while labelled "priced like its peers" (8 tickers
  changed verdict when corrected).
- **Indices:** `fetch_indices.py` appends KSE100/KMI30 levels daily — the index history needed to grade
  market-relative claims honestly (a stock falling 2% while the market fell 8% must not score as a hit for
  "underperforms").
- **Ephemeris:** `pymeeus`-derived sidereal positions (Lahiri ayanamsa from precessing Spica), pre-baked
  into a committed binary table for the browser. Chosen over `pyswisseph` (won't build on 3.14) and
  `skyfield` (needs a 17 MB kernel).
- **Cross-check:** `tradingview-ta` (screener=pakistan) verifies the quant layer; a mismatch blocks signals.
- **Stack:** Python 3.14 (requests/pandas/numpy) · vanilla JS SPA (hash router, canvas charts, no framework)
  · JetBrains Mono + Pixelify Sans · **Supabase** (auth + per-user profiles/watchlist/plan) · **Vercel** hosting.

## Entitlements & security posture

Billing is **not wired**. Card processing through international providers is unavailable in Pakistan, so
payment will run through a local gateway (PayFast or similar) later. Until then plans are set manually and
the product says so on `#/plans` rather than showing a dead checkout.

- **`BILLING_LIVE = false` is the single switch.** While false, any signed-in account reads as subscribed,
  so shipping paywalls could not strip access from accounts that already had it. Flipping it moves access
  entirely onto the plan's feature list.
- **A user cannot promote their own plan.** `profiles.plan` is guarded at the database by a CHECK
  constraint plus two triggers: a `BEFORE UPDATE` trigger reverts `plan`/`plan_since` for role
  `authenticated`, and a `BEFORE INSERT` trigger forces `plan='free'`. **The INSERT trigger is
  load-bearing** — the client writes profiles via `upsert`, so an UPDATE-only guard would have left a
  crafted insert able to self-grant `pro`. This was caught and closed during the build. Plan changes are a
  service-role-only path.
- `ui_mode` (which desk shell you see) is deliberately client-writable — it is a view preference, not an
  entitlement.
- **Owner preview.** `#/plans` carries an owner-only "preview as plan" switch that re-renders the whole
  product as any tier without changing the stored plan (in-memory; a reload resets it).
- Per-user rows (watchlist, notes, birth data, learn progress) are RLS-scoped to their owner. The research
  layer is shared and read-only to users.

### Known gaps, stated for audit

- **`state/legal.json` is `review_status: DRAFT`.** Terms/Privacy/Risk are drafted but **not reviewed by a
  Pakistani lawyer**. This is a hard gate before charging anyone.
- **Two Supabase items are outstanding on the owner:** rotate/disable the legacy `service_role` key, and
  enable leaked-password protection.
- **The track record is young.** **95 dated claims are filed and 0 have resolved** (verified against
  `state/claims.json` at the time of writing) — a waiting period, not a proven record, and the product
  displays the real counts rather than implying otherwise.
- **The Broker plan is defined, not built.** No leaderboard API, white-label, or broker-side scoring exists.
- **The astrology layer has no demonstrated edge** (see above). It is excluded from signal confluence and
  never feeds a setup.
- The repo has **no test suite or linter**; correctness rests on `preflight.py`, `room_verify.py`,
  `design_lint.py`, and the weekly `/code-review` pass.

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
