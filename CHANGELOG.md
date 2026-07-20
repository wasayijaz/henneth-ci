# Henneth — Changelog

Newest first. Every entry = what changed, why, and (for bugs) how it's prevented from recurring.
The desk is a **live website** — nothing ships unless `python scripts/preflight.py` exits 0.

---

## 2026-07-19 — Three-plan product, the Investor desk, and entitlement enforcement

Turned the single-tenant desk into a three-audience product. **Nothing here is billed** — card
processing via international providers is unavailable in Pakistan, so a local gateway comes later.

### Plans
- `Free → Investor → Pro → Broker` (`PLANS` / `PLAN_ORDER` in app.js). The paid entry tier is
  **Investor**, not "Learner" — a tier named for what the customer lacks is a label on the customer.
  DB migration `rename_learner_plan_to_investor` moved the stored value and the CHECK constraint.
- Broker renders **"coming soon"** (disabled CTA) — the plan is defined, the product is not built.
- Plan cards show an **Upgrade CTA** for any tier above yours. `on` is evaluated before `soon`, so
  your own plan never reads "Coming soon". `notifyUpgrade()` records interest instead of faking a
  checkout that does not exist.
- `#/plans` carries an **owner-only preview-as-plan** switch: re-renders the entire product as any
  tier without touching the stored plan (in-memory, reload resets). `hasFeature`/`isSubscribed`
  honour the preview even though `BILLING_LIVE` is false, or preview would be meaningless.

### Entitlement security — a self-promotion hole found and closed
`profiles.plan` is guarded by a CHECK constraint plus **two** triggers. The first migration added a
`BEFORE UPDATE` trigger only. That was insufficient: the client writes profiles via **upsert**, so a
crafted INSERT could have set `plan='pro'` and self-granted a paid tier. Migration
`freeze_plan_on_insert_too` adds a `BEFORE INSERT` trigger forcing `plan='free'` for role
`authenticated`. Plan changes are now a service-role-only path.
`ui_mode` is intentionally left client-writable — it is a view preference, not an entitlement.
`BILLING_LIVE = false` remains the single switch; while false any signed-in account reads as
subscribed, so shipping paywalls could not strip access from accounts that already had it.

### The Investor desk (`#/learn`)
- 4 levels that **unlock in order**, 17 lessons, played **one card per screen** in a focused player.
  A long scroller with quizzes was the first attempt and was rejected as a poor experience.
- Card kinds are visually unmistakable and namespaced `k-*`: lesson · watch out · the point ·
  interactive · check yourself.
- New **Level 2, "The documents"**: the full map of what a Pakistani listed company publishes, the
  annual report, all three financial statements, the auditor's report + pattern of shareholding +
  related-party transactions, and announcements/AGM/material information.
- **Interactive labelled statements** (`anatomies` in `state/curriculum.json`): tap any line for what
  it is and what to watch. **Rule 2 compliance:** `fundamentals.json` holds revenue/net income/EPS but
  not gross profit, opex or finance cost — so real figures appear **only** on the lines the desk
  actually holds (anchored to a real named company), and every other line reads *"in the filing"*.
  No statement line is fabricated to make the lesson look complete.
- Plus a 12-document tap-to-learn map and a dividend-date timeline highlighting the ex-date.

### Two bugs introduced during this build, caught before/at verification
1. **Async render race.** `renderPlayer()` awaited the anchor fetch mid-render, letting a second
   render interleave and leaving 3 stale `.anatomy` nodes; clicks bound to a detached copy silently
   did nothing. Fix: fetch the anchor once in `openLesson`, keep `renderPlayer` synchronous.
   *Prevention:* never await inside a function that fully rewrites its own container.
2. **Class-name collision.** The card wrapper took `class="pl-card ${c.type}"`, so a card of type
   `anatomy` matched the `.anatomy` **component** selector and inherited its border. Card kinds are
   now namespaced `k-*`. *Prevention:* never use a raw data-driven type string as a CSS class.

