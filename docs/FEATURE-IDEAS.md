# Henneth Desk — Feature Ideas & New Additions

Compiled 2026-07-31. Two inputs: (a) a full audit of what the repo already computes but never
shows, (b) external research on PSX retail apps and global research platforms.

Every idea here is checked against **SECP Reg 2(ha)** (S.R.O.7(I)/2026). The desk holds no Reg 3
licence, so nothing may publish a buy/sell/hold, price target, stop-loss, or portfolio pick on a
**named security**. Safe shapes: historical/factual, impersonal, sector-level, or a calculator the
reader runs with their own inputs. Each item below is tagged.

---

## Part 1 — What the desk already computes and never shows

The single biggest finding: **74 files in `state/`, only 52 are ever fetched by the dashboard.**
25 are computed every cycle and read by nobody. One fetch points at a filename that does not exist.

This is the cheapest feature source in the product — no new data, no new scraping, no new licence.

### 1.1 Dossier tab on every ticker — biggest win available
`state/dossiers.json` is 791 KB covering **464 tickers**: technical, fundamental, valuation,
documents, recent news. Desk Room covers **43**. The file is not fetched at all.

Surfacing it is roughly a **10× expansion of research coverage** with zero new computation.
*Reg 2(ha): safe* — descriptive/factual per name, no call, no level.

### 1.2 Per-stock pattern hit-rate table
`predictability.json` carries **7 named setups × 229 tickers**, each with sample size `n` and
`hit_rate`, walk-forward, 10-day horizon, ±3%: `breakout`, `pullback_trend`, `momentum_follow`,
`oversold_bounce`, `ma50_reclaim`, `meanrev_snapback`, `gap_up_hold`.

The dashboard renders one scalar `score` and throws the rest away.
*Reg 2(ha): safe* — pure historical frequency, phrased as "this pattern has resolved up N% of the
time on this name's own history". Not a prediction.

### 1.3 Liquidity capacity — "how big can you go"
`liquidity.json` has 25 fields; 7 are shown. Hidden and valuable:
- `capacity_at_50bp_pkr`, `capacity_1day_pkr` — square-root-law capacity
- `days_to_liquidate`
- `amihud_x1e6`, `amihud_pctile`
- three independent spread estimators (`roll_spread_pct`, `cs_spread_pct`, `fht_spread_pct`)
- `zero_volume_days_pct`, `zero_return_days_pct`, `daily_sigma_pct`

Capacity is the most useful unshown number in the repo. On PSX, where a large share of the board is
thin, "can this name absorb my size at all" is a real, unanswered question.
*Reg 2(ha): safe* — a market-microstructure fact about the security, not a call on it.

### 1.4 "What the desk distrusts" honesty badge
`verify.json` holds **389 tickers** adversarially QA-flagged by `room-verifier`. Never surfaced.
Publishing the desk's own doubts is a trust move no PSX competitor makes.
Already filed as `product_backlog.json` item 7 (`verify-json-unsurfaced-qa`).
*Reg 2(ha): safe* — data-quality metadata.

### 1.5 Correlation peers on the ticker page
`correlation.json`: 1832 pairs, 750-session lookback, top-8 peers per name. Fetched today, used
only by the portfolio page. "Names that move with this one" belongs on every ticker.
*Reg 2(ha): safe* — statistical relationship, historical.

### 1.6 Earnings and ex-dividend countdown
`fundamentals.json` carries `next_earnings` and `ex_div_date` for **206 names**. Referenced
nowhere in the app. A dated calendar strip is one of the most-used features on every global
platform.
*Reg 2(ha): safe* — announced corporate dates, factual.

### 1.7 Research-queue transparency
`room_queue.json` + `room_plan.json` (`deferred_full: 69`) know exactly which names are waiting for
a Desk Room session. "This name is #14 in the queue" turns a backlog into a feature and sets
honest expectations.
*Reg 2(ha): safe* — operational metadata.

### 1.8 PSX-native candles
`ohlc_daily/` (16 files, growing) is the **only PSX-native OHLC the desk owns**, written by
`snapshot.py`. Zero consumers. `history/` has no high/low at all; `history_deep/` is Yahoo-sourced
and covers only 122 of 470 names. Every real candle chart on the site depends on this file
eventually being used.
*Reg 2(ha): safe* — price history.

### 1.9 Cycle uptime strip
`runlog.json` is declared in `LIVE_FILES` but never actually fetched, and is stale since
2026-07-17. A visible "last refreshed / cycles completed today" strip is both a trust signal and a
self-monitoring tool.
*Reg 2(ha): safe.*

### 1.10 Desk-vs-TradingView drift widget
`crosscheck.json` already compares the desk's own numbers against TradingView. Showing the drift is
another credibility artifact.
*Reg 2(ha): safe* — but must carry the standing note that TV PSX data is ~15 min delayed, so a gap
is expected, not an error.

