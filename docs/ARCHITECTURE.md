# Henneth — Architecture as it exists today

Written for a coding agent joining with zero previous context. Read this before adding a module. The most common failure in this repo is a second implementation of something that already works.

This describes the live product, not a target design. Operations live in [OPERATIONS.md](OPERATIONS.md). Governance lives in [CLAUDE.md](../CLAUDE.md). Sharp edges live in [GOTCHAS.md](GOTCHAS.md). Known debt lives in [TECH-DEBT.md](TECH-DEBT.md).

---

## 1. System overview

Henneth is a research publication and research terminal for the Pakistan Stock Exchange, with a thin global-markets layer for context. It never places orders. Execution is manual.

There are two public surfaces, one owner-only surface, three Vercel projects, and one private Git repo:

| Surface | URL | Source | Vercel project |
|---|---|---|---|
| Marketing site | https://henneth.app | `site/` (Astro, static) | `henneth-site`, root directory `site/` |
| Research terminal | https://desk.henneth.app | `dashboard/` + committed `state/` | `psx-trade-desk`, repo root |
| Company Intelligence | https://ci.henneth.app | `Henneth Desk 2.CI.0/` + generated private slice | separate CI project, root directory `Henneth Desk 2.CI.0/` |

The product is a hybrid of five parts:

