# Organic growth — the build plan

**Status:** approved by owner 2026-07-21. This is the execution doc.
**Read with:** [SEO_PLAN.md](SEO_PLAN.md) (SERP findings, YMYL guardrails, GSC loop) ·
[BLOG_PLAN.md](BLOG_PLAN.md) (cluster architecture, drafting pipeline) ·
[PSX_COSTS_VERIFIED.md](PSX_COSTS_VERIFIED.md) (every rate a page may quote) ·
[CLAUDE.md](../CLAUDE.md) (desk rules — Rule 2 and Rule 5 apply to published content).

**This doc supersedes SEO_PLAN.md §7 and BLOG_PLAN.md §4.4 on cadence only.** Everything else in
those two documents stands. See §7 below for why, and patch both files as instructed.

---

## 0. Verified starting position (2026-07-21)

Not estimates. Pulled from GSC and the repo on the date above.

| Fact | Value | Source |
|---|---|---|
| GSC property | `sc-domain:henneth.app`, siteOwner | GSC API |
| Property added | 2026-07-20 | GSC API |
| Sitemap submitted / indexed | **14 / 0** | GSC `listSitemaps` |
| Impressions, clicks, ranking queries (90d) | **0 / 0 / 0** | GSC `searchAnalytics` |
| Blog posts published | **0** | `site/src/content/blog/` does not exist |
| Blog engine | built and working | `[...slug].astro`, cluster enum, Article + Breadcrumb LD, TOC, related rail, honest `lastmod` |
| Tickers with a dossier | 444 | `state/dossiers.json` |
| Tickers fair-valued | 167 | `state/fairvalue.json` |
| Tickers predictability-ranked | 208 | `state/predictability.json` |
| Symbols with dividend history | 280 | `state/dividends.json` |
| Universe / with price history | 554 / 450 | `state/coverage.json` |

**Read this honestly:** the domain is invisible. Nothing is indexed. The content machine is fully
built and completely empty. Every number above that is zero is zero because no public page exists
worth crawling — not because of a technical fault.

---

## 1. The decision this plan implements

The desk gated everything behind an account on 2026-07-21 to protect a future paid product.
Correct instinct, wrong target. Three things were collapsed into one switch:

1. **Can Google see it?** (indexable)
2. **Does it need an account?** (email capture)
3. **Does it need payment?** (revenue)

All three are currently set to "account required," which turns off #1 — the only channel that
would ever produce customers for #3.

**The timing argument, which is the whole case.** SEO lag from a zero-authority domain is 5–8
months. Gate until month 6 and then open, and the clock starts at month 6: traffic lands month
12–14, and paid launches to an empty room. Open the public layer now and traffic lands month 5–6 —
exactly when billing goes live. **The gate and the paywall want opposite timelines.** Opening the
public layer now *is* the route to paying customers in six months.

### The three layers

| Layer | Account? | Indexable? | Contains | Job |
|---|---|---|---|---|
| **1 — Public** | No | **Yes** | Marketing site, blog clusters, calculators, thin ticker pages, `/cast`, broker league table | Rankings and links |
| **2 — Free account** | Yes | No | Watchlist, full daily read, full chart reading, Investor desk lessons, alerts | **Email addresses** |
| **3 — Paid (month 6)** | Paid | No (paywall schema) | Fair-value workings, strategy backtests, Desk Room, Scores, research library | Revenue |

Layer 3 never opens. The thin public ticker page is an advertisement for it, not a substitute:
a page saying *"FFC screens overvalued on three of four methods"* sells the workings, the debate
and the backtests — it does not replace them.

Signups are **not** removed. Layer 2 is the asset being built during the six months. It is
currently invisible because Layer 1 is empty and nobody arrives to sign up.

---

## 2. THE TECHNICAL RULE — read before writing any code