### 1.11 Regime-conditional astro panel
`astro_regime.json` and `astro_natal_test.json` (379 tested variants) are scored, falsifiable, and
unsurfaced. This is the desk's genuinely differentiated pillar and it is currently invisible.
*Reg 2(ha): safe only if kept sector/market-level* — a named-ticker astro ranking would not be.

---

## Part 2 — Broken today (found during the audit)

- **`dashboard/app.js:3865`** — `await j("backtest.json")`. That file does not exist; the real name
  is `backtests.json`. Always resolves null, so the Learn page's "across N tested sets" clause at
  `:3868` never renders. Compound bug: the code then reads `bt?.results || bt?.strategies`, but
  `backtests.json` uses the key `templates`. Both must be fixed together.
- **`dashboard/app.js:6431`** — `CAPTCHA_SITE_KEY = ""`. The captcha has shipped **disabled** since
  2026-07-23 while `README.md:370-372` states it is on. Either turn it on or correct the README;
  a security control documented as active but inert is the worse of the two states.

### Thin routes worth filling
`/shipped` (14 lines), `/ask` (17 — an input box with no corpus behind it), `/news` (20),
`/calendar` (21), `/glossary` (26 — hardcoded, ignores the generated `explainer.json`),
`/research` (38 — only 36 documents), `/leaderboard` (44 — renders an empty structure).
`/scores` is a dead route.

### Empty by design failure, not by choice
- `leaderboard.json` and `broker_scorecard.json` are both literally `{}`. 410 claims filed, **0
  resolved**. Only 4 broker calls captured, all from one house, against `min_sample_to_rank: 5` —
  so nothing is rankable. `SOCIAL_PLAN.md:267-285` already targets Q4 2026 for a real league table.
- `learnings.json` is empty because the `reviewer` agent is invoked by **no cycle prompt**. That is
  a one-line pipeline fix, and it unblocks the desk's whole learning loop.

---

## Part 3 — External research

### PSX competitor landscape
The PSX retail market is served mainly by price-and-portfolio apps, not research products.

- **Investify** — real-time prices on 500+ listed companies, interactive charts with up to five
  years of history, fundamentals, alerts, business news, a **free demo trading account**, and a
  Shariah-compliance filter built on KMI-30 / KMIALL.
- **iInvest** — five years of price history, multi-device portfolio sync, live news and research,
  real-time prices and exchange rates.
- **PSXON** — the other commonly cited free option for prices, learning, and demo practice.

Trading for these apps routes through **KiTS** (the Karachi Internet Trading System) — note KiTS is
a *trading platform*, not a data vendor; an earlier draft of this doc had that wrong. PSX **UINs
reached 583,000 at end-FY26, +48% YoY**, after sitting flat at 230,000–300,000 from FY16 to FY23.

**What this means for Henneth.** Nobody in this set ships walk-forward pattern statistics,
liquidity capacity, adversarial QA of their own data, or a scored astro lens. The competition is
competing on *quotes and portfolio tracking*. The desk's whole computed layer is unoccupied ground
— but it is unoccupied only for as long as it stays hidden inside `state/`.

Two features the local market has proven demand for, and the desk lacks:
- **Shariah / KMI-30 compliance filter.** Table stakes in Pakistan. The desk has sector and
  universe data; a compliance flag is a small addition with outsized local relevance.
- **Demo / paper mode.** Both leading apps ship one. For Henneth this is doubly attractive because
  a paper portfolio is *the reader's own* — it is a calculator, so it stays clear of Reg 2(ha)
  entirely while delivering the "what would this have done" experience.

### Global research platforms — what the market has converged on
- **Simply Wall St** wins on visual translation of dense financials, and on the **Snowflake**: one
  scoring system applied identically to every equity across five axes (Value, Future Growth, Past
  Performance, Financial Health, Dividends). Its weakness is throttling — 30 reports/month on
  Premium — plus shallow screening and missing metrics, which pushes serious users away.
- **Koyfin** wins on depth: terminal-style customizable dashboards, 10 years of financials,
  100,000+ securities, 5,900+ screening criteria at $468/year.
- The stated 2026 direction across the category: unlimited access, advanced analytics, AI-driven
  insight, professional portfolio management. Pretty visualization alone is no longer enough.

**Transferable to Henneth, cheaply:**
1. **A Snowflake-equivalent.** One consistent multi-axis score on every one of the 464 dossier
   names. The desk already computes the inputs — valuation, liquidity, predictability, QA
   confidence. Presenting them as one comparable shape is a presentation change, not a data
   project. This is the single highest-leverage borrowed idea.
2. **Real screening.** Koyfin's moat is the screener. The desk has ~229 tickers with pattern stats,
   206 with fundamentals, and full liquidity metrics — enough for a genuine multi-criteria screen,
   which no PSX product offers. *Reg 2(ha): a screen the reader configures is a tool, not a pick.
   A pre-built "top picks" screen is not — the reader must set the criteria.*
3. **Do not throttle.** Simply Wall St's report cap is its most-cited flaw. Henneth's costs are
   deterministic Python, so unlimited access is nearly free and is a direct competitive answer.

---

