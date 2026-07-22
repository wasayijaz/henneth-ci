# Publication Restructure — implementation handoff

**Status:** planning doc, not yet implemented.
**Owner decision date:** 2026-07-22.
**Revised 2026-07-22 after a pass against the actual code.** Five instructions were wrong or
incomplete: §2's X-ray row, §4 (already compliant in code — the copy is the violation), §5 (turning
natal off disarms the watchdog's public probe), §6b (the performance headlines it says to strip do
not exist), and §7 (US coverage is a trade, not a pure defence). Each correction is marked
**VERIFIED** or **CORRECTED** in place, with the file and line that settles it.

> **Not legal advice.** Drafted without a lawyer. This changes the product's shape to match
> what `state/legal.json` already claims. It reduces exposure; it does not eliminate it.
> An SECP written query and a lawyer review are still on the list (§8).

---

## 1. Why

The desk currently reads as an **advisory service**: named analysts issuing conviction-rated
calls with entry/stop/target and position sizes computed against a capital figure.

It should read as a **publication**: scheduled, impersonal market research that anyone can
subscribe to and that is identical for every subscriber.

Same content, mostly. Different frame. The publication frame is defensible in a way the
advisory frame is not — most importantly in the US/global regime, which is the real argument
for widening coverage beyond PSX.

### The three tests

Every published surface must pass all three:

1. **Scheduled** — ships on a fixed calendar, not on demand or per-user request.
2. **Impersonal** — byte-identical output for every subscriber. The desk does not know the reader.
3. **General circulation** — open subscription, not a client relationship.

`state/daily_read.json` already passes all three. It is the reference model.

---

## 2. Surface map