1. Deterministic Python (`scripts/`) fetches, measures, scores, backtests, and writes JSON into `state/`. This runs in GitHub Actions even when the owner's computer is off. No LLM. No tokens.
2. Judgement agents (`.claude/agents/` + `prompts/`) run on the owner's machine. They write analysis back into `state/`. Visitors read the saved analysis 24/7; agents refresh it, they are not needed to serve it.
3. The terminal (`dashboard/`) is a static path-routed SPA. It reads `state/*.json` over HTTPS. It writes nothing to `state/`.
4. Supabase holds only auth and per-user rows. It never serves research.
5. Vercel serves static files. Edge middleware gates `/state/*` and CI `/data/*`. The CI project also exposes a separate owner-only `Henneth Desk 2.CI.0/api/ask.js`: it verifies the Supabase ES256 owner claim, loads only the requested company row, projects it through `api/ask_contract.js`, and builds the final answer/citations server-side around qualitative model output.

    PSX DPS / Yahoo / Firecrawl / TV
                    |
                    v
     scripts/  --writes-->  state/*.json  <--writes--  local agents
                    |
          +---------+------------------+
          |                            |
          v                            v
     gated copy on                allow-listed extract
     desk.henneth.app/state/*     site/src/data/public/*
     (account required)                    |
          |                                v
          +---- publish.py --> git push --> Vercel --> henneth.app

---

## 2. Major modules and who owns what

| Concern | Owner (change this, not a copy) | Consumers |
|---|---|---|
| Prices, calendars, dividends, history | `scripts/psx_data.py` + the fetchers | every later script, the terminal |
| Canonical PSX identity | `psx_data.canonical_symbol` / `split_board_state` — temporary XD/XB/XR board suffixes collapse to the ordinary ticker at universe intake | `update_universe.py`, `snapshot.py`, public extract |
| Universe + market mapping | `scripts/update_universe.py`, `config/markets.json`, `psx_data.yahoo_symbol` / `market_symbols` / `research_symbols` | every per-ticker script |
| Research vs signal eligibility | `scripts/liquidity.py` -> `state/liquidity.json`; `psx_data.research_symbols()` | backtest, fundamentals, predictability, fair value, signals |
| Indicators | `scripts/indicators.py` | `quant.py`, `strategy_engine.py`, backtests |
| Strategy rules | `strategies/*.json` + `strategies/library.json` | `strategy_engine.py`, `backtest.py`, `build_signals.py` |
| Position sizing (Rule 4) | `CLAUDE.md` is the rule. Computed in `scripts/build_signals.py`. Shown in `dashboard/app.js` `deskSize()` and `site/src/scripts/calculators.ts` `sizePosition()` | practice book, marketing calculators |
| Risk limits published to the client | `scripts/build_dashboard.py` writes `state/desk_rules.json` (allow-list of rule constants only) | `app.js` `loadDeskRules()` |
| Health gate (Rule 6) | `scripts/data_health.py` -> `state/health.json` | signal generation, terminal banners, watchdog |
| Publish gate | `scripts/preflight.py` | `publish.py`, `build_dashboard.py`, the cloud workflow |
| Live-site gate | `scripts/watchdog.py` | after every publish |
| Account gate (data) | `middleware.js` | every `/state/*` request on the terminal |
| Account gate (UI) | `dashboard/app.js` `OPEN_ROUTES` / `gateAllows()` | clean dashboard paths |
| Per-user data | Supabase `profiles` + RLS | `app.js`, the Chrome extension |
| Public marketing extract | `scripts/build_public_slice.py`, `scripts/build_astro_lite.py` | Astro pages under `site/` |
| Ask-the-desk | `api/ask.js` (Groq) | `/ask` and the context rail |
| Company profile source | `scripts/fetch_company_profiles.py` -> `state/company_profiles.json` | CI slice, Room dossiers, explainer, ticker overview |
| Official company documents | `scripts/fetch_company_documents.py` -> existing `state/research_index.json` + transient ignored PDF handoff | deterministic document extraction |
| Page evidence, facts and events | `scripts/document_intelligence.py` -> `state/company_documents.json`, `state/company_event_ledger.json` | CI slice, approval queue |
| Issuer source registry | `scripts/fetch_issuer_sources.py` -> `state/company_intel/source_registry.json` | CI Sources view |
| Company financial series | `scripts/build_financial_series.py` -> `state/company_financial_series.json` | CI Financials view, graph, synthesis handoff |
| Company source QA | `scripts/build_source_qa.py` -> `state/company_source_qa.json` | CI source-health badges and graph |
| Company knowledge graph | `scripts/build_company_graph.py` -> `state/company_intel/company_graph.json` | CI Graph view |
| Company change intelligence | `scripts/build_change_intelligence.py` -> `state/company_intel/change_intelligence.json` | CI Changes view and overview metrics |
| Judgment handoff | `scripts/document_queue.py` -> `state/document_synthesis_queue.json` | owner-approved local synthesis only |
| Synthesis training batch | `scripts/prepare_synthesis_batch.py` -> ignored `.cache/company_intel/training_batch.json` | local librarian/verifier agents |
| Approved CI briefs | `scripts/company_brief_review.py` -> `state/company_briefs.json`, `state/company_brief_receipts.json` | CI Brief view |
| Company Intelligence slice | `scripts/build_ci_slice.py` -> `Henneth Desk 2.CI.0/data/company_intelligence.json` | private CI app only |
| Operating events | `scripts/build_operating_events.py` -> `state/company_intel/operating_events.json` | evidence-backed Wave 1 index derived from canonical documents/events |
| Sector driver graphs | `scripts/build_driver_graphs.py` + `sector_driver_models.py` -> `state/company_intel/driver_graphs.json` | full 20-company pilot across BANKS/CEMENT/E&P/REFINERY/FERTILIZER/AUTO_ASSEMBLER/POWER/OMC/HOLDING_COMPANY; declarative routing only, no company values |
| Impact scenarios | `scripts/impact_engine.py` -> `state/company_intel/impact_scenarios.json` | graph-filtered event-to-driver Bear/Base/Bull scaffolding; numeric impacts remain null without sourced inputs |
| Historical event studies | `scripts/build_event_studies.py` -> `state/company_intel/event_studies.json` | one raw-price benchmark per canonical event; strict pre-event baselines and calendar horizons |
| Conditional historical benchmarks | `scripts/build_conditional_benchmarks.py` + `conditional_benchmarks.py` -> `state/company_intel/conditional_benchmarks.json` | exact event-type/subtype same-company and same-sector analogue resolver over existing event-study outcomes; statistics suppressed below three mature prior observations |
| Causal driver evidence map | `scripts/build_causal_foundations.py` -> `state/company_intel/causal_foundations.json` | one categorical evidence row per driver-graph edge, resolving only same-company official events and strict event studies; no causal estimate or numeric impact |
| Financial statement v2 facts | `scripts/financial_statement_facts.py` -> retained financial series/model inputs | conservative page/table facts; legacy rows remain audit-only |
| Financial model inputs | `scripts/build_financial_model_inputs.py` -> `state/company_intel/financial_model_inputs.json` | exact pilot, cement-only v1 model, null-safe derived history |
| Financial qualification coverage | `scripts/build_financial_coverage.py` -> `state/company_intel/financial_coverage.json` | metadata-only official PSX document map, evidenced annual slots, quarantined audit-only coverage and bounded-restage candidates; never infers values |
| Forecast/valuation readiness | `scripts/build_forecast_readiness.py` + `forecast_contract.py` -> `state/company_intel/forecast_readiness.json` | exact input-qualification contract over annual consolidated official facts; sector-driver registry coverage is tracked separately and never activates an unimplemented numeric model |
| Snapshot Scenario Lab | `scripts/build_company_scenario_lab.py` -> `state/company_intel/scenario_lab.json` | caller-supplied sensitivity, reverse-expectations and market-gap algebra over dated fundamentals/prices; generated state never selects a forecast or house case |
| Persistent Company Brain | `scripts/build_company_brains.py` -> `state/company_intel/company_brains.json` | compact 21-domain, five-type reference index over authoritative profiles, approved briefs, operating events and resolvable event studies |
| Thesis monitoring | `scripts/build_thesis_monitoring.py` + `thesis_monitoring.py` -> `state/company_intel/thesis_monitoring.json` | source-cluster-linked inference records with canonical Strengthening/Stable/Weakening/Broken states and explicit prove/kill/watch checks; no user thesis storage in v1 |
| Private user theses | Supabase `company_theses` + owner-only RLS | authenticated CI create/edit/archive/restore/delete; separate from deterministic thesis monitoring and inactive until the owner applies `docs/company_theses.sql` |
| Intelligence confidence | `scripts/build_intelligence_confidence.py` + `intelligence_confidence.py` -> `state/company_intel/intelligence_confidence.json` | transparent seven-component scores over retained signal clusters using source quality, independence, strict analogues, financial readiness, completeness and recency |
| Management delivery | `scripts/build_management_delivery.py` + `management_delivery.py` -> `state/company_intel/management_delivery.json` | categorical follow-through checks for active theses using only same-symbol, strictly later official events with exact assertion/conflict keys; broader guidance remains blocked without first-class guidance objects |
| Evidence watchlist | `scripts/build_evidence_watchlist.py` + `evidence_watchlist.py` -> `state/company_intel/evidence_watchlist.json` | exact-ID monitoring index over deterministic theses, delivery, confidence and financial readiness; exposes what would confirm or break a signal without forecasting or loose matching |
| Bounded document restage | `reprocess_company_documents.py` + metadata receipts under `state/company_intel/` | explicit first-batch IDs, scoped transient run directories, no shared queue mutation |
| Company Intelligence data gate | `Henneth Desk 2.CI.0/middleware.js` | `/data/*` on the CI Vercel project |
| Company Intelligence Ask UI | `Henneth Desk 2.CI.0/app.js` + `styles.css` | owner-only Ask tab; per-symbol request state and nine server-owned answer sections |
| Company Intelligence Ask UI gate | `scripts/check_ask_henneth_ui.mjs` via `scripts/preflight.py` | 20-row static UI/auth/citation/section/responsive verification |
| Brand / plan copy on the marketing site | `site/src/site.config.ts` | every Astro page |
| Desk Room scaffolding | `scripts/room_*.py` | Room agents; terminal Room surfaces |
| Astro pillar | `scripts/astro_*.py` | `/astro`, `/cast`, `/mychart`, `/financial-astrology` |

If you are about to add a helper, search this table first.

---

## 3. Frontend / backend relationship

There is no application server for the research product.

**Terminal (`dashboard/`)**

- `index.html` is the shell. It loads `auth-terminal.js`, `app.js`, `rail.js`, `topbar.js`, `board.js`, `shell.js`, `icons.js`, `i18n-ur.js`.
- Routing uses clean URL paths (`/today`, `/ticker/LUCK`). `route()` in `app.js` is the sole
  dispatcher; in-app navigation uses the History API and browser back/forward arrives through
  `popstate`. Supabase auth callbacks still arrive in the URL hash and are handled separately —
  those callback fragments are not dashboard routes.
- Data access is `j(filename)` in `app.js`. Locally it reads `../state/`; live it reads `state/` and attaches the Supabase bearer token. Middleware verifies that token. There is an XHR fallback because some browser extensions break `fetch`.
- `app.js` is about 7,300 lines and owns almost every page. Adjacent files own chrome, not product rules.
- `app.html` is a stale pre-gate shell. `scripts/vercel_build.sh` copies the whole `dashboard/` then deletes `app.html` so it is not served.

**Marketing site (`site/`)**

- Astro 5, static output, no server adapter.
- Hermetic on purpose: the marketing build must not import `../state/`. It reads only `site/src/data/public/*`, which Python writes.
- Waitlist / plan-interest posts from the browser to Supabase (`site.config.ts` points at table `waitlist`).
- Calculators are client-side TypeScript. The position-size tool is a deliberate second copy of Rule 4 — both copies name each other in comments.

**Chrome extension (`extension/`)**

- Read-only companion. Detects a ticker on TradingView or PSX DPS, reuses the desk session token, shows the same public-safe research. Not on the publish path.

---

## 4. Important data flows

### 4a. Cloud refresh (free, no agents)

`.github/workflows/desk-data.yml` runs `python scripts/run_cloud.py` then `python scripts/publish.py`.

`run_cloud.py` is the ordered list. Do not reorder casually. Two order invariants:

1. `liquidity.py` must run after both history fetches and before `fetch_fundamentals` / `predictability` / `backtest`. Out of order, `research_symbols()` falls back to core-only and backtests silently charge flat friction.
2. `build_astro_lite.py` must run after `astro_engine.py`. It writes into `site/`, never `state/`.

`build_public_slice.py` runs in `run_cloud.py` after the research it reads (and after `build_astro_lite.py`). It writes only the allow-listed extract into `site/src/data/public/`. `publish.py` commits that folder as generated data, same as `state/`. Adding a field to `state/` still does not publish it. If a pilot name is temporarily missing from the universe (for example an ex-dividend suffix like `FFCXD`), the extractor keeps the last published public row and marks it `stale` rather than deleting the marketing page.

### 4b. Local judgement cycle

`prompts/cycle-full.md` (pre-market / escalation) and `prompts/cycle-light.md` (intraday). Agents read `state/`, write `state/`, then the same `publish.py`. The cloud never holds an Anthropic key.

Deterministic `build_signals.py` already publishes candidate setups labelled `basis: "backtest-proven, unaudited"`. The Auditor can later upgrade a setup. Those are different objects. Do not collapse them.

### 4c. What a signed-in visitor sees

Browser loads `index.html` / `app.js` (public) -> `sb.auth.getSession()` -> `Authorization: Bearer ...` -> `middleware.js` -> CDN `state/*.json`.

A signed-out visitor can load the shell and a short open-route list (`cast`, `mychart`, `legal`, `plans`, `glossary`, `shipped`, `unsubscribe`). Almost every research file still returns 401. The UI gate and the data gate are independent; do not assume one covers the other.

### 4d. What a marketing-site visitor sees

Astro pages rendered from `site/src/data/public/tickers.json` (pilot names), `astro_lite.json`, `coverage.json`, `strategy_levels.json`, `context.json`. No fair-value method values, no verdicts, no backtest stats, no Desk Room, no predictability. That allow-list is the product boundary. Adding a field to `state/` does not publish it.

### 4e. What the private Company Intelligence app sees

`fetch_company_profiles.py` retains sourced DPS issuer profiles. `fetch_company_documents.py`
incrementally indexes official PSX/PUCARS announcements in the existing research index and makes a
bounded, ignored current-run PDF handoff. `document_intelligence.py` immediately extracts page-linked
evidence, conservative facts/events, append-only changes, a training-mode approval queue, and transient
full-page financial normalization; it makes no model call. `build_financial_series.py`,
`build_source_qa.py`, `build_company_graph.py`, and `build_change_intelligence.py` turn retained
evidence into period-aware financial rows, source-health flags, an evidence-linked graph, and a
deterministic "what changed" digest. `fetch_issuer_sources.py` weekly discovers same-domain issuer
pages and report links from the official DPS profile. `stage_issuer_documents.py` safely downloads a
bounded same-domain PDF set into the existing transient extraction handoff; the same document
intelligence and financial-series modules consume it immediately. Raw HTML/PDF bodies are not committed.

Model synthesis is training-mode only. `prepare_synthesis_batch.py` writes a compact ignored handoff for
the librarian/verifier agents. `company_brief_review.py` is the deterministic approval gate: it validates
document/page citations, blocks advice language, requires a clean verifier receipt, and writes durable
briefs only after explicit owner approval.

`build_ci_slice.py` joins the bounded private view into one generated file under
`Henneth Desk 2.CI.0/data/`. The app reads no other state file and never calls a market provider.
Its separate Vercel project uses `Henneth Desk 2.CI.0/` as the project root. The shell and sign-in form load publicly, but
middleware verifies the existing Supabase ES256 access token and serves `/data/*` only when the
signed `sub` equals `CI_OWNER_USER_ID`. No owner UUID, service-role key or signup path lives in the
repository. Private user theses use the separately reviewed `company_theses` RLS contract only
after the owner manually applies `docs/company_theses.sql`; the UI treats an absent table as an
explicit not-activated state.

Wave 1 Company Intelligence runs after the second `document_intelligence.py` /
`build_financial_series.py` pass. It derives operating events from the append-only event ledger
and retained evidence, builds only the three declared sector driver models, then emits scenarios
before the slice. The pilot boundary is exact equality with `company_profiles.pilot.symbols`.

---

## 5. Database ownership

Supabase project `qteoncckohuoatbjjykb`. Auth + per-user data only.

Live today, as described in [OPERATIONS.md](OPERATIONS.md) section 6 (there is no checked-in migration of the live schema):

- `auth.users` — Supabase Auth.
- `profiles` — one row per user, RLS owner-only. Client-writable fields include `watchlist`, `notes`, `portfolio`, `followed_brokers`, `digest_prefs`. `plan` is not client-writable (`freeze_plan` / `force_free_plan` triggers). Also holds onboarding / astro-board / strategy-board / language / theme.
- `waitlist` — marketing-site inserts.

Written, not applied (SQL lives in `docs/`, owner runs it by hand):

- `docs/company_theses.sql` — private per-user company theses for the exact 20-company CI pilot.
  It grants authenticated CRUD only behind four owner predicates, revokes public/anonymous access,
  bounds every input and labels any fair-value assumption as private user input. The CI app degrades
  to a visible not-activated state until this file is manually applied and live RLS checks pass.
- `docs/push_subscriptions.sql` — Web Push endpoints. Feature is inert until VAPID keys, this table, and a shipping change all exist.
- `docs/lifecycle_email.sql` — activation columns, `mark_activated` RPC, unsubscribe RPC, `lifecycle_email_log`, `lifecycle_queue` view. `scripts/lifecycle_email.py` exists; it cannot run until this is applied and Resend + service-role secrets exist.

Never assume a SQL file in `docs/` has been applied. Additive first. There is no migration runner.

---

## 6. Authentication flow

1. `dashboard/index.html` does a synchronous first-paint guess from `localStorage` key `sb-qteoncckohuoatbjjykb-auth-token` (must track the project ref). This only decides whether the chrome is collapsed.
2. `initAuth()` in `app.js` calls `sb.auth.getSession()`, loads `profiles`, migrates a guest birth chart, then `route()`.
3. Sign-in / sign-up UI is `dashboard/auth-terminal.js` (`window.HennethAuthTerminal`). Passwords never touch our code.
4. Cloudflare Turnstile is wired but off (`CAPTCHA_SITE_KEY = ""`). Do not enable one side without the other — see the comment above that constant.
5. Access tokens are ES256. `middleware.js` and `api/ask.js` each verify against the project's JWKS. Fail closed. If the project is switched back to HS256, every gated request 401s. That is the correct direction.
6. The publishable key in `app.js` / `site.config.ts` is safe to ship. The service role must never enter the client bundle, a state file, or a commit.

---

## 7. Authorization model

| Layer | What it protects | Bypassable from the client? |
|---|---|---|
| `middleware.js` | research files under `/state/` | no |
| `gateAllows()` / `OPEN_ROUTES` | which clean dashboard paths render | yes — it is UX |
| `hasFeature()` / `PLANS` / `BILLING_LIVE` | which screens are teaser-walled | yes, and while `BILLING_LIVE === false` every signed-in account is treated as Pro |
| Supabase RLS | a user's own `profiles` row | no, if RLS stays on |
| Supabase RLS | a user's own `company_theses` rows | no, after the unapplied schema is activated and its four owner policies are verified |
| `isOwner()` | plan-preview chrome | yes — it is an email string compare |

`plan` is frozen in the database against client writes. There is no payment gateway. Do not flip `BILLING_LIVE` or `site.earlyAccess` until a local gateway, reviewed legal pages, and a service-role trial path exist.

---

## 8. Important business rules and where they live

| Rule | Authoritative text | Enforced by |
|---|---|---|
| Long only, daily timeframe, no advice language | `CLAUDE.md` | agents, `api/ask.js` system prompt, copy review, `provenance_lint.py` |
| Numbers come from `state/`, else "unknown" | `CLAUDE.md` Rule 2 | agents; Ask-the-desk now relies on instruction-following around a pre-filtered slice, not templates |
| Position sizing | `CLAUDE.md` Rule 4 | `build_signals.py` (validity guard), `app.js` `deskSize()`, `calculators.ts` `sizePosition()` |
| Max 4 names, 20% exposure, one per sector | `CLAUDE.md` Rule 4 + `config/desk.json` `risk` | `build_signals.py`; practice checker in `app.js` |
| Health gates new signals | `CLAUDE.md` Rule 6 | `data_health.py`; consumers must honour `health.json` |
| Auditor veto | `CLAUDE.md` Rule 7 | `.claude/agents/auditor.md` on the local cycle |
| Strategy files immutable once live | `CLAUDE.md` Rule 8 | convention + Auditor; no file-system lock |
| No lookahead | `CLAUDE.md` Rule 9 | `backtest.py` / `strategy_engine.py` |
| News impact 4+ retriggers the full cycle | `CLAUDE.md` Rule 10 | news-sentinel + orchestrator prompt |
| Named-security levels are not published | `docs/PUBLICATION_RESTRUCTURE.md` + V2 | `build_signals.py` computes then discards entry/stop/target/shares; public tools take the reader's own numbers |
| `config/desk.json` is never served | `CLAUDE.md` | `vercel_build.sh` copies `dashboard/` + `state/` only; `desk_rules.json` is an allow-list export |

---

## 9. AI / LLM architecture

Three separate uses. Do not mix their jobs.

**Local desk agents** (Claude Code). Orchestrated by `prompts/cycle-full.md` and `cycle-light.md`. Each agent is a markdown file in `.claude/agents/`. They read compact dossiers (`state/dossiers.json`), never scrape. Output is JSON in `state/` (`rooms.json`, `daily_read.json`, `macro.json`, `claims.json`). Token cost stays on the owner. The cloud workflow has no API key on purpose.

**Ask-the-desk** (`api/ask.js`). Vercel Edge. Auth required. Fetches about 13 light state files with the caller's token, builds a symbol/sector-scoped slice, calls Groq (`llama-3.3-70b-versatile`). Rule 2 here is a system prompt, not an architecture guarantee. If `GROQ_API_KEY` is missing on the terminal Vercel project, the endpoint returns a configured error and the UI says chat is not configured. That is the current live state noted in `GOTCHAS.md`.

**State translator** (`state-translator` agent + `translate_extract.py` / `translate_merge.py`). Optional Urdu layer. Failure must leave English in place.

There is no in-product RAG store, no embeddings pipeline, and no per-visitor agent on the static host.

---

## 10. Integrations and external providers

| Provider | Used for | Isolated behind | Failure mode |
|---|---|---|---|
| PSX DPS | live watch, EOD, sectors, off-market CSV | `psx_data.py` | degrade, keep prior file, exit 0 |
| Yahoo Finance chart API | deep history, non-PSX names, some dividends | several fetchers; ticker via `psx_data.yahoo_symbol` | same |
| TradingView | EOD cross-check only, 15-min delayed | `tv_crosscheck.py` | advisory unless a genuine glitch; never compare TV live to DPS live |
| Firecrawl CLI | insider filings page | `fetch_insider_offmarket.py` | `stale: true`, keep prior |
| Supabase Auth + DB | accounts, profiles, private company theses, waitlist | client SDK/REST + RLS | signed-out or explicit feature-not-activated fallback |
| Groq | Ask-the-desk | `api/ask.js` | 502/429, no fabricated answer |
| Resend | lifecycle email | `lifecycle_email.py` | not live |
| PostHog + GA4 | analytics | `index.html` snippet; `site/src/components/posthog.astro` + `Base.astro` | silent if env missing |
| Vercel | hosting, edge middleware, one edge function | `vercel.json`, `middleware.js`, `api/ask.js` | last-good deploy stays if publish is blocked |
| Telegram | owner-only alerts | `config/desk.json` `alerts`, `scripts/alert.py` | empty token -> log only |
| Cloudflare Turnstile | signup bot protection | `app.js` `CAPTCHA_SITE_KEY` | currently disabled |

---

## 11. Storage

- Git is the research database. `state/` is committed, including `history/`, `history_deep/`, `intraday/`, so Vercel is self-contained.
- Writes go through `psx_data.save_json`: atomic temp replace, NaN/Inf scrubbed, UTF-8. Callers should not invent a second writer.
- `config/desk.json` is local/private. Never copy it into `public/` or `state/`.
- Root `/public/` is the terminal Vercel output directory and is gitignored. `site/public/` is the marketing site's static assets and is not gitignored — the root ignore rule is anchored on purpose.

---

## 12. Background processes

| Process | Where | What |
|---|---|---|
| `desk-data.yml` | GitHub Actions, weekdays 07/37 minutes past 03:00-11:00 UTC | `run_cloud.py` + `publish.py` + `watchdog.py` |
| App scheduled tasks | owner's Claude app (OPERATIONS.md section 4, SYSTEM-REGISTRY.md) | news, monitor, macro, daily read, Desk Room debates, weekly harvest, weekly code review |
| `lifecycle_email.py` | not scheduled live | welcome / nudge / digest |
| `push_send.py` | runnable, inert without VAPID | web push |
| Content tweet tasks | separate content system | not the desk |

`SYSTEM-REGISTRY.md` is a cheap index and was last dated 2026-07-14. Prefer `run_cloud.py` and `OPERATIONS.md` when the registry disagrees.

The cloud workflow installs Python 3.12 (`.github/workflows/desk-data.yml`). That is the canonical runtime for published numbers. The owner's machine may be 3.14. `requirements.txt` is the only dependency list.

---

## 13. Deployment architecture

One repo, two Vercel projects, one publish choke point.

**Terminal**

- Root `vercel.json`: `installCommand` is a no-op, `buildCommand` is `sh scripts/vercel_build.sh`, `outputDirectory` is `public`.
- `vercel_build.sh` copies all of `dashboard/` into `public/`, deletes `app.html`, copies `state/` to `public/state/`. Deny-list, not allow-list — an allow-list already 404'd `auth-terminal.js` in production.
- The terminal's Vercel configuration falls back only clean dashboard paths to the SPA shell, so a
  refresh or shared link such as `/today`, `/ticker/LUCK`, or `/legal/privacy/` reaches the same
  dispatcher. Static assets, `/state/*`, and `/api/*` retain their normal handling and are not
  swallowed by the SPA fallback.
- `ignoreCommand` skips a deploy when the commit did not touch `dashboard/`, `state/`, `api/`, `middleware.js`, the build script, or `vercel.json`.
- Cache: HTML/JS `must-revalidate`; `state/*.json` 60s + SWR 900s. A caching service worker would violate the freshness guarantee; `dashboard/sw.js` has no fetch handler and is not shipped until push is activated.

**Marketing**

- `site/vercel.json` pins Astro. Do not let Vercel import the root `vercel.json` into this project — that is the terminal build and it breaks the site.
- Ignored-build-step gotcha for merge commits is documented in `site/README.md`.

**Publish**

- Always `python scripts/publish.py "message"`. Never hand-push `state/`.
- Default: stage `state/` + generated marketing extracts only.
- `--code`: ships only files already staged by you. It never runs `git add -A`.
- Rebase auto-resolve is allowed only for regenerable data. A conflict on a hand-authored file aborts.

---

## 14. Invariants

1. Producers write `state/` (or the public extract). Renderers do not fetch upstream vendors.
2. Consumers do not reach around `state/` into `config/`, Yahoo, or DPS.
3. A structurally broken cycle must not publish. `preflight.py` fail -> last-good site stays.
4. A vendor failure must not crash the cycle and must not invent a number.
5. `config/desk.json` and `.env` never enter a served directory.
6. Named-security entry/stop/target/share-count against the desk's capital do not appear on subscriber surfaces.
7. Strategy JSON that has produced a published backtest is frozen. New version = new file.
8. SQL in `docs/` is not live until the owner applies it.
9. `BILLING_LIVE` false means do not take money and do not lock members out.
10. The two Vercel projects stay separate. The marketing build stays hermetic.

---

## 15. Behaviour that must stay synchronized

| If you change... | also change... |
|---|---|
| Rule 4 | `CLAUDE.md`, `build_signals.py`, `app.js` `deskSize()`, `site/src/scripts/calculators.ts` `sizePosition()`, and the comments that name the siblings |
| Risk constants in `config/desk.json` | they flow through `desk_rules.json` automatically; do not hardcode a second set in `app.js` except as the documented fallback |
| Supabase project ref | `SB_URL` / `SB_STORAGE_KEY` in `app.js`, the first-paint script in `index.html`, `middleware.js` / `api/ask.js` JWKS URL, `site.config.ts` |
| `PUBLIC_FILES` in middleware | `watchdog.py` (it uses `public_probe.json` as the unauthenticated content check) |
| Plan ladder / feature names | `PLANS` in `app.js` and `site.plans` in `site.config.ts`. `app.js` wins for entitlement |
| `earlyAccess` / `BILLING_LIVE` | both, plus legal review and a trial grant path |
| Universe / liquidity gates | `psx_data.research_symbols()` only — do not add a local `tier == "core"` filter |
| Indicator math | `scripts/indicators.py` only; delete any local shadow in the same commit |
| JWT verify logic | `middleware.js` and `api/ask.js` (deliberate duplicate; keep them equivalent in behaviour) |
| Dashboard filename added | nothing — `vercel_build.sh` copies the folder. Do not revive an allow-list |
| Public page data | `build_public_slice.py` allow-list. Never read `state/` from Astro |

---

## 16. Unusual technical decisions

Leave these alone unless the reason died.

- JSON files in git instead of a research database. Lets a static host serve the product and lets `publish.py` be the only write path.
- Two gates, UI and data. The sign-in screen was never enough; `/state/` used to be wget-able.
- JWKS on the edge, no shared secret. Verification is Web Crypto against a public key.
- Ask-the-desk duplicates `verify()` rather than importing middleware. A chat change must not regress the file gate.
- Public extract is an allow-list. New `state/` fields stay private by default.
- Disagreement shape, not verdict, on public ticker pages. Legal + Rule 5.
- Signals compute size and levels, then throw them away. Validity still needs the maths; publication must not look like advice.
- Deny-list dashboard copy. An allow-list already caused a live blank sign-in page.
- `research_symbols()` fails closed to core. A missing liquidity file must not fan the expensive pipeline out across the whole market.
- Health ignores foreign-symbol freshness. A Yahoo miss on XLE must not halt PSX signals.
- No test framework. The real gates are `preflight.py`, `provenance_lint.py`, `watchdog.py`, and a production publish. Do not drop in Jest/pytest as part of an unrelated change.

---

## 17. Important seams

| Seam | Why it is a seam | Do not |
|---|---|---|
| `state/*.json` | Python writes, JS/agents/extension read | let the dashboard call Yahoo; let a fetcher render HTML |
| `state/desk_rules.json` | exports rule constants without exporting secrets | serve `config/desk.json` |
| `site/src/data/public/` | only desk data the marketing site may see | import `../../state` from Astro |
| `psx_data.save_json` / `load_json` | atomic UTF-8 NaN-safe I/O | add a third JSON helper |
| `psx_data.research_symbols()` | one definition of who gets the expensive pipeline | copy a `tier == "core"` filter |
| `psx_data.yahoo_symbol()` | one place that knows `.KA` vs a US ticker vs `US500` -> `^GSPC` | concatenate `.KA` at a call site |
| `middleware.js` | data gate | move research serving through a serverless proxy (`state/` is about 92MB) |
| `publish.py` | the only push path | `git add -A` or a raw `git push` of state |
| `hasFeature()` / `BILLING_LIVE` | future entitlement | scatter `if (plan === "pro")` through pages |
| `strategies/library.json` | live rule templates | edit a live strategy in place |

---

## 18. Where to make a change

| You want to... | Start here, not somewhere else |
|---|---|
| Add a ticker field the UI needs | write it in the Python producer, assert it in `preflight.py`, then read it in `app.js` |
| Add a public marketing fact | add it to the allow-list in `build_public_slice.py`, then the Astro page |
| Change risk limits | `config/desk.json` + `CLAUDE.md` if the rule text changes |
| Change how Yahoo is called | put retry/error handling in one helper and migrate fetchers to it (see TECH-DEBT) |
| Add a dashboard page | `PAGES` + a `pageX()` in `app.js`, nav in `index.html`. Do not start a second router |
| Add a marketing page | `site/src/pages/...` + `site.config.ts` if it is brand-shaped |
| Add an agent | `.claude/agents/`, one line in `SYSTEM-REGISTRY.md`, persist into `state/` |
| Add a cron step | `run_cloud.py` if it is free/deterministic; owner's scheduled tasks if it needs Claude |
| Touch auth or `/state/` | stop and read `middleware.js`, `GOTCHAS.md`, OPERATIONS.md section 9b |
| Activate push or email | owner applies SQL + secrets; do not turn it on from code alone |

If this file does not name the place, search `graft/` or run `graft ask` before writing a new module.
