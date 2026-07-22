# Website brief — what the desk actually is, as of 2026-07-22

**Who this is for:** whoever edits henneth.app. Every statement below was read out of the running
terminal (`dashboard/app.js`), the pipeline (`scripts/`) or the config today — not from the
existing marketing copy, which is what we are checking.

**How to use it:** §5 is the actionable part. It lists places where the site currently claims
something the product does not do, or fails to mention something it now does. §1–§4 are the ground
truth those corrections rest on.

**One rule above all others:** if the data layer does not have it, the site does not claim it.
That is CLAUDE.md Rule 2 and it applies to marketing exactly as it applies to the desk.

---

## 1. The positioning, in one paragraph

Henneth is a **publication**, not an advisory service. It publishes scheduled, impersonal market
research that is byte-identical for every subscriber. It does not know the reader, does not tailor
output to them, does not manage money, does not execute, and does not tell anyone what to buy.

The three tests every surface passes (see `docs/PUBLICATION_RESTRUCTURE.md`):

1. **Scheduled** — ships on a fixed calendar, not on demand.
2. **Impersonal** — identical for every subscriber.
3. **General circulation** — open subscription, not a client relationship.

This framing is not cosmetic and it is not optional. Copy that implies bespoke analysis, personal
recommendations, or work performed on request undoes it. §5 lists three places the current site
does exactly that.

**The one deliberate exception:** personal astrology (birth chart → sector and commodity
affinities) is personalised by construction. It is kept, disclaimed on every surface, and is the
item most likely to attract scrutiny. Do not lead with it as though it were investment guidance.

---

## 2. What is actually in the terminal

28 routes. Grouped as the product presents them.

| Surface | What it genuinely does |
|---|---|
| **Today** | The desk's plain-English daily read: tone, favoured/avoided sectors, short watchlist. Written once per day, same for everyone. |
| **Board** | Whole-universe heatmap, backtested signals, predictability ranks, news wire. |
| **Ticker page** | Per-name: chart, business scorecard, fair value four ways, Desk Room debate, broker calls, risk profile, dividends, news. |
| **The Desk Room** | Five personas (chartist, fundamentalist, bull, bear, chair) debate a name; the Chair issues a house view with explicit dissent. **Published on the desk's own editorial rotation — not run on request.** |
| **Value** | Every covered name valued four ways with the full working shown. |
| **Strategies** | ~52 rule-based strategies, each backtested on a stock's own ~19-year history. |
| **Screener** | Plain-English query over the desk's scored fields. |
| **Scenarios** | Oil / rupee / global-tape moves mapped to sector betas, with R² attached. |
| **Compare** | Two-plus names side by side. |
| **Macro** | Global tape, SBP path, rupee, geo-risk radar, measured sector drivers. |
| **News** | PSX announcement wire, tagged to tickers, impact-scored 1–5. |
| **Dividends** | Announced payouts, buy-by/ex dates, and the yields actually delivered. |
| **Calendar** | Results dates, marked verified vs scraped-estimate. |
| **Research** | Broker notes, filings and briefings digested, each claim extracted for public scoring. |
| **Scores** | Dated calls — the desk's own and the brokers' — graded against what prices did. |
| **Sectors** | Sector-level dossiers and debates. |
| **Astro** | Computed sky, what tradition claims, and what survived testing. |
| **Your Chart / Cast** | Personal birth chart read against the market. Open without an account. |
| **Watchlist / Portfolio** | Tracking, plus the desk's rules shown against your holdings. |
| **Practice** | Virtual Rs 500,000 book at real prices. |
| **Learn** | 14-lesson path for a first-time investor. |
| **Tools** | Calculators — see §5.3, the current site names four that do not exist. |
| **Ask** | Plain-English question answered from the desk's own computed files. |

**New today and not yet reflected anywhere on the site:**

- **US / global coverage** — 23 index and sector-ETF symbols (S&P 500, Nasdaq 100, Dow, Russell,
  VIX, the eleven SPDR sectors, EEM/EFA/ACWI, TLT/HYG/GLD/USO). Research-tier only: the desk
  covers them, quantifies them and will read astro against them, but **does not signal on them**.
- **`/tools/position-size-calculator/`** on this site — the reader's own capital, the desk's Rule 4.
- **`/financial-astrology/`** on this site — the public, lighter astro lens.

---

## 3. Plans — the honest state

`BILLING_LIVE = false`. There is no payment gateway (Stripe is unavailable in Pakistan), and plan
is DB-frozen against client writes, so choosing a plan cannot grant it. **Every signed-in account
currently behaves as Pro.** The site's early-access framing is correct and should stay until that
changes.

