# Henneth — Launch, Audit & Subscription Playbook

Compiled 2026-07-15. Sources: the live site (`https://desk.henneth.app`, audited page by page today), the project's own docs (`README.md`, `CLAUDE.md`, `DEPLOY.md`, `CHANGELOG.md`, `docs/PRODUCT-ROADMAP.md`, `docs/GO-PRIVATE.md`, `docs/OPERATIONS.md`, `docs/SYSTEM-REGISTRY.md`, the GitHub Actions workflow), a prior strategy conversation you pasted in, and fresh verification against PSX's and SECP's own pages. Where the internal docs and the live site disagreed, the live site wins — this doc corrects a couple of stale assumptions below.

This is not legal advice. It's a structured brief so a lawyer conversation takes 30 minutes instead of 3 hours.

---

## 0. The one-paragraph status check

You've built more than either of your two source materials (the roadmap doc, the pasted strategy chat) gives you credit for. Hosting is already on Vercel, the repo is already private, Supabase auth + per-user watchlists already exist, disclaimer language is already live on every page, and — contrary to what the pasted strategy chat assumes — **your price/quant/backtest data already refreshes on GitHub's servers 24/7**, not just "while your laptop is open." What's still missing is entirely on the business side: no data licence, no ToS/Privacy/Risk pages, no billing, and a leaderboard that's 2 days old. None of that is a coding problem.

---

## 1. THE LAUNCH BLOCKER — read this before anything else

**You do not currently have the legal right to charge anyone for this product.**

I verified this directly against PSX's own site today, not just the pasted chat's claim. PSX's Data Services Vending page states plainly: dissemination, transmission, sale, and commercial use of its market data feed — live or delayed, including prices, volumes, and index levels — is prohibited without a licence, and PSX "reserves its right to prevent such breaches... and initiate civil and criminal legal proceedings." That is not boilerplate; it's the same clause your competitors (UpInvest, Investify) publicly display licence badges to get around.

Two things compound this, specific to how this project is actually built:
- Your prices come from the **DPS portal** (scraped) and **Yahoo Finance `.KA` tickers** (per `README.md`, "Data & stack"). Neither is a licensed PSX feed. Yahoo's own terms also restrict redistribution of its data — a second, separate licensing problem if you ever charge for anything derived closely from that feed.
- `CLAUDE.md` confirms intraday decisions use `state/live.json` sourced from DPS directly. That is the exact "any website or application" scenario PSX's notice targets.

**Action this week:** email **marketdatarequest@psx.com.pk**, ask for (a) the Data Display Licence terms and (b) EOD summary-data pricing for a small web platform. Two framing points worth using in that email:
1. Your product is daily-timeframe only (confirmed by `CLAUDE.md` rule 3 — no intraday scalping), so you need EOD, not Level 1/2 real-time — EOD is materially cheaper everywhere in the world.
2. Your paid layer is **derived output** (fair value, scores, backtests, the debate transcripts) — a different legal category from raw price redistribution. Structure pricing so raw prices stay in the free/licensed thin layer and the paid layer is your analysis.

**Until you have that licence or written clarity from PSX, don't take money.** Everything past this section assumes you're running that conversation in parallel.

---

## 2. Legal & compliance — everything you need to know

### 2.1 PSX market data licence
Covered above. This is the highest-priority item on this entire document. Nothing else de-risks it.

### 2.2 SECP — are you an "investment adviser"?
I checked SECP's own Securities & Futures Advisors page directly. The trigger for licensing is functional, not about format: *"The Role of securities advisor... is to give investment advice to others,"* licensed under the **Securities and Futures Advisors (Licensing and Operations) Regulations, 2017**. SECP's public page does **not** carve out an explicit exemption for educational/research content — it simply doesn't address the distinction. That ambiguity is exactly why `docs/PRODUCT-ROADMAP.md` already flags "get a Pakistani lawyer to confirm the research-tool framing keeps it outside SECP investment-adviser licensing" as a pre-launch step — that line is correct and still unresolved.

Your product design already leans the right way for this argument: `CLAUDE.md` rule 5 bans "buy/strong buy/guaranteed" language and the live site backs it (see §3 audit — "below/above model fair value," never "cheap/buy"). That's the right posture, but posture isn't a legal opinion. Get one before charging.

