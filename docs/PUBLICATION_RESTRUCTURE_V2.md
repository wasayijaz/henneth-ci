# Publication Restructure V2 — the license-free launch

**Status:** planning doc. Supersedes the signal-related parts of
[`PUBLICATION_RESTRUCTURE.md`](PUBLICATION_RESTRUCTURE.md) (V1).
**Owner decision date:** 2026-07-23.
**Why a V2:** V1 was written believing the *publication frame* (scheduled · impersonal ·
general circulation) protected the signals. The SECP **Research Analyst Regulations 2015 as
amended by S.R.O.7(I)/2026 (dated 2 Jan 2026, effective per the 8 Jan 2026 press release)** make
that assumption wrong for one specific class of output. This doc corrects it.

> **Not legal advice.** Drafted without a lawyer. The owner has no lawyer and is proceeding solo.
> This reduces exposure; it does not eliminate it. A written SECP query and a lawyer review remain
> on the list (§9). Treat the grey-zone calls in §8 as decisions to get confirmed, not settled law.

---

## 0. What changed since V1 — the one sentence

**V1 said "keep the signal levels as commentary; just remove the sizing." Under the Jan 2026 regs
that is not enough — the *signal types themselves* (buy/sell/hold, price targets, stop-loss levels,
TA trading signals on a named stock) are regulated "research services" the moment they reach the
general public, no matter how impersonal or scheduled.** The publication frame does not save them.

Everything else in V1 still stands. V2 changes: §3 (signals), §4 (Desk Room house view), and adds
the money/registration and PSX-data-license sections V1 never had.

---

## 1. The binding law (so nobody re-litigates this)

Research Analyst Regulations 2015, as amended 2 Jan 2026:

- **Reg 2A — registration is now mandatory.** "No person shall act as a research analyst unless
  registered." Applies to a **natural person OR a body corporate** (Reg 2(f)). Previously this was a
  voluntary guiding framework; it is now a hard requirement, and the press release explicitly names
  social-media / online individuals doing analyst-like work.
- **Reg 2(ha) — "research services"** = providing, to a person, a group, **or the general public**,
  any of: (i) buy/sell/hold recommendation · (ii) **price target** · (iii) **stop-loss target** ·
  (iv) opinion intended to influence a buy/sell/hold decision · (v) recommending a portfolio of
  listed securities · (vi) **trading signals based on technical analysis** · (vii) anything the
  Commission adds. **The words "general public" are what kill the publication defence for these.**
- **Reg 2(h) — "research report" EXCLUDES:** general trends in the securities market; commentary on
  economic/political/market conditions; **general commentary on the past performance of a sector or
  the broad-based index**; and **statistical summaries of financial data of companies.** This
  exclusion list is the escape hatch — it is the zone the survivor product lives in.
- **Reg 3 — qualification gate to register (individual):** a relevant HEC-recognised degree
  (finance/accountancy/business/statistics/commerce/economics/law) **+ 2 years research-department
  experience**, OR a CFA/FRM/PRM/actuarial qualification, **+ mandatory IFMP certification.**
  **The owner does not meet this** (fine-arts masters, no cert, no fin-sector experience) — so the
  register-as-an-individual path is closed, and Path A is not available. That is settled, not a
  choice. The only route is to live in the Reg 2(h) exclusion zone.

