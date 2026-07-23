# Social — the distribution plan

**Status:** draft for owner sign-off, 2026-07-22.
**Read with:** [ORGANIC_GROWTH_PLAN.md](ORGANIC_GROWTH_PLAN.md) (§6 lists social as a channel; this
is that channel specified) · [CONTENT_ROUTINE.md](CONTENT_ROUTINE.md) (the publishing gate this
inherits) · [CLAUDE.md](../CLAUDE.md) — **Rule 2 and Rule 5 bind every post.**

This doc owns social only. It does not touch the blog cadence, the SEO plan, or the desk pipeline.

---

## 0. Verified starting position (2026-07-22)

Pulled from `state/` on the date above. Not estimates.

| Fact | Value | Source |
|---|---|---|
| Dated claims on record | **364** | `claims.json` |
| Claims **resolved** | **0** — all `pending` | `claims.json` |
| Oldest claim / first resolution | made 2026-07-14 / resolves **~2026-08-03** | 20-day horizon |
| Broker calls captured | **4** (all Topline) | `claims.json` |
| Brokers rankable | **0** — `min_sample_to_rank: 5` | `broker_scorecard.json` = `{}` |
| Desk Room sessions complete | **42** with house view, bull case, bear case, dissent | `rooms.json` |
| Astro lens backtested | yes, on history | `astro_backtest.json` |
| Blog posts published | **0** | `site/src/content/blog/` |
| Social posts published | **1** (`22-07-26.png`) | `Henneth - Marketing/SM Posts/` |
| Accounts | `@hennethapp` (X), `henneth.app` (IG), LinkedIn | owner, 2026-07-22 |

**Read this honestly.** The differentiated asset — *"we score every call, ours and the brokers'"* —
is real, is built, and has **produced nothing yet**. Any content plan that leads with a track
record in the next two weeks is claiming something the data layer cannot support, which is Rule 2
applied to marketing. What *is* postable today is the 42 debates and the astro backtest. Plan
accordingly.

---

## 1. The position — scorekeeper, not tipster

PSX social is saturated with one format: **"BUY XYZ TARGET 150."** Free, confident, unaccountable,
and never scored. Every account in that lane competes on confidence.

Henneth cannot enter that lane. Rule 5 forbids it, SECP exposure argues against it, and the buyer
is wrong — people who want free tips do not buy research.

The lane that is empty: **nobody in Pakistan publicly keeps score.** Not on their own calls, not on
the brokers'. Henneth does it by architecture — dated, falsifiable, resolved against what prices
actually did, whether it flatters the desk or not.

> **The position, in one line:** *The desk that publishes its calls before the outcome and grades
> them after.*

That position is not a content theme. It dictates the format of every post: **a post that cannot be
checked later does not go out.** Dates, prices with an `as_of`, horizons, and eventually the mark.
This is also the only defensible moat on social — a tip account can copy a chart, it cannot copy
having been on the record for eight months.

**Corollary — publish the ledger before it resolves.** A timestamp you did not control is the whole
credibility mechanism. Posting 364 open, dated, unresolved calls is *stronger* than posting a
finished track record, because a finished track record on a new account reads as cherry-picked.
This inverts the usual launch: **we open with the exposure, not the highlight reel.**

---

## 2. The three engines

Not "pillars." Engines — each has a fuel source in `state/` and stops when that source is dry.

### Engine 1 — Receipts *(fuel: `claims.json`, `broker_scorecard.json`)*
**Live from ~2026-08-03. Not before.**

Scored outcomes, own and broker. Hit *and* miss — a miss posted plainly is worth more than a hit,
because it is the proof that the hits are not selected. The desk's own rules already require
documenting losses (Rule 5); social is where that becomes an asset instead of a compliance line.

- `Called on 14 Jul: OGDC reclaims SMA20 (335.07) in 20 sessions. Resolved 03 Aug: [mark]. Analyst: Meher. Running: n/n.`
- Monthly: the full ledger — every claim, every resolution, no filter.
- **Quarterly Broker League Table** — the press asset (`ORGANIC_GROWTH_PLAN.md` §6.1). **Blocked**;
  see §8.