Relevant reading if you want to hand your lawyer sources directly:
- [Securities' and Futures' Advisors — SECP](https://www.secp.gov.pk/licensing/capital-markets/securities-advisors-and-futures-advisor/)
- [Securities and Futures Advisers Regulations, 2017 (PDF, via PSX)](https://www.psx.com.pk/psx/themes/psx/documents/legal-framework/SECP/regulations/securities-&-futures-advisers-regu-2017/SecuritiesFuturesAdvisersReg2017.pdf)

### 2.3 Business registration
You need a registered entity before you can legally invoice subscribers or open a business bank/merchant account. Two realistic options in Pakistan:
- **Sole proprietorship** — cheapest, fastest (FBR/NTN + bank letter), but no liability separation between you and the business. Fine for a pre-revenue test, weak once you're taking subscriber money and publishing broker scorecards that could draw a complaint.
- **Single Member Company (SMC-Private Limited)** via SECP — limited liability, more credible to a payment gateway and to PSX when you request a data licence, roughly similar admin burden to a private company. This is what the pasted strategy chat recommended, and it's the right call given you're (a) taking payment and (b) publicly grading brokers by name — liability separation matters here.

Recommendation: **register an SMC-Pvt Ltd** before you request the PSX licence — PSX and payment gateways will both want to contract with a legal entity, not an individual.

### 2.4 ToS / Privacy Policy / Risk Disclosure — not yet built
I checked the live site for these directly: there is a disclaimer **banner** on every page ("Research, not advice... Losses are expected") but **no dedicated Terms of Service, Privacy Policy, or Risk Disclosure page**, and no footer links to any. `docs/PRODUCT-ROADMAP.md` lists these as an unbuilt "Build order" item — confirmed still true on the live site today.

You need three separate documents, drafted or reviewed by an actual Pakistani lawyer (the pasted chat estimates PKR 30–60k, one hour — reasonable for a template pass):
- **Terms of Service** — no-advice framing, no execution, subscription/refund/cancellation terms, IP notice on your derived data (fair value, scores), acceptable-use for your broker leaderboard (defamation risk — see 2.5).
- **Privacy Policy** — what you collect via Supabase Auth (email, watchlist, portfolio entries), retention, third parties (Supabase, your payment gateway, any email provider).
- **Risk Disclosure** — investing in PSX carries risk of capital loss, past performance ≠ future results, the desk's own scored record includes losses.

### 2.5 A risk the pasted chat didn't cover: defamation/reputational exposure from the broker leaderboard
You're publicly, factually ranking named brokers (Topline, etc. — already live under "Broker calls on the record") on accuracy. This is your best differentiator, but it is also the one feature most likely to draw a legal letter from a brokerage that scores badly. Two mitigations, both already partly in place per your own rules: (1) only score **factual, dated, sourced** calls — `CLAUDE.md`'s "all numbers from the data layer" rule already enforces this; (2) get your lawyer to specifically bless the leaderboard's wording (factual scoring vs. editorializing) as part of the same ToS review, not as an afterthought.

### 2.6 Payment processing
Stripe does not onboard Pakistani entities cleanly (confirmed by the pasted chat and consistent with known Stripe country support). Realistic options for a Pakistani SMC:
- **Safepay** or **PayFast** — local cards + easypaisa/JazzCash. I checked Safepay's subscriptions product page directly: it advertises recurring billing, renewal automation, and failed-payment retry logic, but does **not** publish KYC/onboarding-document requirements or pricing on the public page — you'll need to talk to their sales team directly for merchant-account requirements (expect: SECP incorporation certificate, bank account, NTN, one director's CNIC).
- **2Checkout or Paddle** — if you want to capture Roshan Digital Account (overseas Pakistani) subscribers in USD; those platforms handle merchant-of-record tax complexity for you but take a larger cut.
- Whichever you pick, get their KYC document checklist **before** you finish registering your company, so you register with the right structure the first time.

### 2.7 Tax treatment
If any of your subscriber base is overseas (the RDA / overseas-Pakistani segment the pasted chat flagged as your best segment), your income may qualify for Pakistan's **IT/IT-enabled export services tax treatment** (reduced ~0.25% rate under the FBR's export-of-services regime, subject to PSEB registration and repatriation through proper banking channels). This is a real, current program — worth a direct question to your accountant/lawyer rather than assuming eligibility, since it depends on invoicing structure and foreign-currency remittance proof. Domestic PKR subscription revenue is ordinary business income, taxed normally under your registered entity.

### 2.8 Data protection
Pakistan does not yet have a data protection law in force — the **Personal Data Protection Bill** has been through cabinet approval and drafts but has not been enacted as of this check. Practical takeaway: you're not yet bound by a PDPA-style statute, but Supabase (EU/US-hosted infrastructure) means you're likely touching GDPR-adjacent expectations for any user who is an EU resident, and writing a real Privacy Policy now (2.4) means you won't have to retrofit one when the bill does pass.

### 2.9 Scraping and the Prevention of Electronic Crimes Act (PECA) 2016
A secondary, lower-probability legal angle: PECA criminalizes "unauthorized access" to an information system. If DPS's own terms of use explicitly prohibit automated scraping (worth checking directly, separate from the market-data-redistribution clause in §1), continuing to scrape after a licence refusal — rather than before you've asked — is the version of this that actually creates exposure. This is one more reason the PSX licence conversation in §1 should happen before commercial launch, not after: it converts a "did we have permission" question into a settled one.

---

## 3. Complete product audit (live site, checked page by page today)

### What's actually live and working
- **Today** — daily macro/sector read, sectors-to-watch table, key risks, named tickers with backtest stats. Rendering correctly, real data (KSE-100 -3.56% Hormuz-blockade narrative, live global tape ticker).
- **Board** — universe heatmap, proven-strategy setups (entry/stop/target/size), news wire, predictability table. All populated with live numbers.
- **Scores / leaderboard** (routed at `#/leaderboard`, not `#/scores` — see UI note below) — desk-analyst and broker call tracking is live and structured correctly.
- **Accounts** — Supabase Auth sign-in button present and wired (not deep-tested past that, per your instruction not to trigger flows that need real credentials).
- **Disclaimers** — "Research · not advice" badge in the topbar and a closing disclaimer line on every page body I checked. No-advice language audit from `CHANGELOG.md` (2026-07-12 entry) checks out live: fair-value verdicts read "below/above model fair value," not "undervalued/cheap."
- **Cloud-independent data refresh** — confirmed via `.github/workflows/desk-data.yml`: prices/quant/backtests/fair-value already refresh every 30 min on GitHub's servers, market hours, Mon–Fri, with a preflight gate before publish and a post-deploy watchdog check. This directly contradicts the pasted strategy chat's assumption that "the loops run while the Claude app is open" — that's true only for the **AI analyst/debate layer** (Desk Room, daily read), not the core price data.

### Verified findings — what needs attention before charging

| Finding | Detail | Severity |
|---|---|---|
| **Leaderboard has no track record yet** | Confirmed live: "Scoring calls since 2026-07-13 · 2 days on the record," 36 calls pending, **0 resolved**. Your own pitch is "we grade ourselves" — an empty leaderboard is a claim, not proof. The pasted strategy chat's advice to wait 8–12 weeks before charging is directly validated by what's live right now. | High — blocks paid launch, not free launch |
| **`#/scores` is a dead route** | Navigating directly to `https://desk.henneth.app/#/scores` silently falls back to the Board view instead of the leaderboard (the actual working route is `#/leaderboard`). Minor, but if you ever link `/scores` from a tweet or ad, it'll land people on the wrong page with no error. | Low — cheap fix, worth doing before any public leaderboard-led launch push |
| **No ToS / Privacy / Risk Disclosure pages** | No footer links found on any page checked. Confirmed against `docs/PRODUCT-ROADMAP.md`'s own "Build order" list — still open. | High — legal, not cosmetic (see §2.4) |
| **AI analyst layer still laptop-dependent** | Per `README.md`'s own loop table, the Daily read and Desk Room debates run "locally (while the Claude app is open)." Only the deterministic price data is cloud-independent (see above). If your laptop is off, "Today"'s narrative and new debates go stale even though prices stay fresh. Paying users will notice a stale "Today" read faster than a stale price. | Medium-high — the pasted chat's #2 "three things that decide this" item, still partially open |
| **No billing/plan-gating layer** | Nothing in the codebase (`README.md`, `PRODUCT-ROADMAP.md`) indicates Stripe/Paddle/Safepay integration exists yet. This is 100% of what's needed to actually run a subscription. | High — the literal blocker for "I want to run a subscription" |
| **No email digest infrastructure** | Flagged as unbuilt in `PRODUCT-ROADMAP.md` item 3. Without it, you have no retention mechanic and no legally-required "collect an email on the free tier" funnel. | Medium — retention, not a legal blocker |
| **Company description / financial trend charts missing** | Flagged honestly in `CHANGELOG.md` as "not built (no data — deliberately not faked)." This is good practice (no fabrication) but is a real gap versus Sarmaaya/Investify, who show revenue/earnings trend lines. | Medium — competitive gap, not urgent |
| **Universe heatmap grid renders low-contrast until interacted with** | On the Board page the ticker grid initially renders in pale, low-contrast text (screenshot-verified) — readable but noticeably weaker than the surrounding UI's otherwise sharp mono-terminal contrast. Given `CHANGELOG.md` already fixed one contrast bug (`.sub{opacity}` issue on 2026-07-12), this may be an intentional "unhovered" state, but it's worth a deliberate design pass rather than leaving it ambiguous. | Low |

### Design/UI system observations (you're the expert here — treat these as notes, not directives)
- The "hard corners, JetBrains Mono, Bloomberg-lite" design language is consistently applied across every page I checked — no visible drift, which the `design-reviewer` agent and `design_lint.py` gate (per `SYSTEM-REGISTRY.md`) are clearly earning their keep on.
- There's no visible mobile breakpoint check possible from this session (I audited at desktop width only) — `CHANGELOG.md` mentions a prior "mobile header horizontal-scroll fix," so mobile has had at least one real bug already; worth a dedicated pass on a phone before public launch given a large share of your target user (per the pasted chat's own market read) is on YouTube/WhatsApp-first mobile devices.
- Chrome-extension fragility: `CHANGELOG.md`'s 2026-07-12 entry documents a real production incident where a Chrome ad/anti-fraud extension broke `fetch()` on ticker pages for at least one real user session. The fix (XHR fallback) is in; worth explicitly QA-ing with a couple of common ad-blocker extensions active before launch, since you can't control what extensions your paying users run.

---

## 4. Launch steps — sequenced

**Phase 0 — Legal & business foundation (do this before writing any more product code)**
1. Register the business as an SMC-Pvt Ltd with SECP (§2.3).
2. Email `marketdatarequest@psx.com.pk` for the Data Display Licence + EOD pricing (§1). Do this the same week as #1 — it's the longest lead-time item.
3. Get a Pakistani lawyer for: SECP investment-adviser exposure opinion (§2.2), ToS, Privacy Policy, Risk Disclosure, and a specific read on the broker-leaderboard wording (§2.5). Budget ~PKR 30–60k, ~1 hour of their time if you hand them this document.
4. Pick a payment processor (Safepay or PayFast for local; add Paddle/2Checkout later for overseas) and get their onboarding document checklist before finalizing your SECP paperwork, so the entity structure matches what they need.

**Phase 1 — Product hardening (parallel to Phase 0)**
5. Publish real ToS/Privacy/Risk Disclosure pages once drafted, linked from the footer on every page.
6. Fix the `#/scores` route so it either redirects to `#/leaderboard` or renders the same view (§3).
7. Decide, deliberately, whether the AI analyst layer (Today's read, Desk Room debates) stays laptop-dependent or moves to a cloud runner (`DEPLOY.md` already scopes this: add `ANTHROPIC_API_KEY` as a GitHub secret + a `claude -p` runner — a few $/month). If you're about to charge for freshness, this stops being optional.
8. Build the billing/plan-gating layer against whichever processor you picked in step 4.
9. Build email-digest infrastructure (Supabase edge function + Resend/Postmark free tier, per `PRODUCT-ROADMAP.md`'s own plan).

**Phase 2 — Prove the leaderboard before charging**
10. Let the Scores/leaderboard run publicly, unpaywalled, for **8–12 weeks minimum** until a meaningful number of calls have resolved. Post it weekly on your own account as a pre-launch marketing asset (see Appendix — this is literally free distribution and it's already partly live).
11. Only start charging once (a) the PSX licence question is resolved in writing, (b) the lawyer has signed off on the SECP/advice framing, (c) ToS/Privacy/Risk pages are live, (d) billing works end to end in a sandbox, and (e) the leaderboard has real resolved-call history.

---

## 5. Pre-launch verification checklist

Run this as a literal checklist before flipping any paywall on:

- [ ] PSX Data Display Licence obtained, or written confirmation from PSX that your current data sourcing + derived-data framing is acceptable
- [ ] SECP investment-adviser exposure — lawyer's written opinion on file
- [ ] SMC-Pvt Ltd registered, bank account open
- [ ] ToS, Privacy Policy, Risk Disclosure live and linked from every page's footer
- [ ] Payment gateway account approved (not just "applied") with subscription/recurring billing tested in sandbox
- [ ] Free → paid plan gating works and fails safe (a billing error should never expose paid content for free, or lock out a paying user)
- [ ] Cancellation/refund flow works and matches what the ToS promises
- [ ] `preflight.py` passing on the last deploy (this one's already automated — just confirm it's green)
- [ ] Leaderboard has ≥8 weeks of public history with at least some resolved calls (not just pending)
- [ ] `#/scores` → `#/leaderboard` routing fixed
- [ ] Mobile pass done on at least one real phone (not just a resized desktop browser)
- [ ] Ad-blocker/extension resilience re-tested (the `fetch()` → XHR fallback from `CHANGELOG.md`) on 2–3 common extensions
- [ ] Data-freshness timestamp visible on every page that shows a price, dated as of the actual last refresh
- [ ] Status page or visible fallback messaging for when DPS (your price source) is down

---

## 6. Feature roadmap

Reconciling the internal `PRODUCT-ROADMAP.md`, the pasted strategy chat, and what I found live — organized by when it should happen, not by who proposed it.

### Must-ship before any paid tier
- Billing + plan gating (§4 step 8)
- ToS/Privacy/Risk pages (§4 step 5)
- Cloud-independent AI analyst layer, or an honest "last analyst update" timestamp if you keep it laptop-dependent
- Data-freshness stamp on every page
- A visible status/fallback page for DPS outages

### Months 2–6 (post-launch, retention & completeness)
- Email digest ("what changed on your watchlist this week") — the actual retention spine per both the roadmap doc and the pasted chat
- Company description + multi-year financial trend charts (needs a new fundamentals-history scraper — flagged honestly as a real data gap in `CHANGELOG.md`, not fabricated in the meantime, which is the right call)
- PWA-ify the SPA before considering a native app — cheap, and matches how your actual users will access this (mobile-first, per the pasted chat's market read)
- Screener with saved filters
- Price/event alerts
- Dividend income planner
- **Shariah-compliance filter (KMI-30 based)** — flagged by the pasted chat as "non-negotiable in this market" and factual (so legally low-risk) — I'd move this up in priority given how much of the retail PSX audience screens for this
- Zakat calculator on portfolio holdings
- CGT / filer-status tax view

### Months 6–12
- Mutual funds & ETFs coverage
- Full-text company filings search
- Public API for the derived scores (careful: this re-opens the data-redistribution question in §1 if the API exposes anything close to raw prices — loop your PSX licence conversation back in before shipping this)
- Native app, only if PWA retention data actually justifies it

### UI fixes (from today's audit — see §3 for full detail)
- Fix `#/scores` dead route
- Re-check universe-grid contrast on Board (design-reviewer/design_lint pass)
- Dedicated mobile QA pass beyond the one prior fix already shipped
- Confirm ad-blocker/extension resilience holds under new load

### Explicitly do not build (per your own `CLAUDE.md` rules and the pasted chat's read — both agree)
- Any order execution, auto-trading, or copy-trading — changes your regulatory category entirely
- Signals sold as calls, or anything phrased as a recommendation
- Anything discretionary on the user's behalf

---

## 7. Pricing plan

Market-sized against what's actually verifiable: Pakistan has roughly 500,000 registered PSX investors; a realistic serviceable paid-research audience is 20,000–50,000 people. At a 1% conversion that's 200–500 subscribers — this is a PKR 2–6M/year business at first, not a PKR 50M one. Price and spend accordingly; this number should set your engineering budget too, not just your pricing.

**Free forever** (your SEO/acquisition engine, not a trial)
Today's read, Board heatmap, news, macro, dividend/earnings calendars, one scorecard per day, the **full Scores leaderboard including broker rankings**, all blog/content. Keeping the leaderboard free is the whole marketing strategy — it's the proof, and it's already live today.

**Desk — PKR 1,500/mo or PKR 12,000/yr** (annual ≈ 33% off; push annual for cash flow and churn)
Unlimited scorecards + fair-value working, watchlist with alerts, portfolio tracker, weekly "what changed" digest, Desk Room house views.

**Desk Pro — PKR 4,000/mo or PKR 32,000/yr**
Full debate transcripts, all 52 strategies with per-stock backtests, screener with saved filters, data export, dividend income planner, filing digests, priority on new coverage.

Structural notes:
- No lifetime deals, ever.
- 7-day free trial on Pro only, card required; Desk's free tier *is* the trial for that tier.
- Founding-member offer: first 100 subscribers lock their price forever — creates urgency without discounting the brand.
- Consider USD pricing for the overseas-Pakistani/RDA segment once you add a USD-capable processor (2Checkout/Paddle) — that segment has hard currency and, per the pasted chat's competitive read, no good research tool serving them today.
- **Do not open Desk/Desk Pro billing until §6's "must-ship before any paid tier" list is done and the leaderboard has real history (§4 step 10).**

---

## 8. Subscription launch — the legal action list, in order

1. Register SMC-Pvt Ltd (SECP).
2. Send the PSX Data Display Licence request email; don't proceed to charging until resolved (§1).
3. Retain a lawyer for the SECP-advisor opinion + ToS/Privacy/Risk Disclosure drafting + leaderboard wording review (§2.2, §2.4, §2.5).
4. Open a business bank account under the new entity.
5. Apply to Safepay or PayFast (local) with the entity's SECP certificate, NTN, and bank details; add Paddle/2Checkout later for USD/overseas.
6. Publish ToS, Privacy Policy, and Risk Disclosure live, linked in the footer.
7. If courting the overseas-Pakistani segment, register with PSEB to claim IT-export tax treatment on that portion of revenue, and confirm the invoicing/remittance structure with your accountant (§2.7).
8. Only then: flip the billing switch.

---

## Appendix — context carried over from the prior strategy conversation

This wasn't independently re-verified today but is worth keeping attached since it shaped the roadmap and pricing above:

- **Competitors, ranked by threat:** Sarmaaya (closest analogue, subscription + courses, 188k FB audience, but has reputational complaints about discretionary account management — exactly the trap your research-not-advice stance avoids), UpInvest (sharpest young competitor, already licensed and already occupying your positioning — worth reading their site closely before you finalize messaging), Investify (free-tracking scale play, not your fight), brokers like KTrade/Finqalab/AKD (give research away free to acquire trading accounts — structurally, your product is a cost centre for them and a business for you). Nobody publicly grades broker calls — that's confirmed still true on your live leaderboard today and remains your clearest wedge.
- **Naming:** the chat argued for dropping "Trade Desk" (signals day-trading to a regulator and to beginners) in favour of something like Kasoti, Miqyas, Nisab, Bunyad, or Parakh — worth a separate decision, not a blocker for anything in this document, and not something I re-verified today.
- **Content/SEO strategy:** programmatic per-ticker pages, the leaderboard as a weekly shareable series, and email as the missing retention channel (organic search takes 6–9 months to compound; X gives spikes, not a base). Consistent with the Months 2–6 roadmap above.
- **New markets:** explicitly not recommended for at least a year — every new market doubles both the data-licence problem and the investment-advice-licensing problem. RDA/overseas Pakistanis are the one expansion that isn't really a new market (same data, same licence, higher willingness to pay in hard currency).

---

*This document is a research/planning aid, not legal advice. Every item in §2 and §8 needs sign-off from a Pakistan-licensed lawyer before you take a single subscription payment.*
