# Henneth — Product Roadmap

Status: PLANNING. Written 2026-07-14, rewritten 2026-07-30 to fold in the onboarding/lifecycle-email
rebuild and reconcile against current state (free early-access, 554-symbol universe, Publication
Restructure V2 in flight). Supersedes the 2026-07-14 draft below the fold where it conflicts.

**Current facts that gate everything here:**
- Pricing is OFF. Owner position (2026-07-20): the product is free, no plans, no trial timer. The
  priced ladder (Free/Investor/Pro/Broker, Rs 3,000/Rs 8,000) exists in code behind `site.earlyAccess`
  but is not charged. Traffic — not this roadmap — decides when that flips.
- Legal review of `state/legal.json` has not happened. Publication Restructure V2 (separate plan,
  in progress) is cutting per-security calls/verdicts/levels to stay inside the SECP 2(h) exemption.
  **Nothing below may reintroduce a named-security buy/sell/target/verdict into an email or onboarding
  flow** — same rule as the site.
- Resend is already connected (MCP) with domain **`send.henneth.app`** verified, sending enabled.
  This closes a gap flagged repeatedly in earlier planning (digest emails had no provider chosen).

---

## 1 — Onboarding rebuild: activation over instruction (headline item)

**The problem.** Current onboarding (built 2026-07-14, `dashboard/app.js`) is a three-screen wizard:
welcome → 4-question quiz (experience/goal/risk-temperament/sectors) → guided tour that drives the
user through the real app by hash route (`#/today → #/board → #/ticker/FFC → #/value → #/leaderboard`)
with coach cards, then flips `profiles.onboarded = true`. It's a **tell** flow — the product explains
itself before the user has done anything. HubSpot/Slack/Firecrawl/Apollo-style onboarding is a
**do** flow: get the user to one real action fast, then follow up by email based on what they did or
didn't do.

**Target shape — "send your first message," Henneth's version:**

1. **Zero-question signup.** Kill the quiz. Replace with one clear next-action prompt right after
   account creation: *"Pick a ticker to watch"* (search box, autofocus) — mirrors Slack's "send your
   first message" and Firecrawl/Apollo's "run your first job" pattern. No screens between signup and
   this.
2. **First action = activation event.** Adding a ticker to a watchlist (or running one Desk Room
   lookup, or using the position-size calculator once) fires an activation event. Track it
   server-side (Supabase row: `profiles.activated_at`, first activation type) — this is the metric
   that matters, not "wizard completed."
3. **In-product nudges replace the guided tour.** A single dismissible coaching card on `#/today`
   pointing at the watchlist add box ("Start here — add a ticker") instead of a forced multi-step
   tour. If the user ignores it, the tour doesn't chase them around the app; the email flow (below)
   does the follow-up instead.