## Part 3B — Deep research pass (2026-07-31)

Nine parallel research agents. Everything below is sourced; anything the agent could not verify from
a primary source is tagged **[UNVERIFIED]** and must not be cited as fact.

### 3B.1 Pakistan — who actually competes, and at what price

**Structural fact that sets the price anchor: research in Pakistan is broker-produced and given away
free as customer acquisition.** Arif Habib's AHL Research runs 8 analysts covering 50+ companies
across 11 sectors, >70% of KSE-100 free-float market cap — and it costs a client nothing. Broker
apps: KTrade (markets "1M+ users" vs ~45K Play Store downloads, ~3.6/5), Finqalab, JS Global,
AKD/BLAST, Topline Vtrade, AHLTrade.

Independents:
- **Sarmaaya** — Free / **Pro PKR 4,000/mo (38,400/yr)** / **Premium PKR 6,000/mo (57,600/yr)** /
  Elite PKR 3,000 alumni / Enterprise. Self-describes as a "PSX authorized data redistributor".
- **Investify** — free, ad-supported, ~4.7★ over ~10,000 reviews, claims a PSX real-time licence.
- **PSX Invest (psxinvest.com) — the closest structural analogue to Henneth, and the clearest
  regulatory warning.** AI/ML technical analysis on 450+ stocks, daily signals at 18:00 PKT with
  **entry range, price target, stop-loss and a calibrated confidence score**, 8 signal types, 14
  chart patterns, min 2:1 R:R, WhatsApp/SMS alerts. **Free / Learner PKR 199 / Pro PKR 2,500 /
  Premium PKR 6,000 per month.** It states plainly that it is "not a SECP-licensed investment
  advisor" *while publishing named-ticker targets and stops*. That is exactly the posture Reg 2(ha)
  removed. Do not copy it — it is the control group.
- FoxLogica Discord bot, PKR 500–5,000 **[UNVERIFIED]**.

**Two price points exist and nothing sits between them:** a sub-PKR-500 impulse tier and a
PKR 2,500–6,000 "serious" tier. PSX Invest and Sarmaaya independently converged on **PKR 6,000/mo
as the ceiling**; ~20% annual-discount is the norm. Consumer anchor for reference: Netflix PK
250/450/800/1,100, Spotify 379/519/679 — so a PKR 2,500–6,000 product costs 3–24× the top
entertainment subscription. That is the wall.

**Nine gaps nobody in Pakistan occupies:** a published scored track record · a broker-call
leaderboard · falsifiability as a feature · lookahead-free auditable backtests · **Urdu output (every
platform is English-only)** · independent non-broker fundamental research at depth · data-integrity
and staleness disclosure · a *licensed* independent research publication · explicit macro-regime
integration. **Net pattern: nobody in the independent tier registers; everybody disclaims.**

### 3B.2 The legal template — how global platforms stay legal, ranked

This is the most directly useful finding in the whole pass. Ordered most- to least-copyable under
Reg 2(h):

1. **Stockopedia — the cleanest template, and the one to copy.** StockRanks 0–100 on Quality, Value
   and Momentum, recomputed daily Tue–Sat over 32–35k stocks; 350+ screener criteria; ~65 Guru
   Screens; Folios (25 portfolios, TWR, CSV-only). It **issues no fair value, no price target and
   no buy/sell/hold on any named security**, and positions itself as a "screening tool" / "research
   compass". It **tiers on universe coverage, not features** — Developed Asia $395/yr, US+Developed
   Asia $600/yr, 14-day trial + 30-day money-back, no freemium. It publishes **simulated,
   equally-weighted** performance (~11.4% annualised, 62% win rate, UK 90+ since Apr 2013)
   explicitly labelled as not actual trading. Forum critique worth heeding: hindsight-bias questions
   on rank validation, only 5–10yr metric history, and **results announcements take days-to-weeks to
   appear in site data** — a lag any honest backtest must model.
2. **Simply Wall St "Narratives"** — the platform supplies the model and the data, the *user* supplies
   the fair-value call. Deliberate liability-shaping design: authorship of the verdict is moved off
   the platform. Its DCF is published open-source on GitHub; ~120,000 securities across 129
   exchanges; Free / ~$10.95 / ~$21.50 per month.
3. **Value Line — publisher/adviser separation.** Timeliness ranks, an 18-month target range, model
   portfolios; print $598/yr, print+digital $718/yr, VL600 $299/yr, newsletter $49/yr. Managed via
   the publisher's exclusion **§202(a)(11)(D)** plus a *legally separate* adviser, EULAV Asset
   Management, spun out in 2010. Also a caution: the Timeliness edge has decayed (Affleck-Graves &
   Mendenhall 1992; Choi 2000; flat post-2000) — a published ranking system's edge is not permanent.
