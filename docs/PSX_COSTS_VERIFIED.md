# PSX transaction costs & taxes — verified rates

Source of truth for any published calculator or article that quotes a Pakistani rate.

**The rule (CLAUDE.md Rule 2, applied to published content): nothing in here may come from a blog,
a news article, or another calculator.** Every figure carries a primary source and a confidence
marker. Anything marked UNVERIFIED does not get published — it gets shown as a user input, or
omitted and labelled, never filled with a plausible guess.

Verified 20–21 July 2026 for tax year 2026-27.

---

## 1. Broker commission — a regulated RANGE, not a free market

PSX prescribes a floor and a ceiling. A broker quoting below the floor is non-compliant, not cheap.

**Source:** PSX Regulations, clause 4.28 + Annexure-III to Chapter 4 —
[PSX-Regulations-February-09-2026.pdf](https://www.psx.com.pk/psx/themes/psx/uploads/PSX-Regulations-February-09-2026.pdf)
(Annexure-III at PDF p.71). Effective 9 Feb 2026; identical text in the prior 27 Aug 2025 rulebook,
so the scale has been stable across the change. **VERIFIED PRIMARY.**

| Transaction | Minimum | Charged on |
|---|---|---|
| Ready Market — normal | **max(PKR 0.03/share, 0.15% of value)** | buy **and** sell |
| Ready Market — intra-day squared | same | **one side only** |
| Fixed Income ETF — normal / squared | max(PKR 0.01/share, 0.01%) | both / one side |
| Deliverable Futures — normal / squared | max(PKR 0.03/share, 0.15%) | both / one side |
| Ready leg financed via MTS/MFS/Murabaha | max(PKR 0.03/share, 0.15%) | Ready leg only |
| Ready↔Future arbitrage | **no minimum** | — |
| Proprietary; sponsor/director + immediate family | **no minimum** | — |

**Ceiling: 2.5% of transaction value.** Commission is *exclusive of levies*. The range exists under
a CCP exemption from s.4 of the Competition Act 2010.

## 2. Exchange and regulator charges

**Source:** [PSX Schedule of Charges, updated 18 Dec 2024](https://www.psx.com.pk/psx/themes/psx/uploads/Schedule-of-Charges-Updated-as-on-December-18-2024.pdf)
— the only Schedule of Charges linked from the live PSX legal-framework page. **VERIFIED PRIMARY**
except where noted.

| Item | Rate | Note |
|---|---|---|
| PSX trading fee | **PKR 3.50 per PKR 100,000** (0.0035%) | per settlement day, both sides |
| SECP levy | **PKR 0.65 per PKR 100,000** (0.00065%) | per settlement day, both sides |
| CVT | **0.00%** | see §4 |
| Advance tax | **0.00%** | in lieu of brokerage commission |
| Sales tax on the trading fee | applicable notified rate | on the **fee amount**, not turnover |
| Regulatory fee | 0.62084 per PKR 100,000 | ⚠️ **UNVERIFIED — do not publish** |

**Regulatory fee caveat.** The schedule says the fee "shall be discontinued" with effect from
29 Aug 2025 or when the Customer Compensation Fund falls below an SECP-specified balance,
whichever comes first. That date has passed and no confirming notice was found. Publish neither
0.62084 nor zero until confirmed.

## 3. Sales tax on brokerage — the number most calculators get wrong

**Sindh: 15%** on tariff heading 9819.1000 ("Stockbrokers, future brokers and commodity brokers").
Statutory and effective rate both 15%; no concession or exemption notification.
**Source:** [SRB Working Tariff, amended to 10 July 2024](https://www.srb.gos.pk/srb/wp-content/uploads/2024/07/Final-Working-tariff.pdf), Part B p.13. **VERIFIED PRIMARY.**

> The **13%** figure circulating in press coverage is the pre-2024 rate and is stale.

**Federal Excise Duty does NOT apply in Sindh.** The Federal Excise Act 2005 First Schedule Table II
serial 13 charges 16% on stockbroker services, *but* the Note to that table disapplies FED "in a
Province where the provincial sales tax has been levied thereon". Sindh levies SST on 9819.1000,
so FED is not chargeable there. **VERIFIED PRIMARY** —
[FED Act 2005 to 30 Jun 2025](https://download1.fbr.gov.pk/Docs/202588138517680FEDAct,2005withindexupdatedupto30-06-2025.pdf), p.87.

Punjab (PRA) rate: **UNVERIFIED**. Only relevant for a Punjab-situs broker; PSX brokers are
overwhelmingly Sindh-registered.

### ⚠️ The base, not the rate, is the common error

The 15% attaches to the **brokerage commission** — the broker's taxable service. It is **not** a
percentage of trade turnover. Separately, sales tax applies to the **trading fee amount**.

Applying sales tax to turnover is, per the research, the single most common defect in published
PSX cost calculators. Getting it right is a differentiator.

## 4. Capital gains tax — s.37A

**Source:** Income Tax Ordinance 2001 s.37A + Division VII Part I First Schedule; Finance Act 2026
(Act XLIII of 2026, assented 26 Jun 2026, in force 1 Jul 2026).
FA2026 did **not** amend the s.37A rate table.

| Acquired | Rate |
|---|---|
| Before 1 Jul 2013 | **0%** (proviso ii) |
| 1 Jul 2013 – 30 Jun 2022 | **12.5%** flat, any holding period (proviso i) |
| 1 Jul 2022 – 30 Jun 2024 | **Taper live**: ≤1yr 15% · 1–2yr 12.5% · 2–3yr 10% · 3–4yr 7.5% · 4–5yr 5% · 5–6yr 2.5% · >6yr 0% |
| On/after 1 Jul 2024 | **15% flat**, ATL on both acquisition and disposal dates |

All **VERIFIED PRIMARY**. By July 2026 the 2022–24 tranche is at most ~4 years old, so only the
15%→5% bands are reachable.

### Non-filer CGT — UNRESOLVED, DO NOT PUBLISH A NUMBER

Every figure circulating on the open web (16% / 20% / 25% / 30%) is wrong. The statute has never
specified a flat non-filer rate: Division VII col (4) points at the **Division I slab rates** with a
proviso that the rate "shall not be less than 15%" — so base is slabs, floor 15%, ceiling 45%.

FA2026 s.5(47)(b)(ii) **omitted Tenth Schedule rule 10 clause (y)**, the carve-out that had shielded
s.37A from the non-ATL uplift. FBR's own
[Budget 2026-27 Salient Features](https://fbr.gov.pk/Budget2026-27/SalientFeatures/Salient-Feature.pdf)
confirms: the exclusion "has been withdrawn." Tenth Schedule rule 1 increases non-ATL rates "by
hundred percent".

**What is unresolved:** whether that doubles the 15% floor (→30%) or the whole slab scale (→30–90%,
which would be absurd). **No FBR circular for FA2026 exists yet** — the circulars index still ends
at 2025, and last year's equivalent landed 4 Aug 2025.

📅 **Diary: FBR Circular 01 of 2026-27, expected early Aug 2026.** Publish the mechanism and a
range until then, never a single number.

### CGT collection mechanics

- s.100B + Eighth Schedule: **NCCPL** collects and deposits, not the investor.
- Income Tax Rules 2002 rule 13N(10): collected **monthly**, on transactions settled that month —
  *not* trade-by-trade at settlement.
- 13N(11): collected from or through the clearing member (the broker).
- 13N(5): **FIFO** cost basis; same-day trades averaged.
- 13N(8): NCCPL adds/deducts a deemed **0.5% of consideration** in lieu of brokerage/commission/
  transaction fees for client trades.
- **FA2026 abolished the investor opt-out** (Eighth Schedule rule 5 omitted) — NCCPL collection is
  now mandatory.
- s.37A(4): securities gains are a **separate block**; losses offset only securities gains and carry
  forward a maximum of **3 years**.

## 5. Dividend withholding — s.150

Division I Part III First Schedule. **FA2026 made no change** to this division.

| Dividend | Filer | Non-filer |
|---|---|---|
| Ordinary cash, and REIT | **15%** | 30% *(inferred)* |
| IPP pass-through (CPPA-G reimbursed) | **7.5%** | 15% *(inferred)* |
| Mutual funds | 25% / 15% by debt vs equity proportion; corporate recipient debt component 29% | doubled *(inferred)* |
| SPV under REIT Regs 2015 | 0% to a REIT scheme; 35% to others | — |
| Company paying no tax (exemption, loss c/f, credits) | **25%** | doubled *(inferred)* |

Filer rates **VERIFIED PRIMARY**. Non-filer figures are **INFERRED** — s.150 is not in the Tenth
Schedule rule 10 exclusion list so rule 1's uplift applies on its face, but FBR has published no
table. Footnote them.

## 6. Settlement — T+1

**VERIFIED PRIMARY.** Effective **9 February 2026**. PSX Regulations v09-Feb-2026 amendment history
item 59; clause 2.4(lxxvii) defines a Ready Market Contract as settling "on T+1 settlement cycle";
Chapter 10 (10.5.1, 10.5.2(c), 10.6) matches. A sweep of all 225 pages found **zero** remaining
T+2 references.

Corroborating: NCCPL circular NCCPL/CM/OCTOBER-25/17 (24 Oct 2025) via
[dps.psx.com.pk](https://dps.psx.com.pk/download/attachment/263279-1.pdf); PSX notice PSX/N-191
(10 Feb 2026) showing the live matrix — Continuous Auction T+1, Negotiated Deals T+0.

Caveats: no gazette/SRO number located; **leverage/MTS segment coverage UNVERIFIED**.

## 7. Still UNVERIFIED — CDC and NCCPL

Both sites sit behind Cloudflare bot-detection that blocks automated retrieval of the PDF paths
(HTML scrapes fine; documents 403). **We do not bypass bot detection**, so these must be downloaded
manually in a normal browser.

**CDC** — from https://www.cdcpakistan.com/downloads-category/tariff-fee-structure/
- CDS Schedule of Fees, 14 Mar 2025 (participant/broker-side: transaction, custody, handling)
- Investor Account Services Schedule of Fees, Dec 2024 (direct investor account: annual fee etc.)

**NCCPL** — from https://www.nccpl.com.pk/downloads ("Schedule of Fees and deposits")
- NCCPL Regulations — Fee Charges and Deposits Schedule, 8 Jan 2026
- Centralized KYC Organization — Fee Charges and Deposits Schedule (biometric/KYC and UIN fees)

Admission fee, biometric/KYC fee, annual fee, per-trade clearing fee: **all UNVERIFIED.**

## 8. Incidence — who the law actually charges

The PSX trading fee, SECP levy and regulatory fee are levied on **TRE Certificate Holders (brokers)**
and collected by payment order on settlement day. The schedule does **not** state they are
client-borne. The CDC CDS tariff is likewise a *participant* tariff.

Brokers generally pass these through, but the regulated fact is what the **broker** owes. Any
calculator presenting them as investor costs must label them as **customary pass-through**, not as
a prescribed client charge.