| Tier | Reality |
|---|---|
| Free | Every account starts here. Cast a chart, read the daily note, follow the public record. |
| **Investor** | Learn, practice, tools, full astro, full dividends, full earnings. |
| **Pro** | Everything above plus value, strategies, research library, screener, scenarios, scanner, watchlist intelligence, Ask, alignment, portfolio X-ray, marketplace. |
| **Broker** | **Unbuilt.** Feature list deliberately empty. Do not describe its contents. |

---

## 4. House rules that constrain copy

- **Long only.** No shorts, no leverage, no derivatives, daily timeframe.
- **The desk never places an order.** Execution is always manual, by the reader.
- **No advice language.** "The setup", "the desk's read" — never "you should buy".
- **Nothing fabricated.** Where the data layer is silent the product says unknown.
- **Losses are published.** Misses stay on the record.
- **Astrology is tested, never predictive.** 2,589 hypotheses, 101 subjects, 4,893 trading days,
  **zero survivors** after multiplicity correction. The site already publishes that zero. Keep it.

---

## 5. Corrections needed — the actionable list

### 5.1 Three overclaims to fix

**a. Tools that do not exist.** `features.astro:61` says *"PSX-specific calculators — position
size, CGT, dividend yield, break-even."* The terminal's Tools page has **compound, SIP, inflation,
dividend-reinvestment, savings goal, mortgage, zakat**. None of the four named are there.
*Position size* now exists — but on this website, not in the desk. **Fix:** name the seven real
ones, and link position size to `/tools/position-size-calculator/`.

**b. The marketplace is not live.** `features.astro:39` says *"Strategies published with their full
record attached, good and bad."* The terminal's own page says publishing **opens once** every
submission can be backtested. It is a build-and-test surface today, not a marketplace.
**Fix:** describe it as composing and testing a strategy; say publishing is coming.

**c. Portfolio "correlated risk".** `features.astro:47` claims positions are X-rayed for
*"concentration, sector overlap and correlated risk."* The X-ray computes weighted beta, blended
yield, expected dividends, gap vs fair value, and three rule checks. There is no correlation
analysis in it. **Fix:** drop "correlated risk" or replace with what is actually shown.

### 5.2 Positioning language to change

**d. Nothing on the site states the publishing schedule.** The schedule is load-bearing for the
publication frame — it is the difference between a periodical and a service. **Add it plainly:**
the desk publishes pre-market daily (~08:45 PKT), monitors intraday, and the Desk Room publishes on
a weekly rotation.

**e. Avoid "run" / "on demand" verbs.** The terminal was itself corrected today: buttons that said
*"Run the desk on FFC"* now say *"The desk's debate on FFC — Published · <date> — Read ›"*, because
nothing was ever run on request. Site copy should match: readers **read** published research, they
do not commission it.

**f. Broker tier.** The site says *"For desks and institutions. Details on request."* — correct,
keep. The terminal's internal blurb promises more; ignore it, it is unbuilt.

### 5.3 Things to add

**g. Global coverage.** The site is positioned as PSX-only. It is now *"a global-markets
publication that covers PSX in depth"* — that is the accurate description and the better one. Be
precise: index and sector level, research and context, **no US stock picks and no US signals.**

**h. The two new pages** need entry points beyond the nav: `/financial-astrology/` and
`/tools/position-size-calculator/`.

**i. The position-size story is good positioning.** The desk used to publish a share count against
its own capital and deliberately stopped, moving it to a calculator the reader drives. That is a
concrete, checkable illustration of "research, not advice" — worth telling rather than burying.

### 5.4 Do not "fix" these — they are correct as they stand

- *"Conditions with a proven edge: 0"* — the published astro null result. It is the differentiator.
- *"Show the method, not a number — a track record you can't check isn't a track record."*
- *"There is nothing proven to charge for."*
- The absence of win rates, returns and hit rates in headlines. Deliberate. Do not add them.
- **"Proven" as a product adjective was removed today** (now "backtested"). Do not reintroduce it.

---

## 6. Words to avoid

**Never:** recommendation · buy/sell call · tip · signal to act · advice · guaranteed · assured
returns · "our picks" · anything implying a personal relationship with the reader.

**Prefer:** the desk's read · the setup · published research · tested · backtested · scored ·
the house view · research, not advice.

---

## 7. Open items the site must not get ahead of

- `state/legal.json` is **`review_status: DRAFT`** — not yet reviewed by a Pakistani lawyer. No
  pricing may go live before that.
- No payment gateway exists.
- The public track record is still filling; most dated calls have not reached their horizon.
- US coverage is days old. Describe it as coverage and context, not as a track record.