4. **Morningstar — not copyable.** Moat → Fair Value Estimate → Uncertainty → Star rating; Investor
   $249/yr ($199 promo), $34.95/mo (a 68% monthly penalty). Its ratings are issued by *Morningstar
   Research Services LLC, an SEC-registered investment adviser*; credit via Morningstar DBRS, an
   NRSRO. The licence is what makes the product legal. Most-cited "worth it" feature: **X-Ray +
   Stock Intersection**. Complaints: ads shown to paying subscribers; linked brokerage accounts carry
   no transaction history.
5. **Seeking Alpha — the direct contrast case.** The only one that authors *and sells* its own
   directional calls: Quant Ratings on 5,000+ names, **Alpha Picks with explicit buy AND sell
   signals**. Premium $299/yr, Alpha Picks $499/yr, bundle $798 ($639 first year), PRO $2,400/yr.
   Advertised +371.06% vs S&P +99.68% since Jul 2022 **[UNVERIFIED vendor claim]**. Loudest complaint
   is subscription management; a BBB complaint documents $1,700+ paid with pro-rata refunds refused.
   **The entire $499 Alpha Picks SKU is precisely what SECP treats as a licensed research service.**
6. **GuruFocus** — GF Score; GF Value anchored to a company's *own* historical multiples (a neat
   trick: no analyst opinion required). Premium $424/yr, Premium Plus $1,273–1,398, Professional
   $2,323, API $200/mo. Billing friction is the loudest complaint; new AI tools "fail basic questions".

**Universal complaint across all five: data errors and staleness. Second: portfolio/brokerage sync is
half-built everywhere.** Both are things this desk can actually win on — `verify.json` exists.

### 3B.3 Frontier / emerging-market retail products — the real pricing template

Western pricing is irrelevant to Pakistan. These markets are the comparable set.

**India.** *Screener.in* ₹0 / **₹4,999/yr** (48-hr refund) — the free tier gives full 10-year
financials; the paid tier gates **volume and workflow, not data** (50 → unlimited companies, 10 → 800
alerts, 18 → 60 quick ratios, CSV, ₹500 AI credits). Ships a **custom formula language**, concall
notes, and free shareholding + insider history. *Trendlyne* GuruQ ₹310/mo or ₹2,190/yr; StratQ
₹5,900/yr; PRO ₹1,500/mo or ₹8,900/yr; PRO PLUS ₹2,000/mo or ₹11,900/yr — sold on **parameter count
and alert latency** (1,758 params / daily technicals vs 3,512 / **15-minute** technicals; 200 vs
1,200 backtests per year), plus a proprietary **DVM (Durability/Valuation/Momentum) composite badge**.
*StockEdge* Premium ₹399/mo or ₹1,500/yr, Pro ₹1,499/mo or ₹5,995/yr, Club ₹2,499/mo or ₹11,994/yr —
**500+ pre-built scans as a menu, not a formula box**, with custom scans sold as a *quota* (2 → 50).
*Tijori* (Zerodha invested $5mn) $0 / $4/mo / **$43/yr** — **1,000+ free and 6,000+ paid hand-built
operational metrics** (market share, revenue mix, capacity) with **a source link on every datapoint**,
plus a Reverse DCF. *Finology ONE* ₹299/mo bundles a course with research; *Finology 30* ₹11,999/yr
pushes 2–3 monthly recommendations over notification, email and WhatsApp. MarketsMojo ₹9,999 /
₹4,999 / ₹12,999 per 13 months **[UNVERIFIED, secondary source]**. *smallcase* — a marketplace where
research is the product and the broker is the rail (₹399/mo or 1.75%+GST to the SEBI-registered
manager; platform charge ₹100 or ₹10 capped at 1.5% per invest event).

**Bangladesh.** *AmarStock* — 7-day trial; ৳300 (1mo) / ৳800 (3mo) / ৳1,250 (6mo) / **৳2,000 (1yr,
"most popular")** / ৳5,000 (3yr), and plans **stack rather than replace**. Headline features are
**category-level PE (DSE A/B/N/Z)** and **circuit-breaker tracking** — local regulatory constructs
modelled natively. Bengali UI. Sells Elliott Wave and FA courses on the same site. StockNow, LankaBD,
StockBangladesh, BullBd — pricing **[UNVERIFIED]**.

**Sri Lanka.** *AnalytiCAL (CAL)* — **free to all CAL brokerage clients**, marketed as "no expensive
subscriptions": complete financials for every CSE company, **foreign buying/selling data**, screeners,
analyst commentary. Research as a customer-acquisition weapon for the brokerage — the same dynamic as
Pakistan. The CSE's own app ships **CDS E-Connect** (view your depository account, transfer stock),
24-hour e-KYC, and **"Investo," a trilingual Sinhala/Tamil/English AI chatbot**.