### Engine 2 — Mechanics *(fuel: `PSX_MECHANICS_VERIFIED.md`, `PSX_COSTS_VERIFIED.md`)*
**Live today.**

How the market actually works, primary-sourced. Highest save/share rate, zero controversy, feeds the
blog clusters and gets fed by them. This is what makes a stranger believe the desk knows things.

The strongest of these are **corrections**, because corrections travel and the SERP is wrong:
- *The KSE-100 is a **total-return** index (base Nov 1991 = 1,000). Most sources say price index.*
- *Selection is **36 sectors + 64 largest by free float** — not the "35 + 65" everyone repeats.*
- *There is no "spot market" on the PSX.* The term appears twice in the rulebook: a contract-note
  field, and a punitive T+0 mode for non-compliant issuers. The vacuum exists because the thing
  doesn't.
- *Settlement is T+1, and book closure moved with it* — the 2023 rulebook's "– 2 SETTLEMENT DAY"
  suffix is gone in the Feb 2026 edition.

⚠️ Every caveat in `CONTENT_BACKLOG.md` §"Angles that must not be lost" carries over verbatim to
social. "Last day to buy" appears in **no** primary source. Do not post it as a rule. No published
weight cap on KSE-100 means *"the methodology does not specify a cap"* — never *"there is no cap."*
A caveat dropped for character count is a wrong YMYL claim.

### Engine 3 — The desk at work *(fuel: `rooms.json` — 42 sessions ready)*
**Live today. Most differentiated thing you own.**

Two AI analysts argue a stock, a Chair synthesises, and **the dissent is recorded**. Nothing in
Pakistani finance media shows its own disagreement. Formats:

- **Bull vs Bear** — the two cases side by side, house view, and the dissent left visible.
- **The Chair's dissent** on its own. *"The house view is X. Here is why one desk disagreed."*
  Intellectual honesty is the entire brand and this format is nothing but.
- **Desk Room replay clips** — already a staged animated walkthrough, currently distributed nowhere.
  It is a built video asset. Reels/Shorts cost a screen recording.

### Engine 4 (low frequency, high reach) — the astro lens *(fuel: `astro_backtest.json`)*

Astro content in Pakistan travels several times further than finance content. Henneth's version is
the only defensible one: **tested and scored on PSX history.**

The flagship piece writes itself — *"We tested what financial astrology claims about markets against
19 years of PSX data. Here is what survived and what didn't."* It reaches the astro audience **and**
the skeptics, because the honest answer includes what failed.

⚠️ Per `CONTENT_BACKLOG.md` #4 and the desk's astro rules: presented as a **tested, scored lens with
published results**, never as prediction. Every astro post carries the disclaimer. `room-astro`
refuses claims the backtest did not support — social inherits that refusal.

**Ratio, once all four run:** roughly 40% receipts · 30% mechanics · 20% desk at work · 10% astro.
Until 03 Aug, receipts are 0% and mechanics + desk carry the load.

---

## 3. Platform roles — they are not the same job

| | `@hennethapp` (X) | `henneth.app` (IG) | LinkedIn |
|---|---|---|---|
| **Job** | Be the record | Be seen | Reach the buyer |
| **Audience** | Active PSX traders, finance X | Retail, younger, broad | Bankers, AMC, corporate finance, treasury |
| **Native format** | Single post + thread | Carousel, Reel | Long-form text post |
| **Lead engine** | Receipts | Mechanics + astro | Mechanics + League Table |
| **Cadence** | 5×/week + 1 thread | 3×/week | 2×/week |
| **Converts?** | Some | Rarely — expect near-zero click-through | **Best buyer per follower** |

**X is the record.** Timestamped, quotable, searchable, and where PSX actually argues. Every claim
posts here first — the platform *is* the notarisation.

**IG is a magazine, not a funnel.** Judge it on reach and saves, never clicks. Your design language
(mono, hard corners, cream/green, terminal) is already carousel-native — that's a real head start
and most finance IG in Pakistan is ugly. Link in bio, and stop expecting more.

