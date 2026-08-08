# Comparison pages — plan

Status: **plan only.** Nothing here is written yet. This file is the spec a content run reads
before drafting; it is not itself content.

Process: [CONTENT_ROUTINE.md](CONTENT_ROUTINE.md) · Queue: [CONTENT_BACKLOG.md](CONTENT_BACKLOG.md)
· Strategy: [SEO_PLAN.md](SEO_PLAN.md)

---

## Why this exists

Comparison articles are roughly a third of everything AI answer engines cite — the single largest
content category by citation share, ahead of blogs, news and product pages. The site currently has
**zero**. Someone asking ChatGPT or Perplexity "what should I use to research PSX stocks" gets an
answer assembled from whoever *did* write the comparison. Henneth is not in the room.

The same pages serve two distinct demand shapes that the existing content misses entirely:

- **Category queries** — "best PSX stock screener", "PSX research tools". High intent, low
  competition in this market, and no page on the site targets them.
- **Alternative queries** — "Sarmaaya alternatives", "FinHisaab vs X". Lower volume, but the
  visitor has already decided they want a tool and is comparing. Closest thing to a qualified
  arrival the site can get for free.

## The hard constraint that shapes everything below

These pages name real, named competitors — small companies run by real people in the same city.
That makes them the highest-liability content on the site, and the rules are tighter than for a
blog post:

1. **Every claim about a competitor is a verified observation with a date.** "As of
   2026-08-09, Sarmaaya's screener exposed N metrics" — checked that day, on the record, with the
   URL. Never a remembered feature list, never an inference from marketing copy.
2. **No disparagement.** Describe what each tool does and who it fits. A tool being wrong for one
   reader is not a defect. If a sentence would embarrass the desk if the competitor's founder read
   it aloud, cut it.
3. **Concede honestly where a competitor is better.** This is not politeness — it is the mechanic
   that makes the page citable. A comparison that concludes "we win on everything" is read as
   marketing by both humans and models, and gets discounted accordingly. Henneth is *worse* than
   several of these on raw metric count and on coverage breadth, and saying so plainly is what
   makes the paragraph where it is better believable.
4. **CLAUDE.md Rule 5 still binds.** No advice language anywhere, including about competitors.
5. **A dated "verified on" line at the top of every comparison table**, plus the standing
   `dateModified`. Comparison content decays faster than anything else on the site; an undated
   feature table is a liability the moment a competitor ships.
6. **Re-verification is scheduled, not aspirational.** Any page here that has not been re-checked
   in **90 days** is stale. See the maintenance section.

## The competitor set

Verified as live and relevant on 2026-08-09 by search; feature detail is **not** yet verified and
must be checked page-by-page during the drafting run.

| Tool | URL | Shape |
|---|---|---|
| PSX Data Portal (DPS) | dps.psx.com.pk | The official source. Free, authoritative, deliberately unopinionated. |
| Sarmaaya | sarmaaya.pk | The incumbent generalist. Broadest brand recognition in Pakistan. |
| FinHisaab | finhisaab.com | Free screener, claims 230+ fundamental and 60+ technical metrics. |
| StockIntel | stockintel.com | Filings-led — searchable annual reports and quarterlies, peer metrics. |
| Ticker Analysts | tickeranalysts.com | Screener plus AI-generated report insights. |
| AZEE Stock Analytics | azeetrade.com | Broker-attached analytics; dividend and trader screens. |
| KSEStocks | ksestocks.com | Long-running data/community site. |
| Mettis Global | mettisglobal.news | News and terminal, more institutional than retail. |

Henneth's honest position in that set: **not the broadest data, not the cheapest, not the most
metrics.** What no one else in the list publishes is a *scored track record* — dated, falsifiable
claims marked right or wrong in public, including the desk's own null results, and the same
yardstick turned on Pakistani brokers' calls. That is the differentiator every page below is built
around, because it is the only one that is actually true.

---

## The three pages

Build in this order. Page 1 earns the category query and is the hub; pages 2 and 3 hang off it.

### 1. `/compare/psx-research-tools/` — "PSX research tools compared"

The hub, and the one that matters most. Targets the category query directly.

- **Lead with the answer.** First 60 words state which tool fits which reader, before any table.
  This is the block an AI answer engine lifts; burying it under an intro paragraph forfeits the
  citation.