4. **Progressive disclosure, not a tour.** Desk Room, leaderboard, macro — surfaced contextually
   (e.g. a "see the desk's read on FFC" link once they've watched FFC) rather than force-walked on
   day one.
5. **Replayability kept**, but reframed: "Show me around" becomes an opt-in help trigger from the
   account menu, not the default new-user path.

**Why this fits the desk specifically:** the product's real hook is explainability on a ticker the
user already cares about, not the desk's own feature list. Get them to name a ticker in the first 30
seconds; everything else follows from that signal.

### 1a — The email flow ("aware" = lifecycle emails, not just onboarding copy)

Resend free tier (verified via the connected MCP + Resend's published limits, 2026-07): **3,000
emails/month, 100/day, 1 verified sending domain, no credit card.** `send.henneth.app` is already
verified and enabled — this roadmap requires zero new infra to start sending, only templates and
trigger wiring. At current traffic (pre-paid-launch, small user base) 100/day is not a binding
constraint; revisit if/when a paid launch drives signups past that ceiling (Resend Pro is $20/mo for
50k/month if needed later).

**Flow (mirrors HubSpot/Slack/Apollo activation sequences, sized to Henneth's actual content):**

| # | Trigger | Email | Purpose |
|---|---|---|---|
| 1 | Signup complete | Welcome + "add your first ticker" CTA (same action as the in-product prompt) | Get them back if they didn't act in-session |
| 2 | 24h after signup, **no activation** | "Here's what the desk found on FFC today" (or a live example ticker) — show, don't ask | Re-hook with a concrete artifact, not a reminder |
| 3 | Activation event fires (ticker added) | "Here's the desk's read on {TICKER}" — links straight to that ticker's Explainability view | Confirms the action worked, delivers value immediately |
| 4 | 7 days post-signup, activated | First weekly digest ("what changed on your watchlist this week") | This is the SAME email infra the 2026-07-14 roadmap flagged as the retention engine — one build serves onboarding AND ongoing digests |
| 5 | 7 days post-signup, **still not activated** | Short "need a hand?" nudge, one CTA, no guilt-tripping copy | Last lifecycle touch before going quiet — no advice language, no urgency tricks |

Digest and re-engagement content must pull from `state/` only (Rule 2) and stay inside the same
no-named-call constraints as the site (Rule 5, Publication Restructure V2) — an email can point at a
ticker's explainability/debate page, never state a verdict or target in the email body itself.

**Branding:** one HTML email base template (`scripts/email_templates.py` — stdlib string templating,
no new deps), Henneth's color tokens/typography, square corners, footer with the platform-wide
"Research · not advice" disclaimer asserted pre-send on every email — not five one-off HTML blobs.
Copy lives separately in `scripts/email_copy.py` so wording edits never touch layout.

**Build status (2026-07-31): built, not yet live.** Superseding the original build-steps sketch
above (Resend `create-template`, a Postgres trigger, a Supabase edge function) — actual shape
turned out simpler and stays inside the existing desk cron instead of adding a new runtime:

1. **Done.** `docs/lifecycle_email.sql` — `profiles.activated_at`/`activation_type`/`signup_at`/
   `email_optout`/`unsub_token`, a write-once `mark_activated(p_type)` RPC (no Postgres trigger —
   the client calls the RPC at the four activation sites), `lifecycle_email_log` for idempotency,
   a service-role-only `lifecycle_queue` view. **Not yet applied** — owner runs it by hand in the
   Supabase SQL editor.
2. **Done.** `scripts/lifecycle_email.py` — plain Python in the existing desk cron, not a Supabase
   edge function (Resend Automations trigger off contact lists, not app state, so they can't decide
   "24h passed, still no ticker"). Modelled on `scripts/push_send.py`'s shape: dry-run default,
   `--send`/`--test`/`--only`/`--requeue-stale`, never crashes the cycle. Runbook: `docs/OPERATIONS.md` §10.
3. **Done.** Wizard deleted from `dashboard/app.js`, replaced by the ticker-search-first card +
   one dismissible coach strip; `markActivated()` wired at all four activation sites.
4. **Pending (owner, GitHub web UI):** three repo secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
   `RESEND_API_KEY`) + one workflow step in `.github/workflows/desk-data.yml` — cannot be pushed
   from this environment (no `workflow` OAuth scope, `docs/OPERATIONS.md` §5).
5. **Pending (owner):** manual test once live — fresh signup → welcome email arrives, add a ticker
   → activation email arrives and `activated_at` is set, force the 24h/7d paths by backdating
   `signup_at` in a test row, confirm the double-send guard (409 on `lifecycle_email_log`).

---

## 2 — Everything else already known to be pending (folded in from prior planning)

Grouped by what unblocks it, not by priority — traffic and the legal review are the actual gates on
several of these, not engineering effort.

### Ships independent of pricing/legal
- **Layer 5 i18n (agent prose → Urdu)** — plan drafted (`state-translator` agent, `_ur` sibling
  fields, per-surface insertion points across Daily Read/Macro/News/Sector Debates/Desk Room). Static
  chrome already fully Urdu (Layers 1-4). Not yet built.
- **Fundamentals-history scraper** (multi-year financial trend charts + company description) — the
  one real data gap blocking a stronger Explainability-first ticker view. Flagged repeatedly, not
  started.
- **Sector Debates + Marketplace** completion (partially built per `psx-plans-and-learner-desk`) —
  request-a-debate credits, marketplace backtest pipeline.
- **Broker fee comparison wizard.**
- **Public track-record hero page** — persona + broker leaderboards already produce the data; needs
  a marketing-facing presentation. Best asset once claims start resolving (currently 286 filed, 0
  resolved).

### Blocked on Publication Restructure V2 landing first
- Any Board/Desk Room display work should wait for that plan's cuts (no entry/stop/target tiles, no
  Chair verdict) to land — building on top of soon-removed surfaces is wasted work.

### Blocked on legal review / traffic (do not build ahead of demand — owner directive 2026-07-20)
- Billing switch-on (local PK payment gateway — no Stripe), `earlyAccess` flip, trial honouring
  (`trial_started_at`/`trial_ends_at` — not built, `profiles.plan` is DB-frozen against client writes
  so this needs a service-role path).
- Broker desk (Broker plan tier — not built).
- Portfolio Builder (parked, advice-shaped — needs lawyer read before any further design).
- Shariah filter (needs KMI-30 constituent data — not sourced yet).

### Needs a separate cost/runtime decision
- Personal AI Analyst chat — needs a runtime LLM + a budget decision (per-message cost model), not
  just an idea.

### Small/deferred polish
- Roman Urdu lesson-body translation (learner desk).
- Paper-portfolio public scorecard.

---

## Build order

1. **Onboarding + email flow (§1)** — ships now, no dependency on pricing or legal, and closes the
   long-flagged "no email provider" gap for digests too. Highest leverage per the owner's own framing
   ("aware" onboarding).
2. Fundamentals-history scraper + Explainability-first ticker view — the other half of "made easy."
3. i18n Layer 5 (agent prose) — separate active plan, continue independently.
4. Publication Restructure V2 — separate active plan, continue independently; blocks Desk Room/Board
   UI work until it lands.
5. Public track-record hero page — once claims start resolving in volume.
6. Everything gated on legal/traffic/pricing — do not start until the owner says demand or the lawyer
   review changes the gate.

---

## Compliance stance (must be everywhere — SECP-sensitive, unchanged from 2026-07-14)
- Describe the product **only** as a research & analytics tool, never an adviser.
- No per-user recommendations, no guaranteed returns, no performance promises. Losses shown, not
  hidden.
- Every email carries the same "Research · not advice" footer as the site. No named-security
  verdict/target ever appears in an email body — link to the page instead.
- Before charging anyone: Pakistani lawyer confirms the research-tool framing stays outside SECP
  investment-adviser licensing (separate from the Publication Restructure V2 SECP research-service
  question, which is about the *content*, not the *billing*).

---

## Appendix — 2026-07-14 original draft (multi-tenancy baseline, still the foundation)

*(Retained for history; items already shipped or superseded are noted inline.)*

**What's already the moat:** shared data + analysis engine (prices, quant, 52 backtested strategies,
4-method fair value, plain-English scorecards, risk/geo-risk/macro), the Explainability angle, the
Desk Room + accountability leaderboards, Rule-5 research-not-advice culture.

**What was missing for multi-user (status now):**
1. Multi-tenancy + auth — **shipped**: Supabase Postgres+Auth+RLS, per-user watchlists/portfolio/
   alert prefs, `profiles.plan`.
2. Delivery (email digests) — **this roadmap's §1 now closes this**: Resend connected and verified;
   prior plan said "Resend/Postmark free tier," Resend is the pick.
3. Explainability UI — partially shipped; fundamentals-trend charts still the open gap (see §2).
4. Public track-record page — not yet built; data exists (leaderboards).
5. Billing — Stripe was the original assumption; **superseded** — no Stripe (PK card processing
   unavailable), local gateway later, currently `BILLING_LIVE=false`, pricing off entirely per owner.

**Going private (the code) note** — resolved: hosting moved to Vercel, repo is private, site stays
public. No longer open.