**LinkedIn is where the money is.** Lowest competition, longest shelf life, and the audience can
expense a subscription. `linkedin-voice-check` already exists as a gate. Underweighting LinkedIn is
the most likely unforced error here.

**@MWasayI leverage.** The brand accounts start at zero and no amount of quality changes that in
week one. Personal account quote-posts the brand account — that is the only distribution the brand
accounts have until they have their own. Not optional; it's the bootstrap. `psx-tweet-pipeline`,
`tweet-voice-check` and `psx-reply-scan` already exist and keep running as-is.

---

## 4. Launch sequencing — do NOT announce

**The single most important instruction in this document.**

An "introducing our first publication" post to zero followers reaches zero people, and burns the
one moment when a visitor decides whether the account is real. A visitor who lands on a launch
announcement sees a company that has done nothing. A visitor who lands on three weeks of dated,
checkable work sees a desk that was already running and they missed the start.

**Therefore: post for three weeks before telling anyone the accounts exist.**

| | Window | What happens |
|---|---|---|
| **Phase 0 — Fill** | 22 Jul – 12 Aug | Post the full cadence to nobody. No announcement, no promotion, no personal-account amplification. Build a wall of work. Receipts engine switches on ~03 Aug inside this window. |
| **Phase 1 — Open** | from ~12 Aug | @MWasayI announces. By then the profile shows ~40 posts, resolved calls, and 42 debates — a track record, not a debut. |
| **Phase 2 — Compound** | Sep onward | The monthly ledger becomes the anchor post. Press pitch when the League Table unblocks. |

**The Phase 1 opening post is the ledger, not the logo.** *"We've published 364 dated calls since
July. Here's what's resolved so far, including the misses."*

---

## 5. The gate — every post, no exceptions

Social is where Rules 2 and 5 are most likely to break, because character limits punish caveats and
engagement rewards confidence. So the gate is stricter here, not looser.

- [ ] **Every number traces to `state/` or a verified doc.** No price, date, or dividend from
      memory. If the data layer doesn't have it, the post doesn't say it.
- [ ] **`as_of` on any market number.** A price with no date implies a live feed. TV data is ~15 min
      delayed and must never be presented as live.
- [ ] **No advice language (Rule 5).** No "buy", no "target", no "should", no "undervalued, so".
      Describes and explains. If a draft would read as a tip when screenshotted without context,
      it fails.
- [ ] **Falsifiable or it doesn't ship** — dated, with a horizon, checkable later.
- [ ] **Caveats survive the edit.** If it won't fit with its caveat, it's the wrong post, not a
      reason to drop the caveat.
- [ ] **Losses included.** A month of only-hits is a selection problem; fix the posting, not the
      ledger.
- [ ] **Disclaimer present** — "Research · not advice", in-image on IG, in-copy on X/LinkedIn.
- [ ] **Voice check run** — `tweet-voice-check` (X) / `linkedin-voice-check` (LinkedIn).

**If a gate fails, the post does not go out.** A missed slot costs nothing. A wrong number on a
screenshot is permanent and takes the domain's credibility with it — the one thing that cannot be
rebuilt by working harder.

---

## 6. Asset rules — and the fix to the first post

`22-07-26.png` establishes the visual language and it's strong: mono type, hard corners, cream/green,
terminal chrome. Consistent with the product, distinct in the category. **Keep the design system.**

Three corrections, in order of severity:

**6a. Never publish illustrative market data. This is a hard rule.**
That post shows a ticker grid labelled *"Data Illustration / Template"* and a chart labelled
*"Illustration"* — invented percentage moves printed beside real listed companies. Rule 2 exists
precisely to prevent this, and a fabricated move next to a real symbol is a false claim about that
company regardless of the label. `CONTENT_ROUTINE.md` §4 already settled this for the website
components: **the slice carries the real board, so honest costs the same as faked.** Social inherits
that verdict. Every data-bearing asset renders from `site/src/data/public/context.json` or
`state/`, and carries its `as_of` stamp.