> **Publish rendered pages. Never publish the data layer.**
>
> `state/*.json` is the asset. Public JSON means a competitor rebuilds the terminal in a weekend.
> Public pages on `henneth.app` are **static HTML generated at build time** from a
> **narrowed extract** of `state/`. `desk.henneth.app` keeps auth on the JSON, unchanged.

This is enforced by architecture, not by discipline. Three sub-rules:

**2a. Never read `../state/` from the Astro build.** The `site/` Vercel project has Root Directory
`site/`, so files above it are excluded from the build unless the "Include source files outside of
the Root Directory" setting is enabled. **Do not enable it.** That setting would put the entire
93 MB data layer inside the marketing build, one misconfigured route away from being served.

**2b. A generator script produces a whitelisted extract.** Write
`scripts/build_public_slice.py`. It reads `state/*.json`, selects **only** the fields in the
whitelist below, and writes `site/src/data/public/tickers.json` — committed to git, so the Astro
build is hermetic and reads nothing outside `site/`.

**2c. The whitelist is an allow-list, never a deny-list.** The script names the fields it copies.
A new field added to `state/` in future is excluded by default. A deny-list would leak it silently
on the next cycle. This is Rule 2 of `CLAUDE.md` applied to publishing: if it is not explicitly
allowed out, it does not go out.

### The public whitelist

Publish per ticker:

- Symbol, company name, sector
- Listing date
- Liquidity tier (`research` / `signal` / neither) — the *label*, not the estimator values
- Fair-value **verdict only** — one word plus how many of the four methods agree. **Never** the
  four method values, the inputs, or the workings.
- Dividend history: dates and amounts (already public record via PSX/CDC)
- A 120–150 word plain-English read
- Last-updated date

Withheld — Layer 3:

- Every fair-value method value, input and working
- Predictability score and rank
- Any backtest result, win rate, expectancy or strategy name
- Desk Room debate content, Chair view, dissent, dated calls
- Scores / claims / broker per-call data
- Anything from `fundamental_scores.json`, `correlation.json`, `liquidity.json` estimators

**Do not guess field names.** Inspect the actual shape of each `state/` file before writing the
extractor, and fail loud on a missing expected field rather than emitting a partial page. A ticker
whose data is incomplete is **skipped**, not published with gaps.

### Two rules inherited from CLAUDE.md that bind public pages

- **Rule 2 — no number from memory.** Every figure on a public page comes from the extract. If
  the extract lacks it, the page says nothing. Never "approximately."
- **Rule 5 — no advice language.** These pages describe and explain. No "buy," no "undervalued,
  so." The platform disclaimer and the "Research · not advice" badge appear on every generated
  page, same as everywhere else.

---

## 3. START HERE — the first block

Do these in order. Report after each and wait for go-ahead. Nothing here touches `state/`,
`dashboard/`, or the desk pipeline.

**Block 0 — verify, don't assume (~20 min).**
1. Confirm `henneth.app` marketing pages, `/blog/`, `/tools/*` and `/cast` are reachable with no
   account. Report anything that is gated — that is a bug against this plan.
2. Confirm `desk.henneth.app/robots.txt` still allows crawling and pages still carry
   `<meta robots="noindex">`. Do not change it; the comment in that file explains why.
3. Confirm the `site/` Vercel project does **not** have "Include source files outside of the Root
   Directory" enabled. If it does, report before changing anything.

**Block 1 — the extract (~1.5 h).**
Write `scripts/build_public_slice.py` per §2. Idempotent, safe to re-run, network-free, exits 0.
Output `site/src/data/public/tickers.json`, committed. Start with **20 symbols** — the most liquid
and most searched: OGDC, PPL, PSO, HUBC, FFC, ENGRO, ENGROH, LUCK, DGKC, MLCF, HBL, UBL, MCB, MEBL,
BAFL, SYS, TRG, NESTLE, PAKT, INDU. Verify by eye that the JSON contains nothing from the withheld
list. **Done when:** the file exists, holds exactly 20 entries, and a `grep` for any withheld field
name returns nothing.