Also: the sidebar was regrouped (Today/Board · You · Edge · Market), the account menu rebuilt to show
the plan you are on, and search widened from a 34 px icon to a labelled 230 px field (collapses back
to an icon under 1100 px; palette behaviour unchanged).

---

## 2026-07-18 — Personal astrology pillar, its funnel, and the daily sky

A Vedic (sidereal) astrology layer shipped as **exploration, never an edge claim** — because the desk
tested it and it failed.

### The test result that frames the whole pillar
- `astro_backtest.py`: 2,589 hypotheses across 101 subjects (99 stocks + KSE100 + KMI30) → **0 survivors**
  after Bonferroni and FDR. Expected ~129.5 false positives at p<0.05; 143 came back.
- `astro_natal_test.py`: 379 natal-method hypotheses, 27 verified company birth charts → **0 survivors**.
  Published with an explicit power caveat: young charts make this test weakly powered, so the finding is
  **"not demonstrated", not "disproved"** — the desk does not claim a verdict it has not earned.
- The honest foil: `sector_macro.py` ran the *same* machinery on ordinary macro factors and found
  **17 Bonferroni / 34 FDR survivors of 98** (oil→E&P at p=2e-5, joint R² ≤2.6%). Same bar, real result.

Two methodology bugs were found and fixed **in our own test harness** before trusting any of it:
- **A self-rigging backtest.** A 2,000-shift permutation can never produce a p below 1/(N+1), so it
  could not reach a ~1.4e-4 Bonferroni bar — "zero survivors" was guaranteed by the method rather than
  by the data. Fixed with two-stage resampling (2,000 screen → 50,000/200,000 fine).
- **A false discovery.** Raw returns surfaced 2 survivors at p=5e-6 on PIOC. Both were **beta**:
  market −0.119%/day, cement −0.238%, PIOC β=1.243 → −0.430%. Market-adjusting returns
  (`r − β·r_mkt`) moved p from 5.0e-6 to 1.29e-3. Two further bugs inside the replication check were
  fixed at the same time.

### The feature
- Browser-side natal chart from a committed 552 KB packed ephemeris (1950–2035, daily, `<9H`).
  Ascendant computed live from LST + latitude, validated against the sunrise anchor.
- Classical synastry against every PSX name (Tara koota, Moon-lord friendship, benefic placement,
  dasha resonance); chartless names (pre-2000 listings) read through the sector significator.
- Vimshottari dasha + antardasha, an isometric-feel natal orrery, per-stock timing windows,
  8 commodities read through traditional rulers, and goal-tailored *language* (never maths).
- **The daily layer** (the actual subscription rationale, since a natal chart never changes): gochara
  placed from the natal Moon and recomputed daily, a transit ring on the orrery, and dated
  "worth another look" shifts. All client-side over data already shipped — zero marginal cost per user.
- `astro_claims.py` files dated **market-relative** claims with a stamped benchmark level and grades
  them on the public scorecard. `fetch_indices.py` was added because grading market-relative claims
  against an absolute price would have scored a stock falling 2% in an 8%-down market as a **hit**.

### The funnel
Casting a chart requires **no account** — it is client-side maths over an ephemeris the browser
already fetches, so the prior sign-in wall was artificial. Guests cast free into `localStorage`;
`migrateGuestChart()` lifts the chart into the profile on sign-in so birth details are never entered
twice. Free tier sees the real chart plus the 3 strongest matches, then one shared `planWall()`.

### A silent bug this uncovered (was live, affected every user)
`computeNatal()` read `timeKnown` while the wizard and the Supabase column both use `time_known`.
The value was therefore always `undefined`, so **no user ever received a rising sign** — every chart
silently fell back to Chandra lagna however exact the birth time given, and the ascendant ray in the
orrery was dead code. Fixed by normalising `bd.timeKnown ?? bd.time_known ?? false`.
*Prevention:* the snake_case DB column is the source of truth; accept both spellings at the boundary.

### Editorial: the 4th wall
On owner instruction, all readings stopped narrating the platform's own mechanics and limits
("so it isn't invented", "the desk tested astrology and found no edge", source citations). Readings
now lead with the Moon (Chandra lagna is a real technique, presented confidently). The null result is
**not hidden** — it remains in this changelog, in the README, and in the Investor desk's astrology
lesson, which teaches the tradition and the test result together. It is simply no longer narrated
inside an individual reading.

