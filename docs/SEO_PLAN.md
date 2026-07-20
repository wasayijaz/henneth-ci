# Organic growth plan — henneth.app

The desk's only user-acquisition channel. Zero paid spend, by decision.

**Read this before writing any page.** It records what was actually verified against live SERPs,
not what sounds plausible, and the guardrails that keep a research desk from publishing a wrong
tax number.

---

## 0. Honest constraints

1. **New domain, no authority.** No backlink profile, no history. Nothing competitive ranks in
   month one. First real traffic ~month 3–4; compounding from ~month 6.
2. **No keyword tool.** There is no Ahrefs/Semrush subscription and none is planned, so **this
   document contains no search-volume numbers.** Any figure claiming to be one would be invented.
   Priority below is derived from *observed SERP weakness* — who actually ranks, and whether what
   ranks is any good. That is a weaker signal than volume, and it is the honest one.
3. **GSC becomes the keyword tool** once impressions accumulate. See §5.
4. **Paid incumbents own the data queries.** Sarmaaya, Mettis, PSX DPS own "X share price".
   Do not fight there: that traffic wants a number, not a subscription. Target the queries where
   the visitor already has the number and still doesn't know what to do with it.

---

## 1. Verified facts this plan leans on

| Fact | Status | Source |
|---|---|---|
| PSX moved **T+2 → T+1** on **9 Feb 2026** | **Verified**, primary source | [NCCPL](https://www.nccpl.com.pk/press-releases/pakistan-capital-market-successfully-transitions-to-the-t1-settlement-cycle), [SECP](https://www.secp.gov.pk/media-center/event-gallery/secp-introduces-strategic-roadmap-to-transition-to-t1-settlement-cycle/), [Business Recorder](https://www.brecorder.com/news/40402673/psx-transitions-to-t1-settlement-from-feb-9) |
| Effectively every ranking PSX explainer still says T+2 | Observed on live SERPs, Jul 2026 | SERP sweep |
| Sarmaaya's deduction calculator renders blank results | Observed | direct page fetch |
| KTrade's commission calculator ships an unrendered `[ktrade_commission_calculator]` shortcode | Observed | direct page fetch |
| Non-filer CGT rate is reported as 16 / 20 / 25 / 30% by different sources | Observed disagreement | multiple secondary sources |

The T+1 shift is the single most valuable asset here. It is a **dated, checkable correction** that
a zero-authority domain can win on merit, because being right beats being established when the
established answer is provably stale. It expires as an advantage the moment competitors update —
so it is worth doing first, not eventually.

---

## 2. Priority stack

Ordered by *return per hour*, not by guessed volume.

| # | Page | Type | Why it's first |
|---|---|---|---|
| 1 | PSX trading-cost calculator | Tool | Two known brands advertise this feature and **both ship it broken**. Fixed-percentage maths, no tax-law risk. |
| 2 | PSX settlement, book closure & spot rate (T+1) | Article | Near-vacuum on "spot rate PSX"; provable freshness win on T+1. |
| 3 | How the KSE-100 actually works | Article | Two *foreign generic glossary sites* rank top-10 for an inherently Pakistani query. |
| 4 | CGT on shares calculator (+ dividend WHT module) | Tool | Real competitors exist but are thin, and the SERP visibly disagrees on rates. **Gated on §4.** |
| 5 | CDC sub-account vs investor account | Article | SERP splits between dry official PDFs and broker marketing. Nobody writes the actual decision. |
| 6 | Sector-aware PE ratio on PSX | Article | Real gap, but harder — needs authority first. |

**Deliberately deferred: zakat on shares.** Genuine whitespace, but three competing fiqh
methodologies exist and per-company zakatable-asset ratios are not available machine-readable for
PSX listcos. A wrong zakat number is a religious-credibility failure, not a data bug. Ship it when
it can be grounded properly (AAOIFI / per-unit-factor route), not as a v1.

---

## 3. Why calculators before articles

- They rank from a weak domain faster than prose, because the SERP intent is "do a thing" and
  almost nothing available does the thing.
- They attract links naturally. **People link to tools; they rarely link to explainers.** This is
  the only realistic route to authoritative backlinks with no budget.
- Pakistan-specific fee/tax structures mean global sites cannot compete.
- Intent is qualified: someone computing their CGT owns shares.

---

## 4. Guardrail — YMYL and the tax-number gate

Tax and money pages are **YMYL** ("Your Money or Your Life"). Google holds them to a higher
E-E-A-T bar, so the things below are not polish, they are the reason the page ranks at all:

- Every rate carries an **"as of" date** and a **link to the primary source** (FBR Finance Act,
  NCCPL circular, PSX/CDC fee schedule) — never a blog.
- A named reviewer and a visible last-updated date.
- Show the **workings**, not just the answer. A user who can see the arithmetic trusts it, and it
  is what differentiates from the thin calculators already ranking.

**Hard gate before any tax calculator ships:** rates must be verified against FBR / NCCPL primary
documents. The SERP sweep found live disagreement on the non-filer CGT rate across four sources,
and the FY26–27 budget reportedly moves CGT and dividend WHT again. **Do not ship a number sourced
from a secondary blog.** This is the desk's own Rule 2 (all figures come from the data layer or
they are "unknown") applied to published content.

Also binding: **CLAUDE.md Rule 5 — no advice language.** These pages compute and explain. They do
not tell anyone what to buy. "Research, not advice" applies to marketing content too.

---

## 5. The loop that actually compounds

Publishing new posts forever is the amateur move. The engine is:

```
publish → wait 3–4 weeks for impressions
→ GSC Performance → filter position 5–20, sort by impressions
→ improve THOSE pages → request re-index → repeat
```

A page sitting at position 11 already has the ranking signal; moving it to 6 beats writing a new
post from zero. GSC tells you this free — it is the keyword tool.

**Judge month 3 on impressions and average position, not sessions.** Traffic is a lagging
indicator and quitting early on a working strategy is the standard failure.

---

## 6. Distribution, zero spend

- **X (@MWasayI)** — every piece gets a thread. First readers, sometimes first links.
- **Be the source.** The broker-call scorecard and strategy backtests are proprietary and
  genuinely newsworthy in Pakistan. One business-press pickup outweighs fifty blog posts, and it
  is the only realistic free route to authoritative links.
- **Answer where the questions already are** — PSX Facebook groups, Reddit, X. Useful answers
  only; drive-by link drops get banned and achieve nothing.
- **Never buy links.** A new domain cannot survive a bad link profile.

---

## 7. Cadence

One genuinely good piece per week beats five thin ones, and it is not close — Google's helpful
content system explicitly targets scaled unhelpful content, and a new domain has no buffer to
absorb that hit. The drafting pipeline exists (`psx-content-drafter` → `psx-fact-checker` →
`psx-voice`); the **fact-checker gate matters more than the volume**.

---

## 8. Measurement

Events fire via `window.hTrack` (see `site/src/layouts/Base.astro`). GA4 property `G-5PLLEK6RYC`
covers both henneth.app and desk.henneth.app.

| Event | Fires on |
|---|---|
| `desk_click` | any link into the desk, carrying `?plan=` intent |
| `waitlist_submit` | newsletter/waitlist signup |
| `contact_click` | mailto links |

**Manual step, required:** mark `desk_click` and `waitlist_submit` as **key events** in
GA4 → Admin → Events. Until then they are ordinary events and will not show as conversions
against landing pages or queries.
