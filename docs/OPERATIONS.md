# PSX Trade Desk — Operations Runbook

**Read this before touching anything that reaches the live site.** It is the single source of truth
for how the desk runs, who does what, and how to publish without breaking the live website. Governance
rules (position sizing, circuit breaker, no-lookahead, etc.) live in [`CLAUDE.md`](../CLAUDE.md); this
doc is about *operations*.

Live site: https://psx-trade-desk.vercel.app/ · Repo: private, hosted on Vercel · Auth/DB: Supabase.

---

## 1. The hybrid architecture (who runs what, where)

Two halves, on purpose. The split is what gives 24/7 freshness at controlled token cost.

```
COMPUTER OFF — GitHub Actions cloud cron  (.github/workflows/desk-data.yml)   FREE, no tokens, no agents
  every 30 min off-peak, market hours →  python scripts/run_cloud.py
  = prices · quant · backtests · fair value · health · dashboard
    + Desk Room DETERMINISTIC scaffolding (dossiers · queue · gate · scoring)
  → publish.py → push → Vercel deploy → watchdog

COMPUTER ON — app scheduled tasks (Claude app, ~/.claude/scheduled-tasks/)     tokens, owner present
  the JUDGEMENT/agent work: news-sentinel · monitor · macro · daily read
  · the Desk Room DEBATES (chartist/fundamentalist/bull/bear/chair) · weekly broker harvest
  → publish.py → push → Vercel deploy → watchdog

ALWAYS — every visitor sees the full SAVED analysis 24/7 (debates, TA/FA, 52 backtests, scores),
  because agent output is persisted in state/ and served statically. Agents REFRESH it; they are
  not needed for a user to READ it. Nothing goes dark when the computer is off.
```

**Rule of thumb:** deterministic/data work can run in the cloud; anything that needs Claude (an agent)
runs on the owner's machine. The cloud never runs an agent (no API key by design).

---

## 2. The ONE publish path — never hand-push state

**Always publish with `python scripts/publish.py "<message>"`. Never `git push` state files by hand.**

`publish.py` is the shared choke point every loop and the cloud use. It:
1. runs `preflight.py` (the pre-deploy gate) — **if it fails, nothing publishes**, last-good site stays live;
2. stages, and commits **only if state actually changed** (a no-op otherwise);
3. pushes **race-safely** — the cloud cron and app loops both push to `main`, so on a rejected
   (non-fast-forward) push it rebases onto latest preferring our fresh state (`-X theirs`) and retries.
   Whatever the other side raced in regenerates next cycle, so nothing is lost.
4. A push to `main` is the entire deploy — Vercel auto-builds in ~60s. There is no separate deploy step.

---

## 3. The safety gates (why the live site doesn't break)

Layered, so a bad cycle can't reach users and a transient glitch can't blank a page:

- **`preflight.py`** (before publish): re-reads every file the UI joins on; asserts shape, non-empty,
  no NaN/Infinity, and **per-ticker history completeness** (the "No data for XXX" class). Also runs two
  free Tier-1 gates on every publish: **code syntax** (`check_code_syntax` — `ast.parse` all scripts +
  `node -c app.js`) and **accuracy/provenance** (`provenance_lint.py` — see §3b). Exits non-zero
  → `publish.py` aborts.
- **`watchdog.py`** (after publish): fetches the LIVE Vercel URLs a browser hits and checks they are
  reachable, fresh, non-empty, health not degraded, and sampled ticker histories serve. Wired into every
  publishing loop; if it fails, the loop re-publishes once then reports loudly. Run ad hoc:
  `python scripts/watchdog.py`.
- **`data_health.py`** (Rule 6): if `health.json.status != ok`, NO new signals generate that cycle
  (monitoring continues). `tv_crosscheck` feeds it but only a **genuine glitch** (close off >20% =
  decimal/split/wrong-symbol; widened 2026-07-15 to safely clear real corporate-action adjustment gaps)
  degrades health; TV lag/adjustment **drift** is advisory and never freezes the desk (a TV-vs-DPS
  mismatch is not an error — CLAUDE.md).