- **One comparison table**, every tool in the set, columns chosen so each has a genuinely
  different winner: price · coverage · screener depth · filings access · published track record ·
  account required · API/export.
- **One short section per tool**, three or four sentences: what it is good at, who it fits, one
  honest limitation. Same length for every tool including Henneth — an obviously longer own-section
  is the tell that turns a comparison into an ad.
- **"How we picked" section** — the criteria, stated before the verdict, so the ranking is
  auditable rather than asserted.
- **FAQ block** with FAQPage schema. Existing pattern, already implemented sitewide.
- Internal links: every named alternative to its own page where one exists; `/psx/` hub; `/tools/`;
  `/research/` (the track-record claim must be clickable, or it is just a claim).

### 2. `/compare/sarmaaya-alternatives/` — "Sarmaaya alternatives"

Targets the alternative query. Sarmaaya has the most brand search volume in the set, so it is the
one worth a dedicated page.

- Opens by saying plainly what Sarmaaya is good at and who should just keep using it. A
  "alternatives" page that will not name a case for the incumbent is not credible.
- Then: five alternatives, each with the reader it actually suits. Henneth is one of five, not the
  conclusion.
- Explicit "stay with Sarmaaya if…" section. Costs nothing, and it is the section that makes the
  rest readable.

### 3. `/compare/free-vs-paid-psx-research/` — "Free vs paid PSX research"

The pricing-intent query, and the one where the site's current position is a genuine asset: DPS is
free and authoritative, most of the set has a free tier, and Henneth is free in early access. The
page can be straight about what is worth paying for without pitching anything, because there is
currently nothing to pitch. Links to `/pricing.md` and `/plans/`.

---

## Structure and implementation

- **New route family `/compare/`**, mirroring `/solutions/` — Astro pages under
  `site/src/pages/compare/`, plus a `/compare/` index so the family is not orphaned (the exact
  failure already fixed for `/psx/`).
- **Footer link to `/compare/`** in the Product column, same pattern as `/psx/` and
  `/global-markets/`. Nav stays capped at 7.
- **Reuse the existing `Matrix` component** for the tables — the comparison-table markup is already
  built and already renders as extractable static HTML.
- **Schema:** `ItemList` over the compared tools, plus `FAQPage`, plus the standard `Article`/
  `BreadcrumbList` the layout already emits. `Product`/`Review` markup is deliberately **not**
  used — review schema on self-authored competitor comparisons is exactly the self-serving-review
  pattern Google's structured-data guidance excludes.
- **Add `/compare/` to `llms.txt`** under a new "Comparisons" section when page 1 ships.
- Every page carries the "Verified on YYYY-MM-DD" line and a one-line note that the desk is one of
  the tools compared. Undisclosed self-inclusion is the fastest way to lose the page's credibility
  and, if a reader complains, more than that.

## Drafting run — gates

In addition to the five standing rules in CONTENT_BACKLOG.md:

6. **Visit every competitor site in the run and record what was seen.** Pricing, feature list, free
   tier, account requirement. No feature claim survives without a same-run observation.
7. **No competitor claim from memory or from a third-party listicle.** Both are wrong often enough
   to be worthless, and being wrong about a named competitor is the specific failure that makes
   this content dangerous.
8. **Read the rendered page** before publishing (standing rule 3 — the build passes on visibly
   broken layouts, twice now).

## Maintenance

- Re-verify all three pages **every 90 days**; update the "Verified on" date only when the check
  actually ran.
- If a competitor materially changes pricing or shuts down, fix the page that week — a comparison
  page that is wrong about a live competitor is worse than no comparison page.
- Track in GSC as a group: impressions on "best PSX…" and "…alternatives" queries are the signal
  these pages are working. Citation in AI answers is the actual goal and is not directly
  measurable; treat referral traffic from chat.openai.com / perplexity.ai in GA4 as the proxy.

## Deliberately not doing

- **No `henneth-vs-<competitor>` head-to-head pages.** They read as combative, they are the format
  most likely to draw a complaint, and a site with four blog posts has not earned the standing to
  put its name beside an incumbent's in a title. Revisit once the track record has resolved calls.
- **No affiliate or referral links.** Nothing in the set offers one worth the credibility cost.
- **No auto-generated per-competitor pages.** Scaled comparison content is the exact pattern
  Google's scaled-content-abuse policy targets. Three pages, written and verified by hand.
