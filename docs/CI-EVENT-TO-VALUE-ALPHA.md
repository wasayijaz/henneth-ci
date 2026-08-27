# Henneth Company Intelligence — Event-to-Value Alpha

## Mission and scope

Event-to-Value Alpha is the active delivery milestone for `ci.henneth.app`.
The broader 68-section Company Intelligence specification remains the long-term
roadmap. This milestone proves the complete, source-grounded investor workflow
for three companies before expanding the universe, generic interface breadth,
or monitoring volume.

Each completed Intelligence Case must establish a traceable path:

`observed evidence -> operating event -> competing hypotheses -> drivers -> analogues -> quarterly financial impact -> scenarios -> valuation -> price-implied expectations -> investor conclusion -> monitoring`.

No case is marked product-complete until it is `Published` and has usable,
source-qualified financial, valuation, and current-price-expectations outputs.

## Execution rules

- The golden scope is exactly three companies: one E&P exploration case, one
  industrial/cement expansion case, and one sales-led expansion case.
- Existing 20-company CI products remain searchable but do not receive new
  formal Event-to-Value work unless they are a selected golden company.
- A source fact, derived fact, inference, analyst assumption, scenario output,
  forecast, and market-implied value remain visibly distinct.
- Numerical accounting, quarterly models, EPS, cash flow, debt, valuation,
  probability, and reverse-expectations calculations are deterministic.
- Historical outcomes are labels, never inputs available before their historical
  cutoff. Small samples remain visible but do not produce misleading averages.
- Every part is committed separately only after its relevant checks are green.
  The execution log below records the investor behaviour, data coverage, and
  unresolved blocker before the next part begins.

## Current baseline — 2026-08-27

| Area | Retained evidence | Status | Implication for Alpha |
|---|---|---|---|
| Architecture coverage | `state/company_intel/completion_matrix.json` | 61 complete, 4 partial, 4 blocked of 69 | Useful foundations exist; this is not proof of investor-ready cases. |
| Financial model readiness | `state/company_intel/forecast_readiness.json` | MLCF and DGKC input-ready; all formal outputs non-computed | No company currently clears Alpha’s financial-output gate. |
| Formal engines | `financial_forecasts.json`, `formal_valuations.json`, `market_expectations.json` | Deterministic code exists; 0 computed / 20 | Alpha must prove live outputs for three cases, not merely engine code. |
| Historical analogue state | `state/company_intel/conditional_benchmarks.json` | 21 dated benchmarks; thin samples remain suppressed | Golden cases need case-specific, cutoff-safe analogue evidence. |
| Private thesis storage | `private_thesis_storage_receipt.json` | Schema configured; live CRUD/cross-user RLS proof absent | Persisted owner scenarios/theses stay disabled until verified. |
| CI release integrity | Generated CI state now carries a reproducible build envelope, but checked-in artifacts cannot contain the hash of the commit that contains them | In progress | Part 0 remains gated on exact release-time restamping plus live deployment/auth proof. |
| Deployment gate | `docs/OPERATIONS.md` describes main-branch publishing; preview-to-production parity is not yet proven | Open | Part 0 must prevent a failing commit reaching production. |

## Golden-company selection register

Selection is evidence-led, not based on a preferred ticker. A company is chosen
only once its retained official source coverage can support five fiscal years,
eight reported quarters, load-bearing share-count data, and a real dated event.

| Case | Required event family | Current shortlist | Selection status | Reason / next evidence |
|---|---|---|---|---|
| A — E&P | exploration, appraisal, development, or production | OGDC, PPL | Unselected | OGDC has a dated official gas-discovery observation (`company_event_ledger.json`, `evt_2564e46943e475e1c5dd`, PSX 268175, 2026-01-02) but no canonical event, E&P model adapter, or qualified financial history; PPL has no qualifying E&P event. |
| B — industrial/cement | expansion, hiring, procurement, maintenance, commissioning, or capacity | MLCF, LUCK, DGKC | Unselected | DGKC is the conditional backfill front-runner: a PP-bag-plant commissioning reference exists (`evt_c66c444c35780cf5951e`, issuer `c7230a44854c74a77777465a`, FY25 Q3), with four annual years; its event date is not normalized, quarterly history is 0/8, bridges are blocked, and share-count assumptions are absent. MLCF/ LUCK do not clear the strict gate. |
| C — sales-led | sales hiring, geography, branch/channel, product-sales infrastructure | PSO, GAL reviewed | Unselected | No retained dated, canonical sales-led event with model-ready history. PSO corporate-card/network clues have null event dates and 0 qualified periods; GAL has no event and 0 qualified periods. PSO is the best source-backfill lead, not a selected case. |

## Ordered execution log