---

## 2026-07-12 — Ticker pages blank in real Chrome (extension breaking fetch)

Wasay reported "no data" on every individual ticker, on both live and preview, in his actual
Chrome (not reproducible in the sandboxed browser pane). Diagnosed directly in his real Chrome
session via console + network inspection.

**Root cause:** a Chrome extension (id `hoklmmgfnpapgjgcpechhaamimifchmp`, script `frame_ant.js` —
an ad/anti-fraud blocker) monkey-patches `window.fetch` and intermittently throws
`TypeError: Failed to fetch` on the dashboard's own same-origin `state/*.json` requests. Not a
code bug — same behavior on preview and live because it's the same browser.

**Fix:** `j()` in app.js now retries with backoff, and its **last attempt uses `XMLHttpRequest`**
instead of `fetch` — extensions that patch `fetch` don't intercept XHR the same way. Verified
live in Wasay's actual Chrome with the extension still active: `#/ticker/FFC` and `#/ticker/HUBC`
both went from "No data" to fully rendering on reload.

Also: user-facing fix is to disable/allowlist that extension for localhost + the live domain —
recommended to Wasay directly, not something code can fully route around if the extension also
blocks XHR on a given page (it didn't here, but could).

---

## 2026-07-12 — Educational + compliance layer on ticker & value pages

Reworked the company (ticker) page toward investor education and away from anything that
reads like advice — aligns with desk hard-rule #5 (no advice language) and reduces trust/
compliance risk for inexperienced users. All new content is derived from the data layer;
nothing is fabricated.

### Added (ticker page)
- **Prominent disclaimer banner** at the top (not hidden in a footer): educational/informational
  only, not personalized advice, past performance ≠ future results, PSX carries risk of capital loss.
- **Data-provenance line** under the header: currency (PKR), source + whether intraday (DPS) or
  end-of-day close, quant/fundamentals timestamps, and that the long chart is split/bonus-adjusted
  (Yahoo) while the DPS close is unadjusted. Inline `low liquidity` / `earnings negative` flags.
- **"What the data flags"** — auto-derived pros/cons ("what could go right / wrong") from real
  signals only (proven strategies, fair-value gap, forward vs trailing P/E, covered yield, beta,
  payout stretch, volatility rank, liquidity, peer valuation, max drawdown, lossmaking). Framed as
  factual observations, explicitly "not predictions, not advice; absence of a flag is not a green light."
- **"Questions to ask before buying"** — 7-item checklist answered from data where the desk has it
  (profit/growth via forward-vs-trailing P/E, cash-generation proxy with caveat, valuation vs peers,
  dividend sustainability via payout ratio + history, "can you tolerate a 30–50% fall" via real max
  drawdown, time horizon) and **honest where it doesn't** (debt: "not in feed — open the balance sheet").
- **Risk profile panel** — risk beyond volatility: price volatility, maximum historical decline,
  liquidity, market sensitivity (beta), valuation, dividend reliability — each with a plain-language
  read and a low/moderate/high chip. Debt & earnings-stability shown as **"not scored"** (no data) —
  honest, not faked. Header teaches "a low rupee price does not mean a stock is cheap."

### Changed — softened advice-flavored language (ticker + value pages)
- Fair-value verdict `undervalued/overvalued` → **"below / above model fair value"** everywhere
  (ticker section heading "Fair value model", pills, value-screen headings + row pills + expand note).
- Business scorecard rating `attractive/caution/neutral` → **"stronger / weaker / mixed scorecard"**.
- Value screen: removed "looks cheap / looks rich"; added the disclaimer banner; headings now
  "Priced below/above model fair value". Verified: **no advice words** (`undervalued`, `looks cheap`,
  `strong buy`, `guaranteed`, etc.) anywhere on either page.

### Fixed — misleading edge cases
- **Negative earnings → P/E** now shows **"n/a · earnings negative"** instead of a misleading `0`/`n/a`
  string (verified on TRG, EPS −8.82: P/E cell reads "n/a · earnings negative", cons list "fallen 93%
  peak-to-trough" + "currently lossmaking", checklist Q1 flags the loss).
- **Illiquid names** flagged in provenance + risk panel (verified PSEL 0.4M/day → low liquidity).

### Not built (no data — deliberately not faked)
- Company description ("what does this company do") and revenue/earnings/debt/cash-flow **trend charts**
  need data not in the feed (fundamentals is a single current snapshot; sector is stored as a numeric
  code, not a name). Flagged for a future scraper add rather than fabricated.

---

## 2026-07-12 — Value working, contrast, empty-state honesty, deploy guard

### Fixed
- **Board RSI / 20d columns went blank ("—") intermittently.**
  Root cause: `j()` (data fetcher in `app.js`) cached `null` on *any* transient fetch
  miss for 25s, so one hiccup loading `quant.json` blanked every RSI/20d/heat cell that
  reads from it. Fix: retry once, **never cache a failure**, fall back to last-known-good.
  Prevented by: `preflight.py` asserts `quant.json` has ≥20 tickers each carrying
  `rsi14`/`ret_20d`/`close` before any deploy.
- **Value tab hid its working.** The four valuation models existed in `fairvalue.json`
  (`relative_pe`, `earnings_power`, `graham`, `ddm`, median → `composite_fair`) but the
  screen only showed price/fair/verdict. Now each row expands inline to show all four
  models, price-vs-each %, the median derivation, the inputs (EPS, P/E, growth), and a
  plain-English why. Prevented from regressing: `preflight.py` requires every fair-value
  ticker to carry a non-empty `methods` object.
- **Light-grey text unreadable.** The `gemini` theme's `.sub` never set `opacity`, so the
  base `.sub{opacity:.55}` washed `--ink2` out. Fix: `.sub{opacity:1}`, darkened
  `--ink2` (#565650→#4a4a44) and `--ink3` (#8a8a80→#6b6b63) for real contrast.
- **Macro "Pakistan macro" showed a big empty grey block + four "—" cells.**
  Two causes: (1) `.facts` used CSS grid `auto-fill`, which reserves phantom empty tracks
  (the grey block) → changed to `auto-fit` which collapses them; (2) FX reserves / 6m
  T-bill / 10y PIB / remittances aren't in `macro.json` yet → now we render only populated
  facts and print an honest "pending this cycle" note instead of dead "—" cells.
- **Dividends "Upcoming" looked broken when empty.** It's legitimately empty off-season
  (PSX payouts cluster Jul–Aug; the desk never guesses a date). Rewrote the empty state to
  say so and point at the trailing payouts already listed below.

### Added
- **`scripts/preflight.py`** — deterministic pre-deploy guard. Re-reads every state file
  the dashboard consumes and asserts the exact shape the UI joins on (tickers present,
  fields non-null, no NaN/Infinity that would break `JSON.parse`). Exit 1 = do not deploy.
  Wired as the **last step of `build_dashboard.py`** (which the GitHub Actions workflow
  runs under `set -e`), so a structurally broken cycle aborts the job and the last-good
  live site stays up. Also the final step of `run_cloud.py`. Verified: empty `quant.json`
  → exit 1; healthy state → exit 0.

### Earlier this session (UI reskin — see git log)
- Option A light-terminal theme across all tabs; ticker-tape marquee autoscroll (pauses on
  hover); board regrouped into 3 filled columns (killed right-side dead space); search
  overlay close bug; mobile header horizontal-scroll fix; local preview loop
  (`preview.bat` → `scripts/serve.py`, serves local `state/`, nothing hits the cloud).

---

## How to not break the live site
1. Iterate locally: `preview.bat` (or `python scripts/serve.py`) → http://localhost:8877/dashboard/
2. Before any push: `python scripts/run_cloud.py` (or at minimum `python scripts/preflight.py`) must exit 0.
3. Push a batch, not every edit. CI re-runs the pipeline + preflight; a bad data cycle can no longer publish.
