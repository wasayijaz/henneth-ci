# Content backlog — the publishing queue

The scheduled routines read this file to decide what to write next. **Order matters**: always take
the topmost item whose file does not yet exist.

Nothing is marked "done" by hand — **existence of the file is the source of truth**, because a
status column drifts the moment one run fails halfway. Check
`site/src/content/blog/<slug>.mdx` and `site/src/pages/solutions/<slug>.astro`.

Process: [CONTENT_ROUTINE.md](CONTENT_ROUTINE.md) · Strategy: [BLOG_PLAN.md](BLOG_PLAN.md)

---

## Blog queue — finish Cluster 1 before starting Cluster 2

Facts for all three are already verified in [PSX_MECHANICS_VERIFIED.md](PSX_MECHANICS_VERIFIED.md).
**No new research is required for these** — the sourcing is done, they need writing.

| # | Slug | Working title | Cluster | Sources |
|---|---|---|---|---|
| 1 | `psx-book-closure-ex-date` | Book closure and the ex-date, after T+1 | Market structure | MECHANICS §A |
| 2 | `psx-market-types-explained` | Ready, futures and what "spot" actually means on the PSX | Market structure | MECHANICS §B |
| 3 | `kse-100-index-explained` | How the KSE-100 is actually built | Market structure | MECHANICS §C |

Then Cluster 2 (Getting started) — **these need research first**, so a run that reaches them must
verify before drafting:

| # | Slug | Working title | Cluster |
|---|---|---|---|
| 4 | `how-to-start-investing-psx` | How to start investing in the PSX | Method |
| 5 | `cdc-sub-account-vs-investor-account` | CDC sub-account vs investor account | Method |

### Angles that are already sourced and must not be lost

- **Book closure (#1).** The rule changed *in the regulation text*: the 2023 rulebook headed clause
  10.6 "…– 2 SETTLEMENT DAY"; the Feb 2026 edition drops the suffix and reads "one settlement day".
  NCCPL's circular says "ex-price shall be computed w.e.f. BC-1". ⚠️ "Last day to buy" appears in
  **no** primary source — present it as a consequence of the ex-entitlement basis, never as a
  quoted rule. ⚠️ Splits are the exception (BAFL, PSX/N-403).
- **Market types (#2).** *"Spot market" does not exist as a defined PSX market type.* The word
  appears twice in the rulebook — a contract-note field, and a punitive T+0 mode for
  non-compliant issuers. The SERP vacuum exists because the thing does not exist. That IS the
  piece. Also: NDM is **T+0 to T+60**, not T+0.
- **KSE-100 (#3).** It is a **total-return** index (base Nov 1991 = 1,000) — most sources get this
  wrong. Selection is **36 sectors + 64 largest by free float**, not the "35 + 65" in circulation.
  ⚠️ No weight cap is published: write "the methodology does not specify a cap", never "there is
  no cap".

---

## Landing page queue

| # | Slug | Targets | Plan |
|---|---|---|---|
| 1 | `psx-dividend-calendar-and-yields` | dividend dates, yields, book closure | investor |
| 2 | `psx-company-fair-value` | "is X overvalued", intrinsic value | pro |
| 3 | `psx-market-today` | daily read, what moved and why | investor |
| 4 | `psx-astrology-market-lens` | the astro pillar (differentiated) | pro |

Each needs a distinct audience and a real problem statement. **If a proposed page would compete
with an existing blog post or tool page for the same query, skip it and extend that page instead** —
cannibalisation is the failure mode these are most likely to hit.

⚠️ #4 needs care: the astro lens is scored and falsifiable per the desk's rules. The page must
present it as a *tested, scored* lens with published results, never as prediction.

---

## Standing rules for every run

1. **No unverified number.** Rates from PSX_COSTS_VERIFIED.md, mechanics from
   PSX_MECHANICS_VERIFIED.md. Anything else needs a primary source read in that run.
2. **No advice language** (CLAUDE.md Rule 5).
3. **Build must pass, and the page must be rendered and looked at** before publishing. The build
   passes on layouts that are visibly broken — this has already happened twice.
4. **Scope `git add` to the files you touched.** Multiple sessions share this checkout and a
   blanket add has twice swept in someone else's in-flight work.
5. If a gate fails, **stop and report — do not publish**. A missed week costs nothing; a wrong
   published number costs the domain's credibility.
