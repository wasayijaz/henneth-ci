# PSX market mechanics — verified reference

Companion to [PSX_COSTS_VERIFIED.md](PSX_COSTS_VERIFIED.md). Same rule: nothing here may come from
a blog, a news article, or another explainer. Every figure carries a primary source and a
confidence marker, and UNVERIFIED items are named rather than filled in.

Verified 21 July 2026 against the PSX Rule Book (09 Feb 2026), the prior Rule Book (15 Feb 2023),
NCCPL circulars and the PSX KSE-100 methodology brochure. All PDFs were downloaded and
text-extracted in full — PSX's PDFs are compressed such that fetch-and-summarise returns nothing
usable, which is very likely **why competitors get this wrong**.

---

## ⚠️ Stale official sources — do NOT cite these

The most useful finding in this entire pass. Post-T+1, **PSX's own published materials contradict
each other**, which is exactly why every secondary guide is wrong:

| Document | Problem |
|---|---|
| KSE-100 Index Brochure (June 2025, still the live link on PSX's indices page) | Quotes Rule 10.6 as *"two Settlement Day before its Books Closure start date"* — superseded T+2 text. Its divisor rule (*"end of T-3 days"*) is stale too. |
| All Shares Islamic Index brochure (updated **June 2026** — four months *after* T+1 went live) | Still says *"on T+2 settlement basis"*. |
| PSX Equity product page | Says *"Transactions are settled in two days (T+1)"* — self-contradictory in one sentence. |

The index brochure's *mechanics* (§C below) remain usable; only its ex-price timing is stale.

---

## A. Book closure and the ex-date

### A1. The rule — VERIFIED PRIMARY

**Ex-date = Book Closure start date minus ONE settlement day.** This changed in the regulation
text itself; it is not inferred from the settlement cycle.

> **10.5.1(c)** — "Ready Delivery Contract in a Security will be declared for settlement on T+1
> settlement cycle **on ex-entitlement basis at least one settlement day before the Book Closure
> start date** of such Security…"

> **10.6 DETERMINING EX-PRICE OF SECURITY ON BOOK CLOSURE** — "…the Exchange shall determine the
> ex-price … as an opening price for the Trading Day falling **one settlement day before its Books
> Closure start date**."

Source: PSX Regulations (Rule Book), **09 Feb 2026**, Chapter 10, pp. 124–125.

### A2. Proof it changed from "minus 2" — VERIFIED PRIMARY, both versions held side by side

The prior rulebook said so in its **section heading**:

> **10.6 DETERMINING EX-PRICE OF SECURITY ON BOOK CLOSURE – 2 SETTLEMENT DAY** — "…two Settlement
> Day before its Books Closure start date."

Source: PSX Rule Book, **15 Feb 2023**.

The "– 2 SETTLEMENT DAY" suffix was **dropped from the heading** and "two" became "one". This is
the cleanest citation available: the widely-repeated "minus 2" rule was real and regulatory, and
it is now "minus 1".

**Independent confirmation — NCCPL, VERIFIED PRIMARY:**
> "In case of corporate actions on a particular symbol, the ex-price shall be computed **w.e.f.
> BC-1** in the Ready market."
— Circular NCCPL/CM/FEBRUARY-26/01, *Transition of Settlement Cycle from T+2 to T+1*, 2 Feb 2026,
Annexure-A pt. 9.

### A3. Trading days, not calendar days — VERIFIED PRIMARY

2.4(xcii) defines T+1 by *"the number of **trading day** after the trade day"*. 2.1(o) makes
"day" mean calendar day **unless** stated as working/trading/settlement day — and 10.5.1(c) and
10.6 both say *settlement day*. Count backwards in trading days, skipping holidays.

⚠️ Drafting wrinkle: the Regulations use "Settlement Day" throughout but **never define it**
(no entry in 2.4). "Trading Day" *is* defined. Do not build a sentence that depends on a formal
definition of "settlement day" — there isn't one.

### A4. "Last day to buy" — INFERENCE, must be labelled as such

**No PSX or NCCPL document states this in words.** NCCPL's site search for "book closure" returns
no results; its 11-question T+1 FAQ never mentions entitlements; the 362-page NCCPL Regulations
do not define book closure.

What IS regulatory: trading on BC-1 is **on an ex-entitlement basis** (10.5.1(c)), so a BC-1 buyer
does not get the entitlement. The corollary — the last cum-entitlement session is the one before
BC-1 — is a single logical step, and **ours, not PSX's**.

Nearest supporting clause, **10.8.14** (broker-to-broker liability, not investor-facing):
> "…delivered to the buyer **at least one Settlement Day before the Book Closure start date** …
> to enable the buyer to get the Securities transferred to his name…"

**Publishing language:** state the ex-date rule as regulation (cite 10.6), state that buying on or
after it does not carry the entitlement (cite 10.5.1(c)), then present "so the last cum day is the
session before" as a **consequence** — never dressed up as a quoted rule.

### A5. Bonus and rights — same ex-date rule — VERIFIED PRIMARY

10.5.1(c) and 10.6 say *"any entitlement"*: one rule covers dividend, bonus and rights. Only the
**price formula** differs (§A7). Issuer-side timetables differ (Ch. 5.8): rights and bonus book
closure must start within 7 working days, and the book closure period *"shall not be more than one
(01) day"*.

### A6. ⚠️ Splits are the exception — VERIFIED PRIMARY

**Do NOT write "the ex-price always applies on BC-1" as a universal.** PSX Notice PSX/N-403
(10 Apr 2026, Bank Alfalah):

> "Trading in the shares of BAFL shall be subject to a **modified settlement cycle i.e. on T+0
> basis (same day settlement)** for the trading day BC-1 … **due to stock split**. However, with
> effect from April 20, 2026 (First Working Day after the Book Closure), normal settlement cycle
> i.e. T+1 shall be resumed, with adjusted price."

So for splits the price adjusts *after* book closure, not on BC-1. PSX issues per-security notices
that can modify the cycle around book closure.

### A7. Ex-price formulas — VERIFIED PRIMARY (arithmetic only, no timing)

PSX, *Price Adjustments while calculating Ex-Dividend, Ex-Bonus, Ex-Right…*, 5 Jan 2016:

- Ex-Dividend = Closing Price − Dividend (Rs)
- Ex-Bonus = Closing × 100 ÷ (Bonus% + 100)
- Ex-Right (par) = ((Closing × 100) + (Face Value × Right)) ÷ (Right + 100)
- Ex-Right (premium) = ((Closing × 100) + ((Face Value + Premium) × Right)) ÷ (Right + 100)

Contains **no timing rule at all** — safe to publish.

---

## B. Market types

### B1. Ready Market — VERIFIED PRIMARY
2.4(lxxvii): a trade *"ready for settlement on **T+1 settlement cycle**"*. 10.5.1(a)–(b): both
book-entry and physical securities settle T+1.

Worth noting: the 2023 definition read *"either on T+1 or T+2"* **and included the Odd Lots
Market**. The Feb 2026 definition drops both.

### B2. ⚠️ "Spot Market" — DOES NOT EXIST as a defined PSX market. Negative finding.

Full-text search of both the Feb 2026 and Feb 2023 rulebooks: "spot" appears **exactly twice** in
each, and neither is a market definition —

1. **Ch. 7**, a field on a broker contract note: *"Nature of trade (SPOT, Ready, Future…)"*.
2. **5.11**, punitive: non-compliant companies traded *"only on **T+0 (SPOT)** for the next 7
   days"* before suspension.

**There is no clause defining a Spot Market, no spot settlement cycle, and no link between "spot"
and book closure.** The reason Pakistani sources are near-absent on this is that the thing being
described **no longer exists as a distinct regulated market** — book closure is now handled inside
the Ready market by flipping it to ex-entitlement basis (10.5.1(c)).

The only live operational sense is PSX's *"modified settlement cycle i.e. on T+0 basis"*, imposed
per-security by notice. **That framing — "PSX's rulebook does not define a spot market" — is
itself the more-correct-than-competitors angle.**

### B3. Futures — VERIFIED PRIMARY
- **DFC** (13.1, 13.2.6): standardised **90-day** contract issued monthly. Settlement basis is
  deliberately *not* hard-coded in the Regulations (13.6.4(a) defers to Contract Specifications);
  the specs say **physical delivery, expiry + 1**. Lot 500 shares, expires last Friday.
- **13.6.2** — futures analogue of the book-closure rule: on an entitlement during a pending
  settlement, the Exchange *"shall **predate** the last day of business and the settlement date"*.
- **CSF** (14.3.3): final settlement **T+1, in cash**; final settlement price is the Ready Market
  close on expiry (14.1(e)); daily MtM (14.3.2).

### B4. ⚠️ NDM is NOT T+0 — VERIFIED PRIMARY
> "Settlement Cycle of NDM trades is ranging from **T+0 to T+60**."
— NCCPL, *Clearing & Settlement Services*, item 02.

Also: NDM trades are disclosed (counterparties known), settled **trade-for-trade**, and *"no
netting is permissible"* across NDM and any other market. T+0 is one available cycle within NDM,
with its own procedure (NCC Systems Procedures §3.5.9). PSX Ch. 8.15 specifies **no** settlement
cycle for NDM — it covers conduct only.

---

## C. KSE-100 methodology

Source: *KSE100 Index (Total Return & Price Return) — Index Brochure*, updated **June 2025**, the
current linked methodology on PSX's indices page. Mechanics below are VERIFIED PRIMARY; only its
ex-price timing is stale (see top).

**C1. Calculation** — free-float market capitalisation divided by an **Index Divisor**, which is
*"the only link to the original base period value"* and the adjustment point for all corporate
actions and constituent changes. Real time, from executed trade prices.

**C2. Base — and the thing competitors get wrong**
- **KSE-100 is a TOTAL RETURN index**: base **November 1991 = 1,000 points**. Cash dividends,
  bonus and rights are adjusted into it.
- **KSE100PR** is the price-return variant: base **1 April 2009 = 6,931 points**.

**C3. Free float** — recommended by the Index Expert Committee in early 2012, approved by the PSX
Board 24 Apr 2012, run in parallel from 11 Jun 2012, **effective 15 Oct 2012**, replacing *total*
market capitalisation. Free float excludes government, director/sponsor/senior-management and
associate holdings, **shares in physical form**, cross-holdings, non-sellable ESOS shares and
treasury shares. Hard ceiling: free float may never exceed a scrip's book-entry shares in the CDS.

**C4. Selection — the folk version is wrong in two ways**
- Largest **free-float** market cap in each of **36** sectors (38 listed, ETFs and open-end mutual
  funds excluded) — *not* market cap, and *not* 35.
- The remaining **64** places by free-float market cap, descending. (The "35 + 65" split in
  circulation is out of date.)
- Excluded: Defaulters' Counter, suspended, or declared Non-Tradable in the preceding six months.
- A new listing qualifies after one re-composition period if its free float is ≥ **2%** of total
  free-float market cap.

**C5. Rebalancing — semi-annual, with buffers**

| Data basis | Notice | Implementation |
|---|---|---|
| Last working day of February | 15 March | First working day of April |
| Last working day of August | 15 September | First working day of October |

Entry is **not** automatic on out-ranking an incumbent:
- **Sector rule (6.1):** *time-based* — must hold largest-in-sector for **two consecutive**
  re-composition periods; or *value-based* — exceed the incumbent by **≥ 10%** of free-float value.
- **Capitalization rule (6.2):** time-based only — must exceed the lowest cap-selected member for
  **two consecutive** periods, then *"automatically pushes out the lowest cap selected stock"*.
- **Special re-composition (6.3):** off-cycle for delisting, mergers, schemes of arrangement.

**C6. Single-constituent weight cap — UNVERIFIED / none found.** The brochure has no capping
section. The only percentages in it are the 2% entry threshold and the 10% sector rule — neither
is a weight cap. **Publishing language: "PSX's published methodology does not specify a cap on any
single constituent's weight"** — a statement about the document, which is true. Do **not** write
"there is no cap" as a statement about reality, and do not import capping rules from KMI-30 or
MSCI-style methodologies.

---

## Source ledger

| # | Document | Version | URL |
|---|---|---|---|
| 1 | PSX Regulations (Rule Book) | **9 Feb 2026** | [link](https://www.psx.com.pk/psx/themes/psx/uploads/PSX-Regulations-February-09-2026.pdf) |
| 2 | PSX Rule Book (T+2 comparator) | 15 Feb 2023 | [link](https://www.psx.com.pk/psx/themes/psx/uploads/PSX_Rulebook_\(updated_on_Febrary_15,_2023\).pdf) |
| 3 | NCCPL Circular NCCPL/CM/FEBRUARY-26/01 | 2 Feb 2026 | [link](https://www.nccpl.com.pk/storage/sections/files/01KGKV97N2SY3JNATCYZEDR77X.pdf) |
| 4 | NCCPL Clearing & Settlement Services (NDM) | undated | [link](https://www.nccpl.com.pk/en/products-services/clearing-settlement-services) |
| 5 | PSX Notice PSX/N-403 (BAFL split example) | 10 Apr 2026 | [link](https://dps.psx.com.pk/download/attachment/273940-1.pdf) |
| 6 | PSX ex-price formulas | 5 Jan 2016 | [link](https://www.psx.com.pk/psx/themes/psx/uploads/priceCalMethod.pdf) |
| 7 | KSE-100 Index Brochure | June 2025 — stale on ex-price timing | [link](https://www.psx.com.pk/psx/themes/psx/uploads/KSE-100-and-KSE100-PR-Brochure-Jun-2025-Updated.pdf) |

**Access note:** nccpl.com.pk sits behind Cloudflare and returns 403 to automated fetching. Its
quotes were obtained via a same-origin `fetch()` from inside a real browser tab. Budget for that
on re-verification.
