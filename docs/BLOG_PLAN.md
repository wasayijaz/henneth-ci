# Henneth blog — cluster architecture and publishing routine

How the blog earns organic traffic. Read with [SEO_PLAN.md](SEO_PLAN.md) (strategy, GSC loop) and
[PSX_COSTS_VERIFIED.md](PSX_COSTS_VERIFIED.md) (every rate a post is allowed to quote).

---

## 1. Why clusters, not a pile of posts

A new domain does not rank by publishing more. It ranks by proving depth on a **narrow topic**.

The mechanism is internal linking. A cluster is one **pillar** page covering a topic broadly, plus
**spokes** covering each sub-question in depth, all linked pillar↔spoke. Google reads that as
"this site covers PSX market mechanics thoroughly" rather than "this site has one page about
settlement". Authority earned by any spoke flows to the pillar and back out to its siblings, so
the cluster rises together instead of each post fighting alone.

Practical consequence: **finish a cluster before starting the next one.** Four half-built clusters
rank for nothing. One complete cluster ranks.

The post template already supports this — `[...slug].astro` picks related posts from the same
cluster and the TOC/breadcrumbs are automatic. The wiring exists; it needs the content.

### A cluster is 4–8 pages. It is NOT 100–200.

This is the most expensive misconception in SEO and it needs saying plainly, because the instinct
to scale is exactly backwards for this site:

- **Google's helpful content system explicitly targets scaled content production.** A domain with
  no history publishing 150 pages in a quarter is the pattern it looks for. There is no authority
  buffer to absorb a hit, and the classification is site-wide — it would drag down the good pages
  too.
- **Crawl budget.** Google will not crawl 200 URLs on a new site quickly. The realistic outcome is
  200 published, a few dozen crawled, and whatever authority is earned divided 200 ways instead of
  concentrated on 8.
- **Nothing gets deep enough to win.** The entire edge here is being right where competitors are
  wrong or absent, and that requires reading the actual PSX Regulations. That cannot be done 150
  times.

Target: **~10 blog posts plus the tool pages by month 4.** Ten genuinely good pages out-rank two
hundred thin ones on a domain this young, and it is not close.

**Where high page counts DO become legitimate — later.** A page per PSX company generated from
`state/`, carrying real model fair value, real dividend history and real strategy signals, is
programmatic SEO with an actual data moat, and few people in Pakistan could build it. But it needs
authority first, and it only works if each page carries genuinely differentiated data. A template
with a ticker swapped in is precisely the thin content that gets penalised. Phase 3, not now.

---

## 2. The clusters, in build order

Order is by *return per hour*, using the live-SERP findings in SEO_PLAN.md §1.

### Cluster 1 — Market structure `Market structure` ★ build first

**Why first:** the strongest position we will ever have. PSX moved T+2 → T+1 on 9 Feb 2026
(verified, primary) and effectively every ranking explainer still teaches T+2. "Spot rate PSX" and
"ready vs spot market" returned an outright vacuum — only generic FX dictionary definitions.
Being *right* beats being established when the established answer is provably wrong.

**This advantage is perishable.** It ends the moment competitors update.

| # | Page | Role |
|---|---|---|
| 1 | How PSX settlement works: T+1 explained | **Pillar** |
| 2 | Book closure, ex-date and buy-by, under T+1 | Spoke |
| 3 | Ready, spot, futures: PSX market types | Spoke |
| 4 | How the KSE-100 actually works (free-float, divisor, sector rule) | Spoke |

Sources: PSX Regulations v09-Feb-2026 Ch.10, NCCPL circular. Already verified.

### Costs and tax — NOT a blog cluster. It lives on the tool pages.

This was originally planned as a four-post cluster and that was wrong: a post at
`/blog/capital-gains-tax-on-shares/` and a calculator at `/tools/capital-gains-tax-calculator/`
target the *same query*. Two pages competing for one keyword split the signal rather than doubling
it — textbook cannibalisation, and self-inflicted.

**Resolution: one URL per topic, tool and explanation together.** `ToolPage.astro` already renders
a prose `<slot />` and an FAQ block beneath every calculator, so the explainer becomes the body of
the calculator page. Same content, half the URLs, no internal competition — and the prose is what
satisfies the YMYL bar that makes a tax page rank at all. A bare widget with no text ranks for
nothing.