- **Client resilience** (in `app.js`): `j()` retries + XHR fallback + last-known-good; a router try/catch
  never leaves a blank screen; a 30-second auto-refresh self-corrects transient misses; the ticker page
  self-heals with retry.

---

## 3a. Code QA — the layer that was missing until 2026-07-15

The three gates above watch **data**, **build shape**, and **design** — none of them read the actual
**code** for correctness or security bugs. The repo has no tests and no linter (Python or JS), and pushes
directly to `main` with no PR/CI review, so nothing was catching real defects before they went live.
Two tiers now close this gap, deliberately NOT a `.github/workflows/*` CI file — see §5's gotcha on why
adding those needs the GitHub web UI; both tiers below avoid that entirely and need no owner action.

**Tier 1 — instant, free, every publish.** `check_code_syntax()` inside `preflight.py` (added 2026-07-15)
`ast.parse`s every `scripts/*.py` and runs `node -c dashboard/app.js`, and FAILS the gate (blocks publish)
on a real syntax error. Since `preflight.py` is the one gate every surface already runs through — the
cloud cron (`desk-data.yml` → `run_cloud.py` → `preflight.py`), every app-scheduled task, and any manual
`publish.py` call — this runs on literally every publish, everywhere, for zero added cost and no new
infrastructure. It catches "the build is broken" the moment it happens, not up to a week later.

**Tier 2 — weekly deep review.** `psx-desk-code-review` (Sat ~12:00 PKT) runs the `/code-review` skill
(8 finder angles — line-by-line, removed-behavior, cross-file, reuse, simplification, efficiency, altitude,
CLAUDE.md conventions — each candidate independently verified CONFIRMED/PLAUSIBLE/REFUTED before it's
reported) against the week's code diff. This is the one that catches things a syntax check can't: logic
bugs, security holes, silently-swallowed errors, dead code. Clear-cut, low-risk fixes are applied directly
and published through the normal gated path; genuine judgment calls (thresholds, design tradeoffs,
anything behavior-changing) are reported, not auto-fixed. Effort is `medium` for the routine weekly pass —
request a `high`/`ultra` pass explicitly before anything high-stakes (e.g. before turning on billing).
Weekly (not daily/per-push) by design: each pass spends real tokens (multiple agent calls), and a syntax
break is already caught instantly by Tier 1 — the deep pass exists to catch what only careful reading
catches, which doesn't need same-day turnaround the way a broken build does.