**Vietnam.** *Simplize* "value a stock in 3 minutes" — Premium price **[CONFLICTING/UNVERIFIED:
199,000đ vs 499,000đ vs 649,000đ; vendor page 404'd]**. *FireAnt* Copilot 399,000 VNĐ/mo promo and an
**Excel add-in sold as a separate 5,400,000 VNĐ/yr SKU**. *VietstockFinance* — five tiers where
**history depth is the paywall** (Pro 4 years with Excel export, Premium unlimited); prices are
sales-gated. *WiChart/WiData* ~300,000đ **[UNVERIFIED]**, paid via **MoMo / VNPAY / bank card, not
Stripe**, and **gifted to new DNSE brokerage customers**. The `vnstock` open-source library sets the
free floor.

**Indonesia.** *Stockbit* Rp250,000 (1mo) / Rp200,000 (2mo) / **Rp150,000 (3mo, most popular)** /
**Rp0 if you open a Stockbit Sekuritas account**. The free tier alone carries a social feed,
Rp100mn virtual trading, Consensus Target, corporate-action and IPO calendar, Earning Recap,
user-published Set Target Price, and insider transactions. Pro adds 15-year charts, a guru-strategy
screener, **Seasonality** (15+ years of monthly patterns), PE/PBV standard-deviation bands, and
**Bandar Detector + Broker Summary** — *bandar* = market operator; it infers which house is
accumulating from IDX broker-attributed trade data. **The single most instructive feature found in
the entire pass.**

**Philippines.** *Investagrams* Prime PHP 349/mo, Prime+ PHP 599/mo, Elite PHP 999/mo
**[secondary-sourced; the vendor page renders prices from JS]**. **AI analyses are metered as a
monthly quota — 3 / 30 / 80** — the cleanest LLM-cost tiering seen anywhere. Ads are what you pay to
remove. Explicitly **not a broker** — which proves standalone research SaaS survives at PHP 349.

**Kenya.** *myStocks (Synergy)* — Standard KES 100 daily / 500 monthly / 1,463 quarterly / 2,850
biannual / 5,550 yearly; Professional 100 / 1,000 / 2,925 / 5,700 / 11,100; Corporate — / 2,000 /
5,850 / 11,400 / 22,200. **The KES 100 day pass (~$0.75) is the most important number in this
section** — micro-duration pricing matched to mobile money. Level 2 depth, 30+ indicators, **19+
years of history**, SMS + email + in-app alerts, and **myCDS: portfolio import from the depository,
not from a broker API**. Rich.co.ke is an NSE **Authorised Data Vendor** — the licence is the moat.

**Nigeria.** *NGX Pulse* — **"Free. Always."** Live prices, **corporate disclosures aggregated into
an investor feed**, heatmaps, NASD OTC, US stocks quoted in naira, a dividend calendar, **Whale Watch**
(large block trades) and **Insider Signal**. *TopChor* free forever; Pro price not published.

**Egypt.** Thinnest and all **[UNVERIFIED]** — Mubasher Info / Smart Signals (no published pricing),
but two ideas worth stealing: **live desk sessions** and **bilingual Arabic/English delivery**.

**Ten features common in these markets and absent from Western tools:**
1. Broker-attributed flow — "who is accumulating".
2. **Corporate-announcement aggregation as the core product** — the exchange's filings portal is
   unusable, and the cleanup *is* the product. (PSX/DPS is exactly this situation.)
3. Concall / results-call notes at retail price.
4. Shareholding + insider tracking on the **free** tier.
5. Hand-built operational metrics with a **source link per datapoint**.
6. **WhatsApp and SMS as first-class alert rails**, not email.
7. Vernacular / multilingual delivery.
8. **Depository (CDS) portfolio integration** rather than broker-API integration.
9. A free social layer plus gamified paper trading as the funnel.
10. Education bundled into the subscription.

**Pricing conclusion: the workable centre of gravity is $2–5/month billed annually.** Almost nobody
sustains more than ~$15/mo on monthly billing without advisory calls attached; annual discounting is
aggressive to the point of distortion; **zero is a real and common price**; micro-duration pricing is
under-used and works. **Distribution: broker bundling is the single biggest channel** — web for
depth, app for alerts, local payment rails not Stripe, media as funnel.

**The direct implication for Henneth.** Because Reg 2(ha) closes the advisory tier that every foreign
top price band depends on, the monetisable ceiling here is data + screening + alerts + education →
the $2–5/mo band → **volume, not ARPU, is the only path**. The research agent independently endorsed
the `_ur` + `state-translator` architecture as "correct and a genuine competitive asset" — Urdu is a
gap in every product surveyed.

### 3B.4 Institutional / AI platforms — and why the desk's architecture is right

- **AlphaSense** — 500M+ documents, Smart Synonyms, Deep Research with sentence-level citations;
  acquired Tegus for **$930M** (Jun 2024), 260k+ expert transcripts; AI-Led Expert Calls ~$450/hr
  prorated + $75 transcription; ~$10–40k/seat/yr estimated, average contract ≈$123,760/yr (Vendr).
  Users report 10–15 hrs/week saved; ~40% flag search completeness for longitudinal work.
  **Cleanest regulatory posture in the set: it distributes others' calls and authors none.**
- **Quartr** — 14,250+ companies across 62+ markets, 48M+ IR documents, and **slide-level keyword
  search, which nobody else has**; ships an MCP server as a first-class product. Free mobile /
  Core ~$25/mo **[UNVERIFIED]** / Pro quote-only. **100% descriptive → lowest regulatory risk.**
- **Fiscal.ai** (ex-FinChat, ex-Stratosphere.io — rebrand confirmed mid-2025, $10M Series A) —
  **2,250+ hand-verified segments and KPIs across 100,000+ companies** is the moat, not the chat box.
  Free / Pro $39/mo annual ($468/yr) / Max $79/mo annual ($948/yr). Official app inside ChatGPT and
  Codex since Jun 2026.
- **Bloomberg** — **$31,980/yr** single seat, ~$28,320 at 2+, 2-year minimum, 6.5% increase from
  1 Jan 2025 (well-corroborated *estimate*; Bloomberg publishes no price). ASKB agentic AI in beta
  since 23 Feb 2026. TRAN is the function AI disrupts; **IB messaging is undisruptable, and is why
  the $32k renews**.
- Funding context: Rogo **$2B valuation** (Apr 2026), Hebbia ~$159M raised, Daloopa **$47M Series C**
  (May 2026), Brightwave $21M.
- **Retail AI price ceiling: Robinhood Cortex is bundled into Gold at $5/mo.** That is what any retail
  AI-research product now competes against. Meanwhile **Koyfin holds $39–79/mo with reportedly zero
  AI at any tier and is not losing share — AI is a feature, not a category.** IBKR added ChatGPT and
  Grok on 22 Jun 2026; TrendSpider caps AI at **25 messages/month on every plan**.

**AI-reliability findings that validate the desk's Auditor-veto + no-lookahead rules:**
**FinanceBench scores ~89% with perfect retrieval but fails 80%+ of the time under realistic
enterprise RAG; across 8 realistic configurations, 47% correct / 26% incorrect / 27% failure.**
**Numerical errors are silent**, and **multi-document reconciliation — comparing two 10-Ks, or two
periods — is where most hallucinations originate**, which is *the core act of equity research*.
Frontier hallucination runs 3.1–19.1% by task. 51.3% of enterprises claim agents in production; only
~10% at scale. A documented failure: **Perplexity read a thin-coverage 10-K without applying the
"in thousands" denominator — wrong by 1,000× — then confidently narrated a 99.8% revenue collapse.**
Pakistani small caps are maximally thin-coverage. **The moat is always the proprietary dataset, never
the chat interface.** The category-wide complaint is **opacity** — Finviz backtests you cannot
inspect, Fintel screens that silently restate history, TIKR line items recategorized. Auditable
determinism is a marketable feature, not just a rule.

Other global tools, for the record: **Koyfin** Free/$39/$79/$209/$299 (~5,900 screener criteria);
**TIKR** Free/$24.95/$54.95/$119.95 (Capital IQ + Morningstar sourced, 30yr/40Q); **Finviz Elite**
$39.50/mo or $299.50/yr (~67 criteria, ~16yr daily backtests, single entry/exit); **Fintel** pricing
**[UNVERIFIED and self-contradictory across pages]**; **Wisesheets** $60/$120/$900 per year.
**Atom Finance is defunct** — its site 404s; acquired by Toggle AI ~15 May 2024. Any "$299/mo Togal
AI" figure in circulation is a name-confusion artifact; **do not cite it**.

### 3B.5 PSX data sources — the ceiling, sharpened

**The single highest-value lead: Capital Stake / StockIntel.** Describes itself as an "Authorized data
vendor of PSX" and is the only source found with a **documented REST + WebSocket PSX API**:
**1/5/15-minute OHLCV built from raw ticks**, dividend-adjusted and unadjusted EOD, financials and
ratios, and a dedicated **corporate announcements & payouts endpoint**. 30-day free trial, no card.
**Full API access is reportedly free with a partner-broker account** (Munir Khanani, Chase, Yasir
Mahmood, Zahid Latif Khan). **[UNVERIFIED: whether the free tier includes *historical* intraday.]**
**This is the one lead that could retire the "no multi-day intraday on any free PSX feed" ceiling.
It is worth a direct enquiry, not a footnote.**

Other local sources: SBP **EasyData** (7,000+ series, free, no API) · PBS weekly SPI in **both PDF and
Excel**, no API · Business Recorder publishes its own **BRIndex100 / BRIndex30**, a genuinely distinct
free dataset. Corporate actions: `dps.psx.com.pk/payouts` is authoritative but HTML-only; `B` = bonus,
`R` = right; **ex-date = book-closure start minus 2 working days**. Ownership is the weakest area —
CDC publishes nothing; the route is "Pattern of Shareholding" inside annual-report PDFs, plus SECP
eServices (PKR 200–3,000 **[UNVERIFIED]**); insider transactions are free at Sarmaaya. The
short-interest equivalent is NCCPL **MTS** (15% Financing Participation Ratio, daily MtM, ≤60 days)
and **MFS**, plus DFC open interest. **FIPI/LIPI from NCCPL, daily, history from 09 Dec 2015,
released ~18:00–19:00 PKT**, free mirrors at Sarmaaya and finhisaab. Broker-level volume is **not
available to an individual** — which is why the Stockbit "Bandar Detector" pattern cannot be copied
here. **NCCPL returned HTTP 403 to every fetch, so all NCCPL details above are [UNVERIFIED].** Both
`psxdata` and `psx-data-reader` work **by scraping PSX — free is not the same as permitted**.

**Retail / free feeds — three hard corrections to Part 5:**
- **Yahoo Finance has no PSX coverage at all.** Symbol search returns zero for `KSE 100`, `KSE100`,
  `OGDC`, `Habib Bank`, `Karachi`, `LUCK.KA`, `HBL.KA`; `Lucky Cement` returns only Taiwan's
  `1108.TW`; `Pakistan` returns only `XBAK.L/.DE/.DU/.MU/.HM` (Xtrackers MSCI Pakistan Swap ETF),
  `GPAK` (US OTC) and `^958600-PKR-NETR`. **There is no `.KA` suffix in Yahoo's symbology — treat any
  `.KA` claim as folklore.** `yfinance` inherits the gap. ⚠️ **This contradicts Part 5's claim that
  `history_deep/` is "Yahoo-sourced". Check the repo's actual fetch script before asserting either
  way — one of the two statements is wrong and it matters for provenance.**
- **TradingView's 15-minute delay is now proven, not assumed.** The scanner returns
  `{"s":"PSX:LUCK","d":["LUCK",443.49,"delayed_streaming_900",…]}` — **900 seconds**, with the
  underlying provider `sixgroup` (SIX Financial Information), **not PSX direct**. Full PSX coverage
  exists (`source2: {"id":"PSX","name":"Pakistan Stock Exchange"}`, PKR, ISINs — LUCK =
  `PK0071501016`), and `tradingview-ta` was verified live on this machine
  (`TA_Handler(symbol='LUCK', screener='pakistan', exchange='PSX', interval=INTERVAL_1_DAY)` →
  `close=443.49`, `{'RECOMMENDATION':'SELL','BUY':4,'SELL':12,'NEUTRAL':10}`, byte-identical to the
  delayed scanner value). But **real-time PSX is not purchasable on TradingView at any tier**
  (absent from their data-coverage catalogue; moderate confidence, absence-of-listing evidence).
  Plans $12.95/$29.95/$59.95/$199.95 per month billed annually.
- Investing.com covers KSE-100 and PSX equities but has **no public API** (`investpy` dead, direct
  requests 403) and forbids reproduction without written permission. **Trading Economics** carries
  KSE100 at 176,926.75 on 31 Jul 2026 (+1,378.77, +0.79%), history to 1994, ATH 191,032.73 (Jan
  2026) — **but tracks it via CFD contracts referencing the benchmark, not the exchange print**, a
  real caveat for a desk that needs official closes; API pricing is unpublished ($149/$299 per month
  figures are **[UNVERIFIED]**). **FT does not carry KSE100.** WSJ 401'd — can neither confirm nor
  deny. **Barchart: no evidence of PSX**, and on Barchart/Nasdaq symbology **`PSX` means Phillips 66
  (NYSE)** — a live collision risk in any code that assumes otherwise. Cboe Indices: no Pakistan.

### 3B.6 Paid data vendors — who actually sells PSX, and the licence wall

| Vendor | PSX? | Code | Entry price | Notes |
|---|---|---|---|---|
| **EODHD** | **Yes, verified** | `KAR` / `.KAR`, MIC XKAR | **$19.99/mo** (All World) | 763 tickers, EOD + splits + dividends + partial fundamentals |
| **Finnhub** | **Yes** | `.PK`, MIC XKAR | **$199.99/mo** (Professional) | EOD daily OHLC only; intl OHLC is top-tier only |
| **Twelve Data** | **Yes, verified** | MIC XKAR | **$229/mo** (Pro) | Delayed EOD only; best session-calendar metadata found |
| **Databento** | Reference data only | no XKAR dataset | $199/mo commercial | Corporate actions + security master only — worth a sales email |
| FMP | **[UNVERIFIED]** | — | $99/mo Ultimate | No published exchange list; call `/stable/available-exchanges` with a key to settle it |
| Alpha Vantage | No evidence | — | — | Pakistan absent from published suffix list |
| Marketstack | **No, verified absent** | — | — | Enumerated all 64 exchanges; XKAR not among them |
| Intrinio | No evidence | — | — | US-centric feeds only |
| Polygon / Massive | **No** | — | — | US-only; rebranded to Massive on 30 Oct 2025 |
| Tiingo | **No, verified** | — | — | Downloaded `supported_tickers.zip`: 107,714 rows, PKR = 0 |
| Norgate | No | — | — | US/AU/CA only |
| Nasdaq Data Link | No | — | — | EDI Asian EOD covers 9 exchanges, no XKAR |

**EODHD detail** (best fit by a wide margin): verified live at `eodhd.com/exchange/KAR` — Karachi,
MIC **XKAR**, PKR, **763 active tickers**; and at `eodhd.com/financial-summary/LUCK.KAR` — live quote
₨440.0351 (30 Jul 2026), 52-week 339–529.5, **EPS 13.0186**, **ISIN PK0071501016**, sector Basic
Materials, FY-end June. Note `MarketCap: 0` and `Description: null` — **fundamentals are only
partially populated for PSX**. Their published PSX hours (Mon–**Fri** 09:30–15:30) **do not match the
real PSX schedule** in CLAUDE.md, so treat EODHD's calendar metadata as unreliable. Tiers: Free $0 /
All World **$19.99/mo or $199/yr** / All World Extended $29.99/mo (needed for intraday + the
hours/holidays API) / Fundamentals $59.99/mo / All-In-One $99.99/mo. History depth for KAR is
**[UNVERIFIED]** — the "30+ years" claim is generic marketing.

**⚠️ The licence wall — this is the finding that matters most.** **Every vendor that covers PSX grants
personal-use rights only.** EODHD's terms bar non-professional users from "Selling, reselling,
retransmitting, redistributing, displaying, or granting access to the Information" **in original or
modified form**, and state that they "are required to report all commercial users of exchange data to
the relevant exchanges." Twelve Data requires a **Redistribution Rights Add-On** and warns of exchange
fees, professional-subscriber rates, record-keeping and regulatory audits. FMP: "Displaying or
redistributing data sourced from FMP requires a specific Data Display and Licensing Agreement." Even
**Finnhub's $3,500/mo All-In-One reads "License: Personal Use."** **There is no way to buy out of the
PSX licensing problem from a Western vendor at a published price.** The only routes are PSX's own
Data Services Vending or a local licensed redistributor — which converges exactly with the Capital
Stake / StockIntel lead in §3B.5. **Any paid-plans productization must resolve this first.**

---

## Part 4 — Recommended build order

Ordered by value delivered per unit of work.

**Wave 1 — surface what already exists (no new data, no new cost)**
1. Dossier tab (§1.1) — 464 names, ~10× coverage
2. Per-stock pattern hit-rates (§1.2)
3. Liquidity capacity line (§1.3)
4. Earnings / ex-div countdown (§1.6)
5. Fix the two bugs in Part 2

**Wave 2 — trust and differentiation**
6. `verify.json` honesty badge (§1.4)
7. Correlation peers (§1.5)
8. Cycle uptime strip (§1.9)
9. Wire the `reviewer` agent into a cycle prompt so `learnings.json` stops being empty

**Wave 3 — borrowed from the global category**
10. Unified multi-axis score across all 464 dossier names (Snowflake-equivalent)
11. Reader-configured screener over pattern + fundamental + liquidity fields
12. Shariah / KMI-30 compliance filter
13. Paper-portfolio mode

**Wave 4 — needs upstream work**
14. PSX-native candles from `ohlc_daily/` (§1.8) — grows as the file accumulates
15. Regime-conditional astro panel (§1.11)
16. Broker league table — blocked on sample size, not on code (Q4 2026 per `SOCIAL_PLAN.md`)

---

## Part 5 — Hard ceilings

State these before anyone plans around them.

- DPS EOD provides `date, close, volume, open` only — **no high, no low**.
- Full OHLCV exists only in `history_deep/`, and only for **122 of 470** names (25 refreshed per
  run), Yahoo-sourced.
- **No multi-day intraday exists on any free PSX feed.** Real 4H/1H charts are impossible without a
  paid data licence. Do not promise them.
- Fundamentals have no multi-year history, no balance sheet, no cash flow, no company description.
- No API keys anywhere — every source is a public scrape.
- The PSX market-data licence is **not held**. That is a separate commercial track and is not
  closed by any product change.

Coverage funnel, for sizing any feature honestly:
`575 → 475 → 467 → 464 → 463 → 370 → 229 → 206 → 166 → 164 → 122 → 43 → 36`

---

## Sources

- [Top 10 PSX Apps in Pakistan 2026](https://qwhosting.com/top-10-psx-apps-pakistan-2026/)
- [Best Stock Investing Apps in Pakistan 2026: PSX & US Stocks](https://digitalpakistan.pk/best-stock-investing-apps-in-pakistan-2026-psx-us-stocks/)
- [Investify — Pakistan Stock Market App](https://www.investify.pk/)
- [iInvest Pakistan Stocks (PSX)](https://apps.apple.com/us/app/iinvest-pakistan-stocks-psx/id1090462694)
- [6 Best Stock Research Platforms in 2026](https://www.streetinsider.com/Press+Releases/6+Best+Stock+Research+Platforms+in+2026:+The+Complete+Guide+for+Modern+Investors/26833983.html)
- [Best Alternatives to Simply Wall St for Stock Research in 2026](https://www.gainify.io/blog/best-alternatives-to-simplywall-stock-research)
- [Koyfin Review (2026)](https://traderhq.com/koyfin-review-best-investment-analysis-tool/)
- [Simply Wall St vs Koyfin](https://quantroutine.com/tools/simply-wall-st-vs-koyfin/)