So the verified material in PSX_COSTS_VERIFIED.md (brokerage as a *regulated range*, floor 0.15%
ceiling 2.5%; Sindh SST 15% **on commission, not turnover**; every published non-filer CGT figure
being wrong) ships as **richer tool pages**, not as posts.

⚠️ Every number still gated by PSX_COSTS_VERIFIED.md. No blog-sourced rates. Non-filer CGT gets the
mechanism and a range, never a single figure, until FBR Circular 01 of 2026-27 lands (~Aug 2026).

### Cluster 2 — Getting started `Method`

Beginner intent, feeds the Individual plan. SERP splits between dry official PDFs and broker
marketing; nobody writes the actual decision.

| # | Page | Role |
|---|---|---|
| 1 | How to start investing in the PSX | **Pillar** |
| 2 | CDC sub-account vs investor account: which to open | Spoke |
| 3 | What you need to open a brokerage account | Spoke |

### Cluster 3 — Valuation `Valuation`

Highest long-term value, hardest to win cold. Needs the authority the first three clusters build.

| # | Page | Role |
|---|---|---|
| 1 | How to value a PSX company | **Pillar** |
| 2 | Why PE ratios mislead on PSX cyclicals | Spoke |
| 3 | Reading a Pakistani company's accounts | Spoke |

### Later — `Sectors`, `Macro`, `Astro`

`Sectors` suits the Desk Room output. `Macro` and `Astro` exist in the icon map but have no
content plan yet; leave them until a cluster above is finished.

---

## 3. Taxonomy — keep code and content in sync

`cluster` is `z.string().optional()` in `content.config.ts`, so a typo (`"Market Structure"`) is
accepted silently, renders the fallback icon, and is unreachable from the filter chips. The chips
also list only 4 of the 6 clusters the icon map knows.

**Fix before publishing at volume:** make `cluster` a `z.enum([...])` so a bad value fails the
build instead of producing an orphan post, and derive the chips from the same list.

Canonical values: `Market structure` · `Method` · `Valuation` · `Sectors` · `Macro` · `Astro`

---

## 4. The publishing routine

### Per post

1. **Pick from the cluster in progress.** Never jump clusters — an unfinished cluster ranks for
   nothing.
2. **Verify every fact first.** Rates from PSX_COSTS_VERIFIED.md; anything else needs a primary
   source in hand *before* drafting. CLAUDE.md Rule 2 applies to published content.
3. **Draft** via `psx-content-drafter` — every factual claim flagged for the checker.
4. **Fact-check** via `psx-fact-checker` — this gate matters more than the schedule. A post that
   fails it does not ship late, it does not ship.
5. **Voice** via `psx-voice`.
6. **Write the file** to `site/src/content/blog/<slug>.mdx` with `draft: true`.
7. **Human review**, then flip `draft: false` and publish.
8. **Link it**: at least one link to its pillar, one to a sibling, one to a relevant `/tools/`
   page. Internal links are most of what makes a cluster work.

### Frontmatter

```yaml
---
title: How PSX settlement works — T+1 explained
description: One sentence, under 155 characters, containing the target query.
pubDate: 2026-07-22
cluster: Market structure
draft: true
---
```

`updatedDate` is added on any material edit — it drives `lastmod` in the sitemap and the "Updated"
line on the post.

### Cadence

**One genuinely good post per week.** Not five thin ones — Google's helpful content system
explicitly targets scaled unhelpful content and a new domain has no buffer to absorb that hit.
At one a week a cluster completes in ~4 weeks, which is the right unit of progress.

### The loop that compounds (from week 4)

Publishing new posts forever is the amateur move:

```
publish → wait 3–4 weeks for impressions
→ GSC: filter position 5–20, sort by impressions
→ improve THOSE pages → repeat
```

A page at position 11 already has the ranking signal. Moving it to 6 beats writing a new post from
zero. **Judge month 3 on impressions and average position, not sessions.**

---

## 5. Guardrails

- **No advice language** (Rule 5). Posts explain; they never say what to buy.
- **No unsourced number.** "Unknown" is an acceptable answer; a plausible guess is not.
- **YMYL bar** on anything tax- or money-related: dated rates, primary-source links, visible
  last-updated. That is *why* these pages rank, not decoration.
- **Draft by default.** Nothing reaches the live site without a human flipping the flag.
- **Never publish on a schedule for its own sake.** A missed week costs nothing. A wrong published
  tax number costs the domain's credibility.