**Block 2 — the page template (~2 h).**
`site/src/pages/psx/[ticker].astro`, statically generated via `getStaticPaths()` from the extract —
same pattern `[...slug].astro` already uses for blog. Requirements:
- Canonical `/psx/<ticker>/` with trailing slash, matching `Base.astro`'s existing normalisation.
- `FinancialProduct` or `Corporation` JSON-LD plus `BreadcrumbList` (Home > PSX > Ticker).
  `isAccessibleForFree: true` while these pages are open.
- Visible last-updated date. This is a YMYL surface (SEO_PLAN.md §4) — dated and sourced or it
  does not ship.
- Internal links: to its sector hub (stub for now), to two sibling tickers, to a relevant
  `/tools/*` calculator, and one CTA into the desk. Internal linking is most of what makes this
  work — see BLOG_PLAN.md §1.
- Reuse existing components and design tokens. No new visual language; `design_lint` rules apply.

**Block 3 — index it (~30 min).**
Confirm the 20 URLs appear in `sitemap-0.xml` after build. Submit nothing new to GSC — the
sitemap index is already submitted and will be re-read. Then use GSC URL Inspection → Request
Indexing on **5** of the 20 by hand. (Note: the Google Indexing API is officially JobPosting and
BroadcastEvent only; it does not apply here. IndexNow is Bing/Yandex. Manual request is the
sanctioned path and it is rate-limited to roughly ten a day.)

**Block 4 — start Cluster 1 in parallel (~ongoing).**
Begin the Market structure cluster exactly as BLOG_PLAN.md §2 specifies, pillar first:
*How PSX settlement works: T+1 explained.* The T+1 correction (verified 9 Feb 2026, primary
sourced) is a provable freshness win against a SERP that is still teaching T+2 — **and it expires
the moment competitors update.** Full drafting pipeline: `psx-content-drafter` →
`psx-fact-checker` → `psx-voice` → `draft: true` → human review → publish. The fact-check gate is
not negotiable and outranks any schedule.

**Do not start Phase 2 until Block 3's pages have been live three weeks and GSC has been checked.**

---

## 4. The six-month plan

| Phase | Window | Build | Success test |
|---|---|---|---|
| **1** | Weeks 1–4 | Blocks 0–4. Cluster 1 (4 posts) + the 20-ticker pilot + PSX trading-cost calculator (SEO_PLAN.md §2 priority 1 — both KTrade's and Sarmaaya's ship broken) | **Indexed count > 0.** Nothing else matters yet. |
| **2** | Weeks 5–8 | Wait, then read GSC. If the 20 index and gather impressions, the template is validated. Sector hub pages (`/psx/sector/<sector>/`) as pillars linking their tickers. Cluster 2 (Costs and tax) — gated on PSX_COSTS_VERIFIED.md | ≥15 of 20 indexed; first non-brand impressions |
| **3** | Months 3–5 | Scale to ~450 tickers in tranches of ~50/week, ordered by the research liquidity gate. **Split sitemaps per tranche** so GSC reports indexation rate per batch. CGT calculator once FBR Circular 01 of 2026-27 lands (~Aug 2026) | Indexation rate holding above ~70% per tranche. If it drops, **stop scaling** — that is Google saying the pages are thin |
| **4** | Months 5–6 | The GSC loop (SEO_PLAN.md §5) becomes the main job: filter position 5–20, sort by impressions, improve those pages. Quarterly Broker League Table for press | Traffic compounding; email list growing |
| **5** | Month 6 | Layer 3 paywall goes live. See §5 | Paying customers |

**Judge month 3 on impressions and average position, not sessions.** Traffic is a lagging
indicator and quitting early on a working strategy is the standard failure mode.

