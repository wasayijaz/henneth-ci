# PSX Trade Desk — Changelog

Newest first. Every entry = what changed, why, and (for bugs) how it's prevented from recurring.
The desk is a **live website** — nothing ships unless `python scripts/preflight.py` exits 0.

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