Two separate exposures, do not conflate:
1. **SECP (this doc's core).** Fixed by *product design* — remove the research-service outputs. Free.
2. **PSX market-data license (§8).** A *contract/fee* problem, independent of SECP. Applies because
   the desk pulls live prices straight from `dps.psx.com.pk` (`scripts/psx_data.py:16`,
   `scripts/fetch_intraday.py:14`). Cannot be designed away — must be licensed.

---

## 2. The test that now governs every surface

For each subscriber-facing surface ask, in order:

1. **Is it about a *named* listed security?** If no (macro, sector, index, education, pure data) →
   almost certainly safe (Reg 2(h) exclusions). Stop here.
2. **If yes — does it output a recommendation, a price target, a stop-loss, a portfolio pick, or a
   TA trading signal?** If yes → it is a **research service** (Reg 2(ha)) → must be cut or reframed.
3. **If it is named-stock but only *describes* (data, valuation working, both sides of a debate)
   with no verdict/target/signal** → grey zone. Defensible as commentary/statistical summary, but
   this is the line to keep clean: **describe, never direct.**

The whole restructure is: move every surface out of box 2 and into box 1 or a clean box 3.

---

## 3. README surface audit — every public surface, verdict, action

Read against the current [`README.md`](../README.md). ✅ keep · ⚠️ reframe · ❌ cut the offending part.

| README surface | Box | Verdict | Action |
|---|---|---|---|
| **Today / daily_read** (macro tone, favoured sectors, watchlist) | 1 | ✅ | Flagship. Lead with it. Keep watchlist at sector/theme level, not "buy these." |
| **Board — "backtest-proven signals"** (entry/stop/target on named tickers) | 2 | ❌ | **The core violation.** Remove entry/stop/target setups on named stocks from published output. §4a. |
| **Value — per-stock model fair value** (4 methods, median) | 3 | ⚠️ | Grey. A named-stock number can read as a price target (2(ha)(ii)). Keep as **valuation working / statistical summary of financials**; never label it a "target", never pair with a buy/accumulate. §4c. |
| **Strategies — 52 backtested strategies** (the library) | 1 | ✅ | The library + historical stats = education/statistics. Keep. |
| **Strategies — "triggering NOW on stock X"** (live signal) | 2 | ❌ | Cut the live "this strategy fires on FFC today → setup" surface. Convert to a **tool the user runs** (§4b). |
| **Desk Room — debate → Chair "house view" + dated falsifiable calls** | 2 | ⚠️❌ | Keep the debate; **cut the Chair's buy/sell house view and any price target** on the named stock. §4d. |
| **Scores — desk's OWN calls scored** | 2 | ⚠️ | Scoring your own buy/sell calls presupposes you make them. Keep scoring **brokers** (journalism). Reframe/limit the desk's-own scorecard to non-security-specific (macro/sector/astro) predictions. |
| **Scores — brokers scored** | 1 | ✅ | Journalism on public calls, published method. Keep — it's a moat. |
| **Research — broker notes + filings digested** | 1 | ✅ | Journalism / statistical summary. Keep. |
| **Macro / Dividends / Earnings / News** | 1 | ✅ | Reference data + macro commentary. Keep — strong retention. |
| **Value/risk profile, "questions before buying" checklist** | 1 | ✅ | Educational framework, not a rec. Keep. |
| **Global coverage (US/global indices)** | 1 | ✅ | Keep, but **de-emphasise as a *compliance* lever** — see §3a. |
| **Personal astro — chart scored against every ticker, "your strongest 3 matches"** | 2 | ⚠️❌ | Most personalised + names/ranks securities *for one person* → closest to 2(ha)(iv)/(v). Pull to **sector/commodity affinity only**; drop the named-ticker ranking. §5. |
| **Plans (Free/Investor/Pro/Broker)** | — | ⚠️ | Pro tier currently sells fair value + live strategy signals. Repackage around survivors. §6. |
| **Investor desk / learn (17 lessons)** | 1 | ✅ | Education. Fully clear. Keep — highest-retention asset. |
| **Disclaimers / legal.json** | — | ⚠️ | Strengthen per V1 §6a + add the RA-regs positive basis. §7-legal. |

### 3a. Global coverage is no longer a compliance argument

V1 §7/§4 leaned on "the publication defence is stronger under a US/global frame." Under the Jan 2026
regs that reasoning weakens: SECP catches provision **to the general public** regardless of frame, so
widening coverage does not dilute SECP — and V1 §7a already flagged it *adds* a US regulator. **Keep
US/global coverage if it helps the product** (context, astro-against-indices reads better), but strike
it from the compliance rationale. It is a product choice now, not a shield.

---

## 4. The three flagship reframes

### 4a. Signals — remove the setup from published output (hardens V1 §3)

V1 already located the code: `scripts/build_signals.py:34` reads `capital_pkr`; `:74-80` computes
`risk_budget`/`shares`/`size_pkr`; `:89` emits them; `:77-79` uses `shares <= 0` as the validity
guard that **must survive**. V1 said strip *sizing*, keep *levels*. **V2 correction: also strip the
published entry/stop/target on named stocks** — a price target (ii) and a stop-loss (iii) are
research services on their own.

- Keep computing everything internally (the Auditor's Rule 4/7 re-derivation must not break).
- **Publish none of it as a per-stock setup.** No `entry`/`stop`/`target`/`size` on a named ticker
  on any subscriber surface.
- Replace with the **user-driven tool** (§4b) + the browser position-size calculator V1 already
  specced under `site/src/pages/tools/`.

### 4b. The "you decide" reframe — the key unlock

The difference between a research service and a software product is **who points at the stock.**

- ❌ *Desk*: "Buy FFC at 385, stop 370, target 410." → research service. Dead.
- ✅ *User-driven tool*: the subscriber picks a stock and a strategy; the tool shows that strategy's
  historical behaviour and current indicator state **on the stock they chose**. The desk recommends
  nothing; it renders data on demand. This is a screener/backtest **tool**, not a signal feed.
- ✅ *Factual description*: "FFC reclaimed its 200-DMA on 2× average volume; results 30 Jul." —
  statistical/descriptive, no verdict.

The strategy library and backtest engine already exist — this is a framing + UI change (surface them
as a tool the user runs), not new machinery.

### 4c. Fair value — keep as valuation, never as a target

The 4-method valuation is computed mechanically from reported financials → defensible as a
"statistical summary of financial data" (Reg 2(h)(vi)). Keep it, with guardrails:
- Never use the word **"target"** for it.
- Never render it beside a buy/accumulate/entry.
- Present it as *"the working, four ways — you read it"*, i.e. the method is the product, the number
  is an output of published method, not a call. Same spirit as the site's existing "show the method,
  not a number" line.

### 4d. Desk Room — keep the debate, drop the verdict

The Room is the stickiest differentiator; it can survive, reframed. V1 §4 established the code is
already impersonal/scheduled (`app.js:2469` renders only a pre-computed session). V2 adds the
substantive cut:

- **Keep:** chartist memo, fundamentalist memo, bull case, bear case, the animated replay. Presenting
  both sides of a named stock with the evidence = roundtable **commentary**.
- **Cut from the Chair:** the buy/sell/accumulate **house view**, the conviction rating, and any
  **price target / dated price call** on the named stock. A "house view: bullish, target 410" is
  2(ha)(i)+(ii)+(iv) in one line.
- **Reframe the Chair** to a *synthesis of the disagreement*: what the bull and bear each need to be
  right, what data would resolve it, what to watch — **no verdict, no target.** "Here is the argument;
  you decide" instead of "here is our call."
- Also do V1 §4's copy fixes ("Run the desk on FFC" → "Read the desk's debate", publish the cadence).

---

## 5. Personal astro under the RA regs

Owner decided (V1 §5a) to keep `#/cast` / `#/mychart`. Under the Jan 2026 regs the **named-ticker
ranking is the exposure**: `app.js:1803-1816` scores *every PSX ticker* against the user's birth
chart and surfaces "your strongest 3 matches." Ranking securities *for one identified person* is the
closest thing in the whole product to 2(ha)(iv)/(v) — worse than the signals, because it is
personalised.

**Change:** pull personal astro to **sector and commodity affinity only** (cement, banks, gold, oil,
E&P…) — no per-named-stock score or "top matches" list on a personal surface. This is exactly the
softer marketing-site version V1 §5a already describes; make it the *only* personal astro version, in
the terminal too. The impersonal astro pillar (`astro`, `astro_regime`, `astro_backtest`) stays fully
live — it is dated, scored, and market-relative, not personalised.

Birth data stays private to the account; disclaimer stays on every astro surface; `legal.json`
privacy section must cover birth date/time/place explicitly.

---

## 6. Can it still be a sticky, paid product? Yes — here's what's left

Stickiness was never the buy signal (the loudest feature ≠ the stickiest). After the cuts, the
product still holds these, and every one survives the regs:

| Retention driver | Surface | Why it's clear |
|---|---|---|
| **Daily habit** | daily_read, macro, news | Commentary — the newsletter model (Bloomberg/FT monetise exactly this with zero signals) |
| **Data moat** | quant, backtests, fundamentals, dividends, earnings calendar, liquidity | Statistical summaries + tools |
| **The debate** | Desk Room (reframed) | Roundtable commentary — nobody else on PSX has it |
| **Journalism / accountability** | broker scorecard, leaderboard, research digests | Scoring public calls — a genuine moat |
| **Education** | 17-lesson Investor desk | Not research at all — high retention |
| **Astro differentiation** | impersonal astro + sector/commodity personal | Unique, dated, honest about the null result |
| **User tools** | screener, backtest-on-your-pick, position-size calculator | Software the user drives, not a signal feed |
| **Personalisation** | portfolio tracker / X-ray (tiles, per V1 §2a) | Arithmetic on the user's own holdings = tracking |

The pitch shifts from *"we tell you what to buy"* to *"the best PSX research terminal + the tools to
decide for yourself"*. That is a real, defensible, paid product — and it removes the single biggest
legal risk at the same time.

---

## 7. Getting paid — entity, bank, gateway

None of this needs an RA license (the product sits in the exclusion zone). The entity is for tax,
banking, the PSX data contract, and **limited liability** — not for SECP registration.

**Entity — recommended: Single-Member Company (SMC), private limited (SECP).**
- One shareholder, one director — fits a solo founder. Gives **limited liability** (the reason not
  to use a sole proprietorship: this product sits near securities regulation and republishes PSX
  data — unlimited personal liability is the wrong posture).
- **Object clause at incorporation: information technology / data services / publishing — NOT
  "securities advisory" or "research analyst."** The registered object should not describe you as an
  adviser.
- No minimum paid-up capital; SECP eServices incorporation fee is modest (thousands of PKR).
- Sole proprietorship is *legal and cheaper* but rejected here for liability + it's a weaker
  counterparty for the PSX data agreement and gateway onboarding.

**Then, in order:**
1. Incorporate the SMC (SECP eServices).
2. Get the company **NTN** (FBR) and a **business bank account** in the company name.
3. Wire a payment path (below).
4. Approach PSX for the data license as the entity (§8).

**Payment path — the Pakistan constraint (README already notes billing is unwired):**
- International processors (Stripe) don't onboard Pakistan. Local gateways: **Safepay, PayFast**
  (cards + wallets), plus JazzCash/Easypaisa for wallets. All onboard a **registered business with an
  NTN + business bank account** — another reason the entity comes first.
- **Recurring subscriptions** are the weak spot locally — verify card-on-file / recurring support
  with the gateway before promising auto-renew; you may run manual/renewal-reminder billing at first.
- **Merchant-of-Record option to investigate:** Paddle / Lemon Squeezy become the seller of record,
  handle global cards + tax, and pay you out — this can sidestep the local-gateway recurring gap *if*
  they support Pakistan payouts. Confirm PK eligibility before relying on it.

---

## 8. The PSX market-data license — gettable, but entity-gated

**Short answer: yes, gettable by someone like you — but you need the entity first, and you should
switch off the free `dps.psx.com.pk` scrape before you charge.**

- PSX licenses market data to vendors and websites of all sizes via **marketdatarequest@psx.com.pk**
  (the address on the notice) and the **Data Services / Vending** desk. It is not reserved for big
  terminals.
- **Tiers matter to cost:** real-time redistribution is the expensive tier; **delayed / end-of-day
  display** is the cheap tier. The desk is daily-timeframe and EOD-driven (README: "PSX DPS portal
  EOD"), so you want the **delayed/EOD website-display** license, not real-time.
- **You need a legal entity to sign it.** PSX executes the data agreement with, and invoices, a
  registered entity (NTN). A sole prop *may* be accepted, but the SMC is the cleaner, expected
  counterparty. So the data license **also** pushes you to incorporate first — same SMC as §7.
- **Your own computed output is your IP, not PSX's to license** — indicators, backtests, fair values,
  prose, scores. What PSX licenses is the **raw price/market data**. You still need *a* licensed
  price source, because the prices themselves are their data.
- **Exact fee: unknown — get it from PSX, don't guess.** [`PSX_COSTS_VERIFIED.md`](PSX_COSTS_VERIFIED.md)
  covers *trading* costs, not data-license fees. The annual data-license fee must come from PSX's own
  quote. Do not publish or budget a number until they send the schedule.

**Sequence:**
1. Incorporate SMC → NTN → business bank account (§7).
2. Email marketdatarequest@psx.com.pk **as the company**, asking for the **delayed/EOD
   website-display** license and fee schedule. (Not as an individual, pre-incorporation.)
3. Sign + pay the annual fee.
4. Move the price source onto the licensed feed; stop the commercial use of the free DPS portal.
5. **Until licensed, do not charge on data scraped from the free DPS portal.** The current free
   period covers you while unincorporated/unlicensed; billing must not switch on before steps 1-4.

---

## 9. Order of operations

Free design changes first (they move the position and cost nothing); paid/registration steps gate
the money.

1. **§4d copy + verdict cut** — Desk Room: drop the Chair's house view/target, reframe to synthesis;
   fix the "Run the desk" copy; publish cadence. *(cheapest, do first)*
2. **§4a** — strip published entry/stop/target/size from named-stock signals; keep the internal
   compute + `shares <= 0` guard.
3. **§4b** — surface strategy library + backtest as a **user-run tool**; add the browser position
   calculator (V1 §3).
4. **§4c** — fair value: relabel, de-target, never beside a buy.
5. **§5** — personal astro to sector/commodity affinity; drop named-ticker ranking.
6. **§3 Scores** — keep broker scorecard; reframe the desk's-own scorecard off security-specific calls.
7. **legal.json** (V1 §6a) + the "proven" copy sweep (V1 §6b) + publish the schedule.
8. **Incorporate the SMC** → NTN → business bank account (§7).
9. **PSX data license** as the entity (§8); switch the feed; then wire billing.
10. **Written SECP query** describing the product *as it will actually ship* (after 1-7); pursue free
    legal channels (P@SHA / PSEB, NIC incubator legal advisory) for a review before charging.

Steps 1-7 cost nothing but decisions and move the position materially. **Do not switch billing on
until 8-9 are done and step 10 has at least a lawyer's eyes on `legal.json`.**

---

## 10. What only a lawyer / SECP query can settle (the honest grey zones)

Flag these as open, not resolved:
- Whether a **mechanically-computed fair value** on a named stock reads as a "price target" (§4c). We
  argue statistical-summary; a regulator might disagree.
- Whether a Chair **synthesis without a verdict** still counts as "opinion intended to influence"
  (2(ha)(iv)) (§4d). We argue no; keep it descriptive to stay clear.
- Whether **sector/commodity astro affinity** is fully clear once named-stock ranking is removed (§5).
- The exact **PSX data-license tier and fee** (§8) — a quote, not a judgment.

These are the four questions to put in the SECP written query and in front of any free legal channel.
Everything else in this doc is a design change you can make now.
