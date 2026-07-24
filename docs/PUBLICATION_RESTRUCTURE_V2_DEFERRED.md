# Deferred go-live checklist — money + PSX data licence (design-only)

**Companion to** [`PUBLICATION_RESTRUCTURE_V2.md`](PUBLICATION_RESTRUCTURE_V2.md). That doc's §7–§8
hold the full reasoning; this is the short, sequenced gate list. **Nothing here is switched on.**
The owner and a lawyer own every step below.

## Two separate exposures — do not conflate them

1. **SECP research-service exposure (product shape)** — **addressed by the V2 build pass.** The
   product now sits inside the Reg 2(h) general-commentary exemption: no published entry/stop/target
   on a named security (§1), reader derives their own levels in a client-side tool (§2), the Desk
   Room ends on the bull/bear debate with no Chair verdict or dated call (§3), the desk's own
   scorecard no longer tracks per-named-stock calls (§4), and `legal.json` states the positive 2(h)
   basis and non-registration (§5).
2. **PSX market-data exposure (commercial)** — **NOT addressed and must not be assumed closed.**
   The free `dps.psx.com.pk` scrape has no data licence. This is a separate commercial track
   requiring a contract, a fee, and a legal entity. Shipping the design pass does **not** clear it.

## The sequence — each step gates the next; billing stays OFF until all are done

- [ ] **0 · Lawyer sign-off (the gate for everything below).** A Pakistani lawyer reviews the
      amended [`state/legal.json`](../state/legal.json) **and the product exactly as it ships**, and
      the four open questions in `PUBLICATION_RESTRUCTURE_V2.md` §10. `review_status` stays `DRAFT`
      until this happens. Pursue free channels first (P@SHA / PSEB, NIC incubator legal advisory);
      a written SECP query describing the shipped product is the belt-and-suspenders option.
- [ ] **1 · Incorporate the entity.** Single-Member Company (SMC), private limited, via SECP
      eServices. **Object clause: information technology / data services / publishing — NOT
      "securities advisory" or "research analyst."** (Full rationale: main doc §7.)
- [ ] **2 · Company NTN (FBR) + business bank account** in the company name.
- [ ] **3 · PSX data licence — as the entity.** Email `marketdatarequest@psx.com.pk` **as the
      company**, requesting the **delayed / EOD website-display** tier (not real-time) and its fee
      schedule. Do not budget a fee number until PSX sends the quote. (Main doc §8.)
- [ ] **4 · Sign + pay the annual data fee; move the price source onto the licensed feed;** stop the
      commercial use of the free DPS portal.
- [ ] **5 · Only now wire billing.** All-paid + trial model is already scoped. Confirm the local
      gateway (Safepay / PayFast, or a merchant-of-record like Paddle / Lemon Squeezy if it supports
      PK payouts) actually supports card-on-file / recurring before promising auto-renew.

## Hard rules for this track

- **Do not charge on data scraped from the free DPS portal.** The free period covers the desk only
  while unincorporated/unlicensed. Billing must not switch on before steps 1–4 (and step 0).
- **Do not publish or budget a PSX data-licence fee** until PSX sends the schedule — it is a quote,
  not a judgment.
- **`legal.json.review_status` stays `DRAFT`** until step 0 is genuinely done.
- The desk's own computed output (indicators, backtests, fair values, scores, prose) is the owner's
  IP; what PSX licenses is the raw price/market data. You still need *a* licensed price source.