| Surface | Verdict | Action |
|---|---|---|
| `daily_read` | Flagship | None. Lead the product with it. |
| `quant`, `predictability`, `sectors`, `liquidity`, `correlation` | Keep | Impersonal data layer. |
| `backtests`, `strategy_library` | Keep | Rules 8/9 make these reproducible and defensible. |
| `dividends`, `earnings_calendar`, `fundamentals` | Keep | Reference data. |
| `rooms` (Desk Room) | Keep, reframe | Must be scheduled + impersonal. See §4. |
| `broker_scorecard`, `claims`, `leaderboard` | Keep as journalism | Public calls only, published methodology. |
| `signals.active` levels | Keep as commentary | Levels stay. **Sizing goes.** See §3. |
| Position sizing vs. configured capital | **Cut from output** | Becomes user-driven calculator. §3. |
| `positions` (desk's own) | Keep | Relabel as the desk's model portfolio. |
| User portfolio tracking | Keep | Arithmetic over the user's own holdings is tracking, not advice. |
| Portfolio X-ray — the per-holding prose | Cut the narrative only | **CORRECTED — see §2a.** |

### 2a. Portfolio X-ray — CORRECTED

The original row said "User portfolio + commentary on it → Cut commentary". Too blunt, and it did
not note that the surface is **sold**: `dashboard/app.js:6219` gates it behind `hasFeature("xray")`
and `site.config.ts` lists "portfolio X-ray" in the Pro ladder. Cutting it wholesale removes a
priced feature.

Reading `app.js:6222-6261`, it splits cleanly:

| Half | Verdict |
|---|---|
| Weighted beta, blended yield, expected dividends from real trailing payouts, value-weighted gap vs model fair value | **Keep** — arithmetic over the user's own holdings, i.e. tracking |
| The `why` strings (`app.js:6243-6250`) — e.g. *"FFC is 34% of the portfolio… one company's bad quarter sets the whole result"* | **Cut or neutralise** — generated prose interpreting their specific mix |

The framing is already careful — `app.js:6254` reads *"These are the constraints the desk imposes
on itself… Not instructions, and not a suggestion to trade."* The three checks are literal Rule 4
restatements, not opinions about their stocks.

**Action:** neutralise the `why` generators to state the rule and the user's value without
interpreting it. Keep the tiles, keep the rule restatements, keep the plan feature.
| `astro`, `astro_regime`, `astro_backtest` | Keep | Strongest astro. Impersonal, dated, scored. |
| `astro_natal`, synastry, personal gochara | **Cut from launch** | Personalized. Breaks the publication frame outright. |

---

## 3. Position sizing — remove from published output

**Problem:** `scripts/build_signals.py` computes share counts against `capital_pkr` from
`config/desk.json` and emits them.

**VERIFIED** against the file — these references are accurate.

- `scripts/build_signals.py:34` — reads `cfg["capital_pkr"]`
- `scripts/build_signals.py:74-80` — computes `risk_budget`, `shares`, `size_pkr`
- `scripts/build_signals.py:89` — emits `size_shares`, `size_pkr`

**One trap.** `build_signals.py:77-79` uses `shares <= 0` as the guard that rejects a setup whose
stop is too wide for the risk budget — an invalid setup under Rule 4. That check must SURVIVE the
strip. Delete the computation rather than just the output fields and invalid setups start
publishing. Keep computing; stop emitting.

**Why it matters:** a share count against a capital figure is the single most advisory-looking
output in the product. It is the difference between "here is the setup" and "here is what you
should buy."

**Changes:**

1. Strip `size_shares` and `size_pkr` from any **published/subscriber-facing** payload.
   Keep them in internal state if the Auditor's re-derivation (Rule 4/7) needs them — the
   audit chain must not break.
2. Keep `entry`, `stop`, `target`, `risk_per_share` in published output. Levels are commentary.
3. Add a **client-side position size calculator** under `site/src/pages/tools/` alongside the
   existing calculators (`sip-calculator.astro`, `compound-interest-calculator.astro` are the
   pattern to follow). The user enters their own capital and risk %. Compute in the browser.
   Persist nothing server-side.
4. The calculator must use the Rule 4 formula unchanged, so the desk's published methodology
   and the user's tool agree.

**Acceptance:** no subscriber-facing surface displays a share count or PKR position value
derived from a capital figure the desk holds.

---

## 4. Desk Room — schedule and depersonalize

Named columnists debating a name, with an editor synthesizing a house view, is publication-shaped
(cf. a roundtable column). It is *not* publication-shaped if it runs on demand per user or
references a reader's holdings.

**CORRECTED — the code already passes this. The COPY is the violation.**

Point 2 below ("no per-user triggering") is already true and was already true when this doc was
written:

- `dashboard/app.js:2469` — `runDeskBar` renders only `if (hvRoom)`, i.e. only when a session
  **already exists** in `state/rooms.json`
- `playDeskReplay(sym)` replays a **pre-computed** debate and sets `sessionStorage["deskran:"+sym]`
- the queue is editorial — `room_queue.py`, `deep_dives_per_day`, driven by the `psx-desk-room-loop`
  scheduled task

Output is byte-identical for every subscriber and no user action spends a token. All three tests
pass today.

**What fails is the wording.** *"Run the desk on FFC"*, *"Run ›"*, *"Run again ›"*, and
`app.js:2475` — *"Once it finishes, the full analyst debate and house view appear right here."*
The product is publication-shaped underneath and is **advertising itself as on-demand personal
analysis**. That is precisely the advisory framing this section exists to remove, and it is
cosmetic. Same pattern on the strategy-library bar (`app.js:2477`) and the board runner
(`app.js:811-813`).

**Changes:**

1. Fix the cadence and state it publicly — e.g. "Desk Room publishes weekly, Tuesdays."
   Enforce in the scheduler, not by convention.
2. ~~No per-user triggering of a Room session.~~ **Already true.** Instead: reframe the reveal
   affordance so it stops claiming otherwise — "Read the desk's debate on FFC", "Published · date".
3. No Room output may reference a reader's positions, watchlist, or capital.
4. Add a standing masthead line to Room output: personas are the desk's research voices;
   output is impersonal and identical for all subscribers.

This is now the **cheapest** item on the list and should run first.

**Caveat to record:** this defense is materially stronger under a US/global publication framing
than under a PSX-only framing. Pakistan's Research Analysts Regulations 2015 have no publisher
carve-out equivalent. This is the actual reason to widen coverage (§7) — not to dilute SECP.

---

## 5. Personal astro — cut from launch

`astro_natal`, synastry, and per-user gochara are personalized by construction. They break the
impersonal test on their own, and they introduce sensitive personal data (birth date, time,
place) into the product.

**CORRECTED — the original "Affected" list conflated two different things and would have deleted
a core IMPERSONAL asset.** "natal" appears in both, but they are not the same feature.

`scripts/astro_natal.py` computes natal charts for **COMPANIES** — first-trade dates for the 15
listed subjects sourced by `astro_charts.py`, cast at the exchange open per the Bill Meridian
convention (`astro_natal.py:1-18`). `state/astro_natal.json` has keys `n_charts` / `subjects`, and
it feeds three impersonal surfaces in `dashboard/app.js` (`:1429` the astro board, `:1794` the
whole-market map, `:1948` the ticker astro lens).

That is scheduled, impersonal and identical for every subscriber. **It passes all three tests and
must STAY.** It is part of the astro pillar, not the personal feature.

What is actually personal is the browser-side chart casting —
`scripts/build_natal_ephemeris.py:1` states its purpose outright: *"A compact daily ephemeris table
the BROWSER can use to cast a person's birth chart… each user's birth date/time/place."*

| Cut | Keep |
|---|---|
| `scripts/build_natal_ephemeris.py` | `scripts/astro_natal.py` — company first-trade charts |
| `state/natal_ephem.json` / `.bin` | `state/astro_natal.json` |
| `#/cast` — the birth-data wizard (`app.js:1635` `BW_STEPS`, `:1698` `renderBirthCast`) | `scripts/astro_natal_test.py` — tests the company charts |
| `#/mychart` — `pageMyChart`, synastry, personal gochara | `app.js:1429`, `:1794`, `:1948` — impersonal consumers |
| birth-data intake (`app.js:3314`) | `astro`, `astro_regime`, `astro_backtest` |
| `"cast"`, `"mychart"` in `OPEN_ROUTES` (`app.js:5194`) | |
| funnel entry points: `app.js:656`, `:3509`, `:5312` | |

`scripts/run_cloud.py:35` drops `build_natal_ephemeris` only — **`astro_natal.py` stays in the
cycle.** `scripts/watchdog.py` no longer references natal at all (probe repointed, §5 step 1).

**CORRECTED — point 3 is understated, and getting it wrong disarms a live safety check.**

`scripts/watchdog.py:61`:

```python
PUBLIC_PROBE_FILE = "natal_ephem.json"
```

The natal ephemeris is the watchdog's **public-access probe** — the one file that must return 200
while every other `state/` file returns 401. It is how the account gate (OPERATIONS.md §9b) is
verified as *gating* rather than *blocking everything*, and `middleware.js` whitelists it in
`PUBLIC_FILES` for exactly that reason.

Flag natal off without repointing the probe and the gate's health check silently stops testing
anything. It will not fail loudly. It will pass, meaninglessly.

**Changes, in this order:**

1. **First:** repoint `PUBLIC_PROBE_FILE` to another genuinely public file and update
   `middleware.js`'s `PUBLIC_FILES` set to match. Re-run the §9b regression check
   (`/state/rooms.json` → 401, probe file → 200) before touching anything natal.
2. Feature-flag natal off for the launch product. Do not delete the code — this is deferral,
   not abandonment. `dashboard/app.js` carries **133** natal/mychart/cast references; a flag is a
   small diff, a deletion is a large one.
3. Remove natal surfaces from the dashboard and any marketing copy.
4. Skip natal steps in the cloud cycle (`run_cloud.py:35`); confirm `watchdog.py` still passes.
5. Keep `astro`, `astro_regime`, `astro_backtest` fully live. Impersonal astro is the pillar.

### 5a. OWNER DECISION, 2026-07-22 — §5 is NOT being implemented as written

The owner has decided to **keep** `#/cast` and `#/mychart` in the terminal, and to additionally
build a **lighter public version on the marketing site**: birth chart → elemental affinities with
sectors and commodities (cement, gold…) plus current transits, leading to sign-up for the
ticker-level reading.

**Record the trade-off plainly, because this reverses the section above.**

- The impersonal test in §1 is **not met** by this surface, by choice. `dashboard/app.js:1803-1816`
  scores **every PSX ticker** against the user's birth chart via `synastry()`, plus the eight
  commodities in `COMMODITIES` (`app.js:1177`). Output differs per reader by construction. It is
  the most personalized surface in the product — more so than the position sizing §3 removes.
- It already carries a disclaimer (`app.js:1783`): *"Astrological exploration, not investment
  advice. A lens to read your own chart against the market — never a reason to buy."*
- The marketing-site version is **softer than what already ships**, not an escalation: sector and
  commodity level rather than named tickers.
- Sensitive personal data (birth date/time/place) stays in the product. `state/legal.json` privacy
  section must cover it explicitly, and it is `review_status: DRAFT`.

**This is the one item to put in front of the lawyer first**, ahead of the §8 SECP query — it is
the surface most likely to attract the "personalized advice" reading, and the owner is choosing to
grow it rather than cut it. That is a legitimate product call; it just needs to be a *known* one.

**Acceptance (revised):** ~~no birth-data intake anywhere~~ — personal astro ships. Instead: the
disclaimer stays on every personal surface, birth data stays private to the account, and the
marketing-site version stays at sector/commodity level with no named-security reading.

---

## 6. Legal + copy

### 6a. `state/legal.json`

Already the strongest part of the stack — better drafted than the competitors reviewed
(alphagenpro.com, psxinvest.com). Amendments only:

1. **Terms §1** — recast from "educational research and analytics tool" to a **publication**:
   scheduled, impersonal, general circulation, identical for all subscribers.
2. **Add a regulatory-status section** stating the *positive basis* for sitting outside the
   licensed perimeter, then the non-registration fact. State the basis first:
   no personalized advice; no discretion or custody over funds; no execution; output is
   systematic and identical for every subscriber; published on a fixed schedule.
   (Competitors state only the bare non-registration fact. That is weaker.)
3. **Add non-affiliation** — not affiliated with, endorsed by, or connected to the Pakistan
   Stock Exchange. Needed given the name and domain context.
4. **Never use the word "recommendation"** in any sense other than negation. AlphaGen's
   disclaimer says output "are recommendations generated by the system" in §2 while §1 denies
   it — a self-inflicted contradiction. Do not reproduce it.
5. Bump `version` and the per-section `updated` dates. Keep `review_status` until a lawyer
   has actually reviewed.

### 6b. Marketing copy audit

Across `site/src/pages/**` — especially `index.astro`, `features.astro`, `plans.astro`,
`solutions/*.astro`:

**CORRECTED — the performance headlines this section says to strip do not exist.**

Grepped the marketing pages for win rate, alpha, hit rate, accuracy, outperform, beat-the-market.
**No hits.** The site already refuses the claim, in writing:

- `index.astro:361` — *"show the method, not a number — a track record you can't check isn't a
  track record"*
- `index.astro:402`, `solutions.astro:90` — publish *"Conditions with a proven edge: **0**"*, the
  astro null result, stated as zero
- `plans.astro:22` — *"there is nothing proven to charge for"*

Anyone following the original instruction would find nothing and conclude this section was already
done. It is not — the exposure is narrower and easy to miss.

**The actual exposure is one word: "proven", used as a product adjective**, in six places —
`index.astro:144` ("Proven-strategy signals"), `:219`, `:402`; `features.astro:34`, `:114`;
`solutions.astro:54`. Internally it is a defined term (cleared the backtest bar: hit rate ≥55%,
positive expectancy after costs, profitable out-of-sample). On a landing page, to a regulator or a
naive reader, it reads as a performance claim. Replace with the mechanism — "backtested",
"rule-based", "tested on the stock's own history".

- ~~Strip performance headlines — win rate, alpha, returns, hit rate.~~ **None present.** Instead:
  strip "proven" as a product adjective (six sites, listed above).
- Strip "recommendation", "buy", "sell", "call", "tip", "advice" as product language.
- No testimonials asserting returns or accuracy.
- Add the publishing schedule to the site — "the desk publishes at 08:45 PKT daily;
  Desk Room weekly." The schedule is part of the defense, so say it out loud.
- Comparison tables against tip groups / WhatsApp: fine to keep, but do not pair them with
  performance claims.

---

## 7. US / global coverage

Widen the terminal beyond PSX. The reason is positioning, not dilution: it makes
"global markets publication that covers PSX in depth" the natural description, rather than
"PSX advisory service."

Secondary benefit: impersonal astro reads far better against global indices and sectors than
against a single thin market, and `astro_backtest.json` already scores the claims.

Sequence this **after** §3–§6. Doing it first just means two regulators and neither defense earned.

### 7a. CORRECTED — this is a trade, not a pure defence

As originally written this section reads as risk-reducing. It is not, and §4's "materially stronger
under a US/global framing" compounds the impression. **Adding US coverage also makes a US regulator
relevant where one currently is not.** Possibly a better argument; definitely a second audience for
it. Record it as a trade so nobody later reads §7 as a way to lower exposure.

### 7b. Cost and scope — measured

**Data is free and needs no vendor.** `scripts/fetch_deep_history.py:33` already fetches
`query1.finance.yahoo.com/v8/finance/chart/{symbol}.KA?interval=1d&range=25y`. `.KA` is the Karachi
suffix — for a US ticker you drop four characters. No key, no plan, no bill. `fetch_global.py` has
used the same endpoint for `^GSPC`, `^VIX` and eight others every cycle for months.

**The stack is already market-agnostic.** The seam is `state/history/{SYM}.json` —
`{date, close, volume, open}`. `quant.py`, `backtest.py`, `predictability.py`,
`compute_fairvalue.py` and `correlation.py` import only `STATE / load_json / save_json /
research_symbols`; none contains PSX logic. The only currency-bound file is `liquidity.py`
(hardcoded PKR ADTV floors, `:80-81`) — `build_signals.py` is the other and §3 guts it anyway.

**Tokens: zero.** `run_cloud.py:1` — *"NO agents, no tokens."* All 40 deterministic steps are free.
Cost appears only if US names enter the Room queue.

**Scope: ~25 index and sector symbols, NOT a US stock universe.** On PSX the edge is structural —
`fetch_indices.py` exists because "no public source carries PSX index history". None of that
transfers; on AAPL the desk is the ten-thousandth chart. What transfers is astro-scored-against-
indices and the Room format. Broad indices (`^GSPC ^NDX ^DJI ^RUT ^VIX`), the ten SPDR sector ETFs,
global/EM (`EEM EFA ACWI`), rates and commodity (`TLT HYG GLD USO`).

**Size:** `state/history` is 24.4 MB / 452 files; `history_deep` 53.2 MB / 99 files (~540 KB each);
`.git` is 47.4 MB. 25 US symbols with deep history ≈ **13 MB**. A 100-name US universe ≈ 54 MB —
doubles the repo, buys no edge.

**Files:** new `config/markets.json` (currency, ADTV floors, calendar, symbol suffix, history
depth); a `market` field on `universe.json` symbols defaulting to `PSX` so nothing existing changes
shape; suffix read from config in `fetch_history.py` / `fetch_deep_history.py`; per-market bands in
`liquidity.py`; `data_health.py` must not let a US gap halt PSX publishing (Rule 6 halts new signals
on a health failure). **No US intraday** — `fetch_intraday.py` runs the PKT cycle, and US-EOD-only
is both cheaper and more publication-shaped.

---

## 8. Order of operations

**REORDERED** after the code pass — §4 moved first (it turned out to be copy-only, so it is the
cheapest real movement available), and §5 split so the watchdog probe is repointed before natal is
touched.

1. Incorporate (Pvt Ltd) — required for the payment gateway regardless.
2. §4 — reframe the reveal copy; publish the Room cadence. **Copy only, no architecture.**
3. §5 step 1 — repoint `watchdog.py`'s `PUBLIC_PROBE_FILE` and `middleware.js` `PUBLIC_FILES`,
   re-run the §9b gate regression.
4. §5 steps 2–5 — feature-flag personal astro off.
5. §3 — strip sizing from published output; add the browser calculator. Keep the `shares <= 0`
   validity guard.
6. §2a — X-ray: keep the tiles, neutralise the per-holding narrative.
7. §6a — rewrite `legal.json` for the publication frame.
8. §6b — the "proven" sweep; publish the schedule on the site.
9. §7 — add US coverage, reposition the site.
10. Send an SECP written query describing the product **as it will actually ship** — i.e. after
    steps 2–8. Also pursue free legal channels: P@SHA / PSEB member resources, NIC incubator
    legal advisory. Per §7a, the same question needs asking on the US side before the US surface
    is public, not after.

Steps 2–6 cost nothing but decisions and move the position materially. Do not take paid
subscriptions with target prices and house views public until step 8 has an answer.

---

## 9. Reference — what the competitors do

Both reviewed 2026-07-22. Both **unlicensed and say so in writing.**

- **alphagenpro.com** — "not registered as an investment advisor, brokerage entity, or asset
  management company under Pakistani financial regulations." Good clauses worth mirroring:
  explicit negative-relationship list (no advisory / fiduciary / brokerage / portfolio
  management), backtest-is-hypothetical language, "automated algorithmic framework, not a
  financial advisory service." Flaw: uses the word "recommendations" in §2, contradicting §1.
- **psxinvest.com** — "not a SECP-licensed investment advisor, broker, asset management
  company, or financial institution", while publishing BUY/SELL tags on named tickers with
  entry/target/stop, a quantified "70% means 70% hit rate" claim, and paid-subscriber
  testimonials asserting accuracy. Cautionary example, not a template.

Takeaway: the category operates unlicensed and nothing has been enforced **yet**. That is a
timing observation, not a legal one.