**First pass (2026-07-15, `high` effort, ~800-line session diff, first review this repo has ever had)**
found and fixed 10 real, verified issues, including: an XSS vector (a broker name could break out of an
`onclick` attribute — `esc()` didn't escape quotes; fixed globally + the call site converted to the same
safe `data-*` + delegated-listener pattern already used for the watchlist star), silent financial-data loss
(the portfolio "add holding" and private-note save paths discarded the real error and showed a false
"Saved ✓"), a governance gap (`tv_crosscheck.py`'s error/drift escalation only ever looked at the `close`
field — a genuine indicator-only glitch was invisible to both health-gating and the advisory log; and
`auditor.md` still instructed a literal `"FAIL"` string match against a status vocabulary that had moved to
PASS/DRIFT/ERROR, silently defeating the Auditor's veto per CLAUDE.md Rule 7), and an architecture fix to
`publish.py` itself (the race-safe conflict auto-resolve used to apply to the WHOLE working tree via
`git add -A` — a rebase conflict on any hand-authored file, not just regenerated `state/` data, could be
silently resolved by discarding the other side's edit with zero visibility; now conflict auto-resolve is
scoped to `state/` files only, and any conflict outside that aborts and fails loudly for a human to
resolve by hand instead of guessing).

---

## 3b. Accuracy QA — "are we presenting fact, not assumption?" (2026-07-15)

The desk's credibility is that it never shows an assumed/placeholder/stale number as fact. Two tiers:
- **Tier 1 (free, every publish):** `scripts/provenance_lint.py`, wired into `preflight.py`. Hard-FAILs
  (blocks publish) on: **stub markers** (TODO/PLACEHOLDER/TBD/lorem/`<INSERT` in any rendered state
  field), **hollow analysis** (a Desk Room `house_view` present but its summary/conviction empty), and
  **grossly stale analysis** (a house view computed at `price_at_session` now >30% from the live close).
  WARNs (surfaces, doesn't block) on 15–30% staleness. Deliberately unambiguous checks only — it never
  guesses whether a *target* price is "wrong" (that's a legit forward call, not an assumption).
- **Tier 2 (judgment):** the existing `room-verifier` agent already cross-examines each ticker's numbers
  against the data + web before a Room session publishes, and records its verdict in `rooms.json[SYM].qa`.
  The desk is already partly self-aware here — house views caveat their own soft spots (e.g. "leans on an
  unverified 30% growth assumption"). The weekly `psx-desk-product-scout` (§3c) reads those `qa` caveats to
  propose accuracy improvements.

## 3c. Self-improvement loop — the desk proposing its own upgrades (2026-07-15)

`psx-desk-product-scout` (weekly, Sun ~12:00 PKT, one cheap agent session) reads the live product + the
accuracy signals above and writes a **ranked backlog** to `state/product_backlog.json` across three
categories — **accuracy** (grounded in provenance-lint/qa findings), **clarity** (presentation), and
**feature** (new capability). It **proposes and ranks only — it never builds.** The owner picks items to
implement; implementation runs on demand through the normal gated path. This split (cheap looped ideation,
human-gated build) is the guardrail: it keeps the "improve ourselves" loop from becoming a token bonfire or
shipping machine-written features with no human in the loop. `score = impact(3/2/1) / effort(3/2/1)`, higher
first. Out of scope by rule: live per-visitor agent runs (impossible on static hosting) and any recurring
heavy-token feature.

---

## 3d. The astro pillar — how a differentiator stays honest (2026-07-17)

The desk runs a **Vedic (sidereal) astrology lens**. It exists only because it is **falsifiable**, and it
is built so it cannot quietly become a horoscope. Four layers, and the order matters:

| Layer | File | What it is | Cost |
|---|---|---|---|
| 1. Sky | `scripts/astro_engine.py` → `state/astro.json` | Where the nine grahas ARE + 90 days of dated events (ingress / station / conjunction / lunation / eclipse), each with a fixed 1–5 importance | free, pure math |
| 1b. Past sky | `scripts/astro_history.py` → `state/astro_history.json` | Daily sidereal positions 2007→today, **cached** | free, incremental |
| 2. Claims | `state/astro_map.json` | What tradition CLAIMS (sector significators, dignities). **Hypotheses, not evidence** | one-off |
| 2b. Falsification | `scripts/astro_backtest.py` → `state/astro_backtest.json` | Does any of it hold on 19y of PSX? | free |
| 3. Lens | `.claude/agents/room-astro.md` | Writes the read — **may only assert what survived** | ~1 cheap agent/week |

**The rules that keep it honest — do not soften these:**

1. **Dates are computed, never recalled.** CLAUDE.md Rule 2 with teeth. During the build, the model's own
   memory placed Rahu in the wrong sign, PSX's sector codes in the wrong sectors, and would have
   hardcoded a wrong ayanamsa. The computation was right every time. **No agent may state a transit date.**
2. **The ayanamsa is derived, not hardcoded** — Spica precessed from J2000 (Chitrapaksha definition),
   published in the JSON so it can be audited. `provenance_lint.py` fails the publish if it leaves the
   sane Lahiri band, if a graha goes missing, or if Rahu and Ketu stop being 180° apart.
3. **No natal charts for companies, ever.** PSX publishes no listing dates. A birth chart from a guessed
   date is invented input. Per-ticker astro = its sector's significators tested on its own history.
4. **`astro_map.json` is frozen on approval** (Rule 8 discipline). Changing a mapping = a v2 file with
   fresh tests, never an in-place edit — or every past astro score silently changes meaning.
5. **Astro never touches a trade.** No setups, no sizing, no gating. Strategist / Risk / Auditor never
   read it. It is a lens the desk reports and scores.
6. **Every read is a dated claim in `claims.json`** (`source_type: "astro"`), resolved against real prices
   and published on the Scores board — hits *and* misses, with the reason each worked or failed.
7. **"Nothing survived" is a publishable result**, not a failure. If the backtest kills a claim, the lens
   says the transit is happening and has no demonstrated effect, and stops there.

**Statistics (the integrity of the whole pillar — read before touching `astro_backtest.py`):**
- **Circular-shift permutation**, not day shuffling: returns are autocorrelated and astro windows are
  contiguous blocks. Shuffling days would manufacture significance.
- **Two-stage resampling.** A permutation p can't go below 1/(N+1). With ~350 hypotheses the Bonferroni
  bar is ~1.4e-4, so a 2,000-shift test could **never** reach it — "zero survivors" would have been an
  artefact of the method. Screen at 2,000; re-test anything at p≤0.01 with 50,000 (floor 2e-5).
- **Every graha is tested against every sector** — the only fair way to let the data pick a significator
  rather than the author. That means hundreds of hypotheses, so the Bonferroni bar is computed from the
  real test count and published alongside the expected number of false positives.
- **Known conservatism:** periodic masks re-align under rotation, so the test is biased *against* finding
  astro effects (verified: a planted +0.40%/day scored p=7.6e-4, not the 2e-5 floor). A null result is
  **"not demonstrated", never "disproved"**. Read effect sizes, not just p-values.

---

## 4. The seven app scheduled tasks (`~/.claude/scheduled-tasks/`)

Only run while the Claude app is open; catch up on next open. The 5 data/agent tasks each end with
`publish.py` + watchdog. The cloud cron now keeps DATA fresh 24/7, so these are primarily about the
**agent** work — but they still run `run_cloud.py` first (cheap, idempotent) as a local-freshness prereq
and a cloud-outage fallback.

| Task | When (PKT) | Does |
|---|---|---|
| `psx-desk-checkpoint-am` | **weekday 11:00** | data + **news-sentinel** + position **monitor**; escalates to full commentary only on impact ≥ 4 news |
| `psx-desk-checkpoint-pm` | **weekday 17:00** | same flow as above — see §4a |
| `psx-desk-daily-refresh` | weekday ~17:20 | macro + market-analyst **daily read** (≤120 words) |
| `psx-desk-room-loop` | weekday ~17:47 | the **Desk Room debates** — ≤3 full/day (budget gate), rest reaffirm free; QA + scoring |
| `psx-desk-weekly-harvest` | Sat ~11:00 | broker **calls** from the business press (Profit/Dawn/Mettis) + filings refresh |
| `psx-desk-code-review` | Sat ~12:00 | **Code QA** — see §3a. Not a data task; touches code only, never `state/`. |
| `psx-desk-product-scout` | Sun ~12:00 | **Self-improvement** — see §3c. Writes the ranked backlog; proposes only, never builds. |

Manual refresh (any session, no waiting for a task): the **`update-live-desk`** skill, or directly
`python scripts/run_cloud.py` (free data) then `python scripts/publish.py "..."`.

### 4a. Two fixed daily checkpoints, not hourly (changed 2026-07-14, simplified same day)

The intraday task no longer runs hourly — it fires exactly **twice a day, every weekday: 11:00 and 17:00
PKT**, for token efficiency (cut from ~8 runs/day to 2). An earlier version tried to align these to Mon–Thu
vs Friday's different market hours (open/break/close), which needed 3 separate tasks since one cron
expression can't hold multiple distinct (hour, minute) pairs — the owner simplified this to one uniform
time pair across all weekdays, which collapses cleanly to **2 tasks**: `psx-desk-checkpoint-am` (cron
`0 11 * * 1-5`) is the single source of truth for the whole flow; `psx-desk-checkpoint-pm` (cron
`0 17 * * 1-5`) is a thin pointer whose prompt just says "read and execute psx-desk-checkpoint-am/SKILL.md
verbatim". **To change checkpoint behavior, edit only `psx-desk-checkpoint-am/SKILL.md`.** Note: the
scheduler's human-readable `schedule` summary string has shown bugs on multi-value hour fields in the past
— trust `cronExpression` and `nextRunAt` from `list_scheduled_tasks`, not the summary text.

---

## 5. The cloud workflow — editing gotcha

`.github/workflows/desk-data.yml` runs the deterministic pipeline in the cloud.
**You cannot push changes to `.github/workflows/*` from this environment** — the git credential and `gh`
here lack GitHub's `workflow` OAuth scope. To add/edit it, use the **GitHub web UI** (repo → Actions →
edit the workflow → commit), or have the owner grant the scope. After a web edit, `git pull` to sync local.
Also ensure repo **Settings → Actions → General → Workflow permissions = Read and write** (so the job can
push refreshed data).

---

## 6. Hosting & data ownership

- **Vercel** serves the static site from committed files (`vercel.json` copies `dashboard/*` + `state/`
  into `public/`). Push to `main` = deploy. `Cache-Control: must-revalidate` is set, so users get fresh
  JS/CSS after each deploy (no stale-cache class on live; the local `serve.py` preview DOES cache — hard-
  reload it when testing).
- **Supabase** = auth + per-user data ONLY (never serves research data). Per-user, row-level-secured on
  the `profiles` table: `watchlist`, `notes`, `portfolio`, `followed_brokers`, `digest_prefs` (all jsonb).
  The client uses the publishable key (safe); the legacy service_role/anon keys are disabled.
- **Repo is private.** State data (incl. `history/`, `history_deep/`, `intraday/`) is committed so Vercel
  is self-contained.

---

## 7. Universe coverage — what tickers the desk tracks

`config/desk.json.universe` controls this. **As of 2026-07-19 the desk covers the WHOLE listed market
in two tiers — 554 symbols total.** `state/universe.json` writes a `tier` onto every symbol:

| tier | who | count | gets |
|---|---|---|---|
| `core` | KSE100 (top-N by weight) + full KMI30 | ~103 | the full pipeline — deep history, backtests, fundamentals, model fair value, signals, Desk Room debates |
| `listed` | every remaining **KSE All Share (ALLSHR)** constituent | ~451 | prices, quant measures, sector, dividends, a real searchable page — but *not* the expensive per-ticker analysis |

**Why two tiers:** covering only KSE100+KMI30 meant a genuine listed company (BBFL was the reported
case) did not exist in the product at all — search found nothing and there was no page to land on.
For a product users expect to be complete, an unsearchable listed company is a bug. But running 70
strategies × 19 years, plus a Yahoo deep-history pull and a fundamentals scrape, across 554 names is
not affordable per cycle. So: everything is *visible*, the core is *researched*, and the ticker page
says which it is (`coverageNote` in `pageTicker`) rather than letting empty sections imply the desk
looked and found nothing.

### 7a. The two gates — research vs signal (do not conflate them)

Tier is no longer what decides who gets analysed. **`state/liquidity.json` is**, via two
deliberately separate gates:

| gate | config | what it decides | count today |
|---|---|---|---|
| **research** | `liquidity.research_min_adtv_pkr` (5M) + `research_min_bars` (500) | what the desk *analyses* — backtests, fundamentals, predictability | 208 (core ∪ promoted listed) |
| **signal** | `risk.min_avg_daily_traded_value_pkr` (30M) | what the desk will ever *publish a setup on* | 100 |

They are different questions and must stay separate. A name can be fully researched and still
never produce a setup — that is the intended outcome for a thin stock, and the ticker page says
so out loud ("No setups will be published on this name") instead of showing an empty signal
section that reads as "the desk looked and found nothing".

Note the signal gate already excludes **38 of the ~103 core names** — index membership is not
liquidity. IBFL is the worked example: a core-tier constituent with a **median turnover of
~98,000 PKR/day**, where a single full position would be 82% of a normal day's entire volume.

**Per-symbol friction is the reason this matters.** `backtest.py` charges each name
`max(config friction floor, estimated round-trip spread)` from `liquidity.json`, not a flat
0.6%. A constant cost assumption flatters exactly the wrong names — Lesmond, Schill & Zhou
(2004) showed the stocks producing the largest momentum returns are the same stocks that cost
the most to trade, and most of this library is breakout/momentum. Switching this on removed
**64 of 591** previously "eligible" strategy-ticker pairs. Those were artefacts, not edges.

**If you add a per-ticker script, decide its gate explicitly.** Cheap pure-math scripts
(`quant.py`, `snapshot.py`, `compute_fairvalue.py`, `build_signals.py`, `data_health.py`,
`liquidity.py`) run across ALL symbols. Anything that hits the network per ticker, or is heavy
compute, MUST call the ONE shared helper — `psx_data.research_symbols()`. Do not hand-roll a
`tier == "core"` filter: three scripts each carried their own copy, so the rule could not be
changed in one place and a missed copy would silently analyse a different set than its peers.
`research_symbols()` fails CLOSED to core-only if `liquidity.json` is missing.

Already gated: `backtest`, `fetch_fundamentals`, `predictability`. Still core-only by tier
(genuinely core-specific, not liquidity questions): `fetch_deep_history`, `fetch_intraday`,
`astro_charts`. Rotation-bounded: `fetch_history` (`LISTED_PER_RUN=90`) and `fetch_dividends`
(`LISTED_DIV_PER_RUN=60`) — core refreshes every run and the long tail rotates stalest-first,
so a 554-symbol universe cannot outrun the 30-minute cron.

**Ordering constraint:** `liquidity.py` MUST run after both history fetches and before
`fetch_fundamentals` / `predictability` / `backtest` (it is placed accordingly in
`run_cloud.py`). Out of order, the gate silently falls back to core-only and the backtest
reverts to flat friction — no error, just quietly worse numbers.

`fetch_fundamentals` is threaded (6 workers): it is latency-bound, and serial it took ~10 min
at this universe size, which alone would blow the Actions budget. 208 names now take ~29s.

If a ticker a user searches for still doesn't appear, check `state/universe.json.symbols` first (is
it there?), then `config/desk.json.universe` (`cover_all_listed` still true? `kse100_top_n` capped?)
— don't assume it's a search bug.

**Cost note:** the deterministic layer (prices/quant/backtests) is free regardless of universe size —
more tickers just means more (free) compute time. Only the Desk Room **debates** are token-budgeted
(`deep_dives_per_day` in the Room config), and that budget is independent of universe size — a bigger
universe means the coverage queue is longer, not that any single cycle spends more tokens.

**Backfill note:** widening the universe requires a one-time full run of `run_cloud.py` (fetches history/
deep-history/fundamentals for the newly-added tickers — subsequent runs are fast again since
`fetch_deep_history.py` only pulls missing tickers). If done via the cloud cron, the first run may run
long; the 15-min timeout in `desk-data.yml` may need raising to ~25 min for that one run (web-UI edit
required — see §5). Preflight/publish gating means a timeout never publishes broken state either way —
worst case the backfill just continues on the next scheduled run.

---

## 8. Known gaps / honest notes

- **Sector concentration** in the portfolio tracker is by POSITION, not sector — the feed only has numeric
  sector codes (e.g. `0809`), no names. Building a code→name map would enable true sector grouping.
- **Digest email SENDING** is not wired (prefs are captured in `digest_prefs`). Needs an email provider
  (e.g. Resend) + a scheduled loop. On hold per owner.
- **Legal pages** (`state/legal.json`, `#/legal/*`) are DRAFTS — a Pakistani lawyer must review before
  charging (flagged in the file's `review_status`). Discoverable from: page footer, the sidebar bottom
  (`.side-legal`), the sign-in/sign-up modal (`.auth-legal`), and the Settings page.
- **Track record** is young (see the clock on the Scores page). Do not switch on paid billing until it
  matures — that clock is the honest gate.

---

## 9. Fixed bug class — `hidden` attribute silently overridden by CSS

The account-menu dropdown never actually closed (2026-07-14): `menu.hidden = true` was set correctly in
JS, but `.acct-menu{display:flex}` (an author-stylesheet class rule) unconditionally overrode the
browser's native `[hidden]{display:none}` default — author-origin CSS always wins over the UA default,
regardless of selector specificity. The element was visually always-open from the moment it was first
rendered; the JS toggle was a no-op the whole time. Proven with `getComputedStyle(el).display` while
`el.hidden = true`. Fixed with an explicit `.acct-menu[hidden]{display:none!important}` override — the
same pattern already used for `.searchbox[hidden]`.

**Rule going forward: any element toggled via the `hidden` DOM property MUST have a matching
`.class[hidden]{display:none!important}` CSS rule**, or the toggle silently does nothing. Checked
2026-07-14: only two such elements exist (`#searchbox`, `#acctMenu`), both now correctly overridden.

---

## 10. If the live site looks wrong — triage order

1. `python scripts/watchdog.py` — is it stale, degraded, or serving empty? It tells you which.
2. If **degraded**: read `state/health.json.problems`. A `tv_crosscheck ERROR` = a real data glitch;
   `drift` in `advisories` = benign TV lag (ignore).
3. If **stale** (`updated` old): a deploy didn't propagate or no cycle ran — run `run_cloud.py` +
   `publish.py`, or trigger the cloud workflow (Actions → Run workflow).
4. If a **single ticker** is blank: check `state/history/<SYM>.json` exists and is non-empty; preflight
   should have caught a broad gap. The client self-heals transient misses (retry button/auto-retry) — a
   one-off "couldn't load" that clears on retry is normal transient behavior, not a data bug.
4b. If a user reports **every ticker / all pages** blank at once, but `curl`ing the live state files and
   `watchdog.py` both show healthy 200s with real data: this is almost always CLIENT-side — either (a) a
   browser extension (ad/anti-fraud blocker) monkey-patching `window.fetch` and throwing on same-origin
   requests (the reason `j()` in app.js has an XHR fallback), or (b) the user was on the page during the
   ~60s Vercel deploy-propagation window right after a publish. Verify server-side health FIRST (curl the
   state files + `watchdog.py`) before assuming a data bug — don't guess from a screenshot alone. Ask the
   user to hard-refresh or try a different browser/incognito if it's reproducible.
5. If a ticker can't be **found in search**: see §7 — check it's actually a tracked constituent before
   assuming a search bug.
6. Never fix by hand-pushing — fix the data, run `publish.py`, let the gates pass.
7. **Whenever you change something structural** (universe size, a config default, a new per-user table, a
   new loop) — update this file (`docs/OPERATIONS.md`) and, if it affects a scheduled task's behavior, that
   task's `SKILL.md` in the same turn. Docs going stale is how future sessions break things they don't
   know changed.