**6b. It's a poster, not a post.** Sixty-plus words before any payoff; the feed gives 1.5 seconds.
One idea per asset. The hook is the first line, and the first line has to earn the second.

**6c. Announcements are the weakest format available.** "Introducing our first publication" asks a
stranger to care about a company. Show the work and let them infer the company. See §4.

**Standing asset rules:** one idea per asset · real data with `as_of` or no data at all · disclaimer
on every data-bearing asset · IG at 1080×1350 (4:5 takes more feed height than square) · legible at
thumbnail size · never animate opacity from 0 for an entrance (a social scraper that doesn't advance
the animation captures a blank panel — this already happened to `DeskPeek`).

---

## 7. Month 1 — concrete

Everything below is postable from existing data. Nothing here needs the pipeline to produce
anything new.

**Week 1 (22–29 Jul) — mechanics + desk, no receipts**
1. X thread — *The KSE-100 is not what you think it is* (total-return, 36+64, no published cap).
2. IG carousel — same, 6 slides, from the same verified facts.
3. LinkedIn — *Settlement moved to T+1 and book closure moved with it. Most explainers online still
   teach the old rule.*
4. X — Bull vs Bear on one of the 42 (`LUCK` or `HUBC`), dissent shown.
5. X — *There is no "spot market" on the PSX.* The rulebook-vacuum piece.

**Week 2 (29 Jul – 5 Aug) — the ledger goes up, receipts switch on**
6. X thread — **the exposure post**: *364 dated calls on record since 14 July. First ones resolve
   03 August. We'll post the misses too.* This is the account's spine.
7. IG Reel — Desk Room replay clip, 30–45s screen capture.
8. LinkedIn — *We tested financial astrology against 19 years of PSX data.* The credibility-through-
   skepticism piece; strongest single LinkedIn post available.
9. **~03 Aug — first resolution.** Post it same day, hit or miss, no delay. A resolution posted late
   looks selected.

**Week 3 (5–12 Aug) — rhythm, then open**
10–14. Receipts as they resolve · one mechanics piece · one Desk Room piece · astro carousel on IG.
15. **~12 Aug — Phase 1.** @MWasayI announces. Opening post is the ledger.

**Standing weekly, from week 4:** 1 receipts thread · 2 mechanics · 1 Desk Room · 1 astro or ledger
· LinkedIn ×2 · IG ×3.

---

## 8. Blocked, and what unblocks it

**The Broker League Table is the highest-leverage asset in this plan and it is not available.**
`ORGANIC_GROWTH_PLAN.md` §6.1 is right that one press pickup outweighs fifty posts — Profit, Dawn,
Business Recorder and Mettis have no equivalent to a public broker scorecard. But:

```
broker_scorecard.json  →  { "brokers": {} }
broker calls captured  →  4, all Topline
min_sample_to_rank     →  5
```

Zero brokers are rankable, and each call still needs its horizon to elapse before it scores. This is
a **harvesting** shortfall, not a modelling one — `room-broker-harvester` exists and has barely run.

**Unblock:** run the harvester weekly against the business press until ≥5 resolved calls exist for
≥3 houses. Realistic first League Table: **Q4 2026**. Do not pitch press before then. A league table
built on four calls from one broker is exactly the kind of thin claim that ends the press
relationship on first contact.

---

## 9. What would make me stop

Written before the fact so it can't be rationalised later.

- **A wrong number ships on a screenshot** → stop posting, fix the gate before the next slot.
  Screenshots outlive deletions.
- **A post reads as a tip when quoted without context** → the format is wrong, not the caption.
  Retire that format.
- **Engagement only ever comes from astro** → the finance content isn't landing; the account is
  drifting to an audience that will never buy research. Re-cut the ratio, don't chase the reach.
- **Three weeks of receipts and no resolved misses posted** → we are selecting. That kills the one
  thing the account is for.
- **IG judged on clicks and found wanting** → wrong metric, not a wrong channel. Judge reach and
  saves, or drop the channel deliberately — but not by accident.