Realistic end state: **~500 indexed pages of defensible, proprietary content by month 5.** The
alternative route — 100–200 AI-written posts a day — reaches a site-wide quality classification by
month 2 and takes the calculators and the T+1 win down with it.

---

## 5. When the paywall goes live (month 6) — do it the sanctioned way

Do not hide content from Googlebot ad hoc. Serving Google something users cannot see is cloaking
and carries a manual action. Google's official mechanism is **Flexible Sampling**, in two forms:

- **Metering** — N free page views per month, then the wall.
- **Lead-in** — a meaningful portion visible, the rest gated.

Pair it with **paywalled-content structured data**: `isAccessibleForFree: false` plus a `hasPart`
block whose `cssSelector` marks the gated section. That is what tells Google the difference between
crawler and user is a paywall rather than a trick.

**Flag for that day:** `[...slug].astro` currently emits `isAccessibleForFree: true`, and
`Base.astro` emits a `price: '0'` Offer gated on `site.earlyAccess`. Both are correct today. Both
must flip when billing goes live, or the structured data advertises a free product that charges.

---

## 6. Free traffic that is not Google

Ordered by return, all zero spend.

1. **Be the source — highest leverage item in this document.** The broker call scorecard is not an
   SEO asset, it is a *press* asset. Nobody in Pakistan publicly scores broker calls against what
   prices actually did. Package it quarterly as a **Broker League Table**; pitch Profit, Dawn,
   Business Recorder, Mettis. One pickup outweighs fifty posts and is the only realistic free route
   to authoritative links.
2. **Calculators are link bait; articles are not.** People link to tools. Cost calculator, CGT
   calculator, dividend buy-by-date checker.
3. **X (@MWasayI)** — the tweet pipeline and `tweet-voice-check` gate already exist. Daily desk
   read → thread. Zero marginal cost.
4. **Video** — the Desk Room replay is already a staged animated walkthrough. It is a built video
   asset that is not being distributed. PSX has close to zero good short-form.
5. **Google Discover** — the Article schema and `dateModified` are already correct for it. Discover
   can outrun search on a new domain.
6. **Answer where the questions are** — r/pakistan, PSX Facebook groups, X. Useful answers only.
7. **Newsletter** — the daily read as email. Owned audience, no algorithm.
8. **Never buy links.** A new domain cannot survive a bad profile.

---

## 7. Reconciling the cadence contradiction — do this, don't skip it

`SEO_PLAN.md` §7 and `BLOG_PLAN.md` §4.4 both mandate *one good post per week* and both give the
correct reason: Google's helpful content system targets scaled unhelpful content and a new domain
has no buffer.

**That rule still holds — for the blog.** It never applied to programmatic pages, because those are
not scaled *content*, they are scaled *proprietary data*. Google penalises the first and rewards
the second. The distinction is whether a competitor could produce the page; nobody can produce a
Henneth ticker page without a 19-year backtest engine.

**Action:** add a one-line pointer to both files —
`> Cadence applies to blog posts. Programmatic ticker pages scale under docs/ORGANIC_GROWTH_PLAN.md §4.`
Do not delete or rewrite the existing cadence text. It is right, and a future reader needs to see
both rules and the boundary between them.

---

## 8. What would make me stop

Honest failure conditions, written down before the fact so they cannot be rationalised later:

- **Indexation rate per tranche drops below ~70%** → stop scaling. Google is saying the pages are
  thin. Deepen the template before adding more.
- **Manual action or sudden sitewide impression collapse** → the programmatic layer is the suspect.
  Pull it, keep the blog and calculators.
- **Ticker pages index but produce no signups by month 4** → the public slice is too thin to
  interest anyone, or too generous to need an account. Both are template problems, not strategy
  problems; re-cut the line.
- **A wrong tax or dividend number ships** → stop everything and fix the gate. Per SEO_PLAN.md §4,
  a wrong YMYL number costs the domain's credibility, which is the one thing that cannot be
  rebuilt by working harder.