| Part | Gate | Status | Visible investor behaviour delivered | Data coverage / unresolved blocker |
|---|---|---|---|---|
| 0 | Release integrity | In progress | Every generated private CI artifact is now sealed with a common UTC cutoff, source commit, generator version, and hash manifest; stale or mismatched envelopes fail closed. | Local structural, no-lookahead, artifact-integrity, and focused product checks are green after finalization. A live preview/prod same-commit receipt and owner-auth/runtime smoke evidence still block the gate. |
| 1 | Model-ready financial truth | Not started | None | Three companies unselected; 5-year/8-quarter, tie-out, cash-flow, and share-count coverage unproven. |
| 2 | Three real operating events | Not started | None | Requires one dated, source-backed event and competing explanations per selected company. |
| 3 | Sector event models | Not started | None | Requires one deterministic E&P, capacity/hiring, and sales-ramp model contract. |
| 4 | Eight-quarter event-to-financial models | Not started | None | Requires complete actuals and source-labelled analyst assumptions. |
| 5 | Historical analogues | Not started | None | Requires case-specific domestic/peer search with historical cutoffs. |
| 6 | Valuation and expectations | Not started | None | Requires computed model outputs and appropriate valuation schedules. |
| 7 | Intelligence Case interface | Not started | None | Requires published case objects and a deterministic rendering contract. |
| 8 | Private thesis monitoring | Not started | None | Requires owner-session CRUD and cross-user RLS verification before writes are enabled. |
| 9 | Golden fixtures and release | Not started | None | Requires all case, product, runtime, and deployment gates green. |

## Part 0 acceptance record

Part 0 is complete only when all of the following are evidenced against the
same commit:

- every generated CI artifact has UTC `build_cutoff_at`, `generated_at`,
  generator version, and source commit metadata;
- no-lookahead distinguishes source-effective/published/observed timestamps
  from generated metadata;
- the aggregate CI contract, artifact-integrity, and authentication smoke tests
  pass;
- a preview deployment and production deployment identify the same green
  commit; and
- the CI private JSON endpoint remains owner-gated while the public login
  surface remains functional.

### Part 0 implementation evidence — 2026-08-28

- `scripts/build_ci_artifact_integrity.py` stamps all generated CI state and
  the private app slice with `source_commit_sha`, `generator_version`,
  `build_cutoff_at`, and `generated_at`, then writes a hash-backed manifest.
  Invalid or unknown commit identities fail closed.
- `scripts/check_ci_artifact_integrity.py` verifies every artifact hash and
  validates the stored source commit. Static checkout checks accept an older
  generated run because a committed file cannot name its own containing commit;
  CI and release jobs fail closed by supplying `GITHUB_SHA` /
  `HENNETH_CI_SOURCE_COMMIT_SHA` immediately after finalization.
- `scripts/check_ci_global_no_lookahead.py` treats the generated envelope as
  metadata rather than economic timing, while continuing to check source and
  provenance dates. It passed locally over 43 artifacts / 16,368 date
  comparisons.
- The aggregate and preflight gates finalize the artifact set only after
  ordinary rebuild checks, so metadata is not mistaken for a business-output
  difference and cannot be erased before validation. The focused artefact
  checker passed over 37 sealed artifacts after a stable finalizer run.
- `scripts/check_ci_release_integrity_receipt.py` now fails closed unless one
  secret-free receipt ties the GitHub contract, preview, production, public
  login, owner `200`, and non-owner `403` checks to the same full commit SHA.
  Its current receipt is deliberately `not_verified`; it is release evidence,
  not an investor-facing generated artifact.
- `.github/workflows/ci-production-release.yml` supplies the controlled
  preview-to-promotion route, guarded by the `ci-production` environment. The
  preview job restamps the private CI slice to the release `github.sha` before
  Vercel builds it, stamps the Vercel preview with `githubCommitSha`, verifies
  that metadata through the Vercel deployment API, and after promotion verifies
  the production domain resolves to that same deployment id and commit without
  a rebuild. The workflow is code-complete but its Vercel Git-deploy setting,
  protected environment secrets, and first live receipt remain external
  evidence.
- **Not evidenced yet:** a GitHub Actions green run, a preview deployment and
  production deployment of that exact commit, a public-login runtime smoke,
  and live owner/non-owner access checks against `ci.henneth.app`. These need
  deployed credentials and cannot be substituted with an offline contract.

## Change log

| Date | Change | Evidence |
|---|---|---|
| 2026-08-27 | Alpha execution record created; no case selected or promoted. | This document and the retained baseline files named above. |
| 2026-08-27 | Completed retained-state candidate audit without promoting weak evidence. | E&P: `company_event_ledger.json` OGDC `evt_2564e46943e475e1c5dd`; industrial: DGKC `evt_c66c444c35780cf5951e`; sales-led: PSO `evt_2f3bfdf4a586999e66b6` / `evt_30027cd832df431a70a9`. All three case slots remain unselected until the strict financial/event gates are met. |
| 2026-08-28 | Implemented and locally verified the Part 0 integrity envelope and finalizer ordering. | 37 sealed artifacts; source-commit binding; workflow structural check; 43-artifact no-lookahead scan; focused metadata-safe deterministic checks. Live deployment/auth evidence remains open. |
| 2026-08-28 | Repaired the artifact source-commit model so static checked-in JSON does not falsely fail after commit, while CI and release jobs restamp and verify against the exact `GITHUB_SHA`. | `check_ci_artifact_integrity.py --self-test`; CI contract exact-commit verification step; release preview restamp before Vercel build. |
