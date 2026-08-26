# Henneth Company Intelligence checkpoint — 2026-08-23

Status: paused by owner before laptop shutdown. The persistent goal remains the complete 68-section
Company Intelligence product; it is not complete and must not be narrowed to the finished waves.

## Completed and verified

- Operating events, three-sector driver graphs and null-safe Bear/Base/Bull scenario shells.
- Strict no-lookahead historical event studies.
- Financial truth/readiness gate with honest partial/unsupported states; the repeated PDF parser
  route is frozen and should not be reopened without a materially different bounded approach.
- Closed-registry signal clusters with no fabricated convergence.
- Flagship Intelligence UI.
- Ask Henneth pure grounding contract, owner-authenticated endpoint and nine-section UI.
- Snapshot Scenario & Reverse Expectations v1 for the exact 20-company pilot:
  - canonical formulas: `scripts/company_scenario_lab.py`
  - builder/state: `scripts/build_company_scenario_lab.py` ->
    `state/company_intel/scenario_lab.json`
  - pipeline and CI slice integration
  - functional Scenarios tab with blank caller-supplied revenue-growth, net-margin and P/E inputs
  - no selected house case, probability, forecast, fair-value verdict or advice
  - EBITDA, FCF, DCF and formal forecast remain explicitly blocked

Latest verification before pause:

- `company scenario lab: PASS (20 rows, formulas, reverse, bounds, provenance, deterministic)`
- `company_scenario_lab_ui: PASS (96 assertions, 20 company rows)`
- Python compileall: PASS
- CI app JavaScript syntax: PASS
- Full preflight: OK
- Existing non-gating warning only: 98 newly-added universe tickers still backfilling history
- `git diff --check`: PASS

No files were staged, committed, deployed or published.

## Exact restart point

Next wave: build the compact canonical Company Brain and uniform intelligence typing.

1. Create a reference-only `state/company_intel/company_brains.json` for the exact 20-company pilot.
   Existing producer state remains authoritative; do not copy full fact payloads or build a second
   event/financial implementation.
2. Every company must expose explicit domain coverage for segments, products, facilities, capacity,
   customers, suppliers, employees, management, geography, subsidiaries, competitors, financial
   statements, operating KPIs, capital allocation, projects, guidance, risks, catalysts, historical
   events, forecasts and valuation. Missing knowledge stays `unknown`/`blocked`.
3. Normalize references to exactly one epistemic type: `reported_fact`, `derived_fact`, `inference`,
   `scenario`, or `forecast`, with source product/ID, evidence refs, confidence and availability date.
4. Integrate the Brain through `build_ci_slice.py`, then add Investor Snapshot and unified Timeline
   surfaces. Extend Ask Henneth only through a deliberate bounded contract change.
5. Add exact-pilot, reference-resolution, no-lookahead, deterministic and 20-company UI gates to
   preflight before accepting the wave.

After Company Brain, the major remaining dependencies are qualified multi-period financial history,
event-linked earnings bridges and forecasts, broader sector driver models, valuation and market-
expectations engines beyond snapshot sensitivity, thesis storage/monitoring, confidence calibration,
alternative-data pipelines, conditional analogue/causal research and advanced quant factors.

Workflow on resume: Sol/root orchestrates; Luna-high thinks/reviews hard logic; GPT-5.5 executes;
timebox each bounded wave and move on rather than looping on one parser or foundation.

## Resume update — Company Brain wave completed

Work resumed after this checkpoint. Company Brain v1 is now generated, pipeline-integrated and
visible through Investor Snapshot and the typed Company Timeline. It covers the exact 20-company
pilot with 21 explicit domains and 48 compact source-resolvable objects. Forecast and formal
valuation remain blocked. Ask Henneth now receives only a capped Brain coverage/timeline summary and
the deterministic snapshot-readiness states; its adversarial contract gate increased to 5,960
assertions across all 20 companies. Full preflight returned OK after the integration.

## Pause update — sector-driver expansion queued, not implemented

Owner paused work to restart Codex. The sector-driver expansion was planned and independently
reviewed, but implementation was deliberately stopped before any model files changed. The temporary
checker edit made during planning was removed. `sector_driver_models.py`, `build_driver_graphs.py`
and generated driver state remain at the last verified three-sector implementation.

The last complete verification before this pause was green:

- Python compile and all Company Scenario/Brain builders and checkers: PASS.
- Scenario UI: 96 assertions; Brain UI: 86 assertions.
- Ask contract: 5,960 assertions; endpoint: 30; UI: 39.
- Full `scripts/preflight.py`: OK, with only the existing non-gating 98-ticker history-backfill warning.
- `git diff --check`: PASS apart from line-ending notices.
- No files were staged, committed, deployed or published.

### What is complete

1. Foundation ingestion/provenance, company profiles, official documents, source QA, graph and
   change intelligence for the exact 20-company pilot.
2. Evidence-gated Operating Events and strict no-lookahead Event Studies.
3. Declarative driver graphs for Banks, Cement and E&P.
4. Null-safe Bear/Base/Bull Impact Scenario scaffolding with no unsupported numeric impacts.
5. Financial truth/readiness gate and conservative retained financial observations. Forecasting
   remains blocked where qualified multi-period history is absent; do not reopen the failed broad
   PDF-parser loop without a materially different bounded approach.
6. Signal clusters with closed-registry convergence and no fabricated corroboration.
7. Snapshot Scenario Lab and Reverse Expectations arithmetic for all 20 companies, with user-only
   inputs and no house case.
8. Compact persistent Company Brain: 20 companies, 21 explicit domains, five intelligence types,
   and 48 source-resolvable reference objects.
9. Investor Snapshot, typed Company Timeline, flagship Intelligence UI and bounded Ask Henneth
   nine-section answers.
10. Pipeline/preflight integration and documentation for the completed waves.

### What remains for the full 68-section goal

1. Expand sector driver graphs from 10/20 modeled companies to all 20.
2. Expand event-to-driver routing and the Impact Engine beyond null-safe shells.
3. Acquire/qualify multi-period consolidated financial history, then build earnings bridges and
   genuinely sourced forecasts.
4. Add full sector-specific financial models and valuation methods beyond snapshot P/E sensitivity.
5. Build historical same-company/peer/sector analogue matching and conditional benchmarks.
6. Add Market Expectations and Expectations Gap engines beyond the current reverse algebra.
7. Add private Investment Thesis storage, kill conditions and evidence-driven thesis monitoring.
8. Add source-quality-aware confidence calibration and contradiction/management-delivery scoring.
9. Add bounded alternative-data pipelines such as hiring, permits, tenders and operational activity.
10. Add causal research, backtested proprietary factors and advanced quantitative experimentation
    only after sufficient point-in-time history exists.
11. Complete the broader company navigation, continuous-monitoring flows, end-to-end product audit,
    deployment readiness and owner-approved publish/deploy.

### Exact next wave after restart

Expand declarative driver coverage for the exact pilot. Add models for `REFINERY`, `FERTILIZER`,
`AUTO_ASSEMBLER`, `POWER`, `OMC` and `HOLDING_COMPANY`; keep existing `BANKS`, `CEMENT` and `E&P`.
ENGROH must use an explicit company override to `HOLDING_COMPANY` rather than its unsuitable exchange
sector label. No company values or forecasts belong in these graphs.

Implementation order:

1. Change `scripts/sector_driver_models.py` and `scripts/build_driver_graphs.py`.
2. Strengthen `scripts/check_operating_intelligence.py` for exact 20/20 non-empty coverage, exact
   sector registry, valid statement-line routing, used drivers, empty quality flags and the ENGROH
   override.
3. Extend `scripts/impact_engine.py` event-driver candidates only where the new graph contains the
   named driver; numeric impacts remain null until sourced inputs exist.
4. Rebuild driver graphs, impact scenarios and the CI slice.
5. Update `docs/ARCHITECTURE.md` and `docs/OPERATIONS.md`.
6. Run compile, builder, operating-intelligence checker, UI/Ask checks, full preflight and
   `git diff --check` in small batches.

Workflow after restart: root orchestrates, Luna-high executes code, GPT-5.5 performs quick planning
and independent review. Timebox every step and move on as soon as its acceptance gate passes.

## Resume update — causal driver evidence map completed

Causal Driver Evidence Map v1 now covers all 20 pilot companies and all 160 unique driver-graph
edges. It accepts only retained same-company official events directly tagged to a driver and strict
baseline-before-event study records; current retained events have no direct driver tags, so all
event/study links honestly remain empty. It preserves the canonical pilot order and exposes an explicit next-data requirement per edge,
and blocks causal estimates, numeric impact, forecasts and valuation. Macro evidence is explicitly
excluded until stable per-test source identifiers exist. The state builder, CI slice, cloud pipeline,
preflight contract and read-only CI surface are integrated; focused and full verification results are
recorded in the delivery handoff for this wave.

## Resume update — Evidence Watchlist v1 completed

The exact 20-company pilot now has a deterministic Evidence Watchlist. Six active monitoring items
across five companies connect active deterministic theses to exact management-delivery, confidence,
financial-readiness and official-source evidence records. The CI Watchlist tab shows what would
confirm or break each monitored assertion and honest empty states for the other 15 companies. No
private user thesis, loose matching, forecast, probability, numeric impact, valuation, price claim or
advice enters this state. Backend, slice, UI and preflight contracts are integrated.

## Resume update — Forecast/Valuation Readiness Contract v1 completed

The exact 20-company pilot now has an explicit readiness contract for future numerical models. All
nine existing sector-driver registries map across the pilot, including the ENGROH holding-company
override, but remain explicitly qualitative. Real input readiness is 0/20 because no retained facts
meet the three-period annual consolidated current-parser gate. The contract requires strict
post-period availability, aligned PKR scale, exact official provenance and no conflicts or quality
flags. Synthetic checks prove the future input-ready seam while numeric forecast, valuation, market
expectations and impact activation remain blocked until a separate implemented model exists.

## Resume update — Conditional Historical Benchmarks v1 completed

All 16 retained operating events now have a conditional benchmark record. Matching is exact on event
type and subtype, candidates must strictly predate the target, and same-company history remains
separate from same-current-sector history. Outcomes are referenced from the target event study rather
than recomputed. The current database yields three prior exact candidates across the 16 targets, but
all 64 horizon aggregates remain suppressed because no horizon reaches the minimum sample of three.
Three undated target events are explicitly blocked rather than assigned an inferred date. Peer,
international, period-aligned financial and causal interpretation remain unavailable.

## Resume update — full-pilot driver graphs completed

The queued sector-driver wave is now implemented. All exact 20 pilot companies have non-empty,
declarative graphs across nine canonical models: BANKS, CEMENT, E&P, REFINERY, FERTILIZER,
AUTO_ASSEMBLER, POWER, OMC and HOLDING_COMPANY. ENGROH uses the explicit holding-company override.
The contract verifies the exact registry, graph coverage, edge vocabulary, used drivers and empty
quality flags. Event-to-driver candidates are filtered through each company's actual graph; all
financial and valuation impact fields remain null until sourced inputs qualify.

## Resume update — Thesis Monitoring v1 completed

The deterministic pipeline now turns the six retained source-qualified signal clusters into six
read-only thesis-monitoring records across the exact 20-company pilot. Every thesis is typed as an
inference, retains its source-cluster/evidence links, and defines explicit prove, kill and watch
checks. Public status uses Strengthening/Stable/Weakening/Broken; all current single-source records
are conservatively Stable. The CI app has a Thesis Monitor view, while Ask receives only a capped
four-thesis summary without raw evidence or URLs. User-authored thesis storage remains a later
private-data wave.

## Resume update — Intelligence Confidence v1 completed

The six retained signal-cluster inferences now have transparent confidence scores built from seven
fixed components: source reliability, signal independence, historical precedent, financial-model
quality, peer evidence, data completeness and recency. Weights sum to 100 and every component keeps
its raw facts, normalized score, weighted points and rationale. Single-source disclosures receive no
false independence credit, and analogue inputs remain strict no-lookahead. The Intelligence view
shows the breakdown; Ask receives only a capped score/component projection.

## Resume update — private company thesis storage code-ready

The CI Thesis Monitor now has a separate private user notebook for the exact 20-company pilot:
create/edit, reversible archive/restore and confirmation-gated hard delete over authenticated
Supabase REST. Bounds mirror the schema, failed saves retain drafts, and optional fair values are
explicitly private user input—not Henneth output. Deterministic monitoring remains independent.

`docs/company_theses.sql` defines bounded inputs, explicit authenticated grants, public/anonymous
revocation and four owner-only RLS policies. The offline schema/UI gates are wired into preflight.
The feature is not live: the owner must manually apply the SQL, verify cross-user isolation and run
Supabase security advisors. No SQL was applied and nothing was staged, deployed or published.

## Resume update — Management Delivery v1 completed

The six active deterministic theses now have six categorical delivery records across the exact
20-company pilot. All currently remain `not_observed`: no strictly later retained official event
exactly matches their normalized assertion or conflict key. Source-linked events are excluded and
the latest source observation is the cutoff, preventing self-confirmation and lookahead leakage.
Broader management-guidance delivery is explicitly `blocked_no_guidance_objects` because no
first-class guidance objects exist. State, CI slice, Thesis Monitor UI and preflight gates are wired.

## Resume update — Market Expectations Gap v1 completed

Scenario Lab now computes the gap between reverse-solved revenue growth required at the current
price and the caller's entered growth assumption, using the same entered margin and P/E. Generated
state remains assumption-free with a null selected gap. The exact 20-company formula seam is gated;
this is sensitivity algebra, not a forecast, probability, valuation verdict or house case.

## Resume update — Financial Results Coverage & Qualification Queue v1 completed

All 20 pilot companies now have a deterministic metadata-only map of indexed official PSX financial
documents, three required annual-history slots, missing revenue/PAT/EPS lines, quarantined audit-only
coverage and bounded candidate document IDs for future owner-approved qualification. Only titles
that explicitly say year/twelve-month ended create an annual period; unresolved periods stay null,
and a regression gate prevents half-year notices from being misclassified. No PDF was parsed, no
legacy fact was promoted and forecast/valuation remain blocked pending genuine qualified history.

## Final authoritative pause handoff — 2026-08-23

This section supersedes the earlier restart points in this append-only checkpoint. Development is
paused by the owner after the completed waves below. The persistent objective remains the full
68-section Henneth Company Intelligence product; the product is not complete.

### Completed product and intelligence capabilities

1. Exact 20-company pilot with official-source ingestion, evidence provenance, source QA, company
   graph and deterministic change intelligence.
2. Sixteen first-class Operating Events and strict no-lookahead event studies for all 16 events.
3. Full-pilot declarative driver graphs: 160 unique edges across BANKS, CEMENT, E&P, REFINERY,
   FERTILIZER, AUTO_ASSEMBLER, POWER, OMC and HOLDING_COMPANY. ENGROH uses the explicit
   HOLDING_COMPANY override.
4. Null-safe Bear/Base/Bull impact shells. Event-driver routing is constrained by each company's
   graph; unsupported numerical impacts remain null.
5. Closed-registry signal clusters and the five canonical epistemic types: `reported_fact`,
   `derived_fact`, `inference`, `scenario` and `forecast`.
6. Conditional Historical Benchmarks v1 for all 16 events. Matching is exact by type/subtype,
   same-company and same-sector candidates remain separate, candidates strictly predate targets,
   and existing event-study outcomes are reused. Three exact prior candidates resolve; all 64
   horizon aggregates are suppressed because `n < 3`; three undated events are blocked.
7. Causal Driver Evidence Map v1 with one categorical record per driver edge. It makes no causal
   estimate and cannot promote scenario assumptions into evidence.
8. Persistent Company Brain for all 20 companies: 21 explicit domains, typed references and a
   unified timeline. Forecast and valuation domains remain blocked when evidence is unavailable.
9. Deterministic Thesis Monitoring v1, Intelligence Confidence v1 (seven transparent components),
   Management Delivery v1 (six conservative categorical records), and Evidence Watchlist v1
   (six active items across five companies; 15 explicit inactive states).
10. Private user-thesis CRUD code and owner-only SQL/RLS contract. It remains inactive until the
    owner manually applies `docs/company_theses.sql` and completes live cross-user isolation checks.
11. Financial statement v2 extraction and quarantine: 249 retained facts, zero model-loadable,
    249 audit-only and 17 conflicts. No audit-only fact is promoted.
12. Financial Coverage & Qualification Queue v1: exact 20 companies, three annual slots each,
    official-document metadata candidates and strict protection against treating half-year results
    as annual history.
13. Bounded Batch A document diagnostics were completed without consuming documents or changing
    canonical financial state. The degraded broad-parser route is frozen; do not repeat it. Batch B
    requires separate owner approval.
14. Forecast/Valuation Readiness Contract v1 covers all 20 companies. Input readiness is 0/20 and
    requires three aligned annual consolidated PKR periods for revenue, attributable PAT and EPS,
    exact official provenance, strict availability dates, compatible scale and no conflicts/flags.
    Synthetic fixtures prove the future input seam; no numerical forecast or valuation is active.
15. Snapshot Scenario Lab, reverse expectations and Expectations Gap arithmetic use caller-supplied
    growth, margin and P/E only. Generated state selects no house case, probability, forecast,
    valuation verdict or advice.
16. Product surfaces completed: Investor Snapshot, typed Company Timeline, Intelligence, Financial
    Baseline, Financial Coverage, Forecast Readiness, Scenario Lab, Thesis Monitor, Evidence
    Watchlist, Operating Intelligence, Conditional Benchmarks and Causal Map.
17. Ask Henneth is owner-authenticated and qualitative: nine server-owned answer sections, bounded
    same-company context, citation validation and no numeric/advice/cross-company leakage.
18. CI state, Ask and private CI data remain owner-gated. Pipeline builders, CI slice generation,
    offline security/UI contracts and preflight integration are complete for these waves.

### Verified state at pause

- 16 event studies and 16 conditional-benchmark records across the exact 20-company pilot.
- 1,273 conditional-benchmark UI assertions; 64 suppressed and zero available aggregates.
- Full `scripts/preflight.py`: `RESULT: OK — all checks passed, safe to deploy`.
- The sole known warning is the existing 98-ticker history backfill.
- `git diff --check` passed apart from line-ending notices.
- Main Company Navigation was planned only. Its implementation agent was interrupted before edits;
  it must not be reported as completed.

### Exact next wave on resume: Main Company Navigation

Implement the specification's exact 17 primary company tabs: Overview, Intelligence, Financials,
Earnings, Business, Operations, Scenarios, Valuation, Guidance, Catalysts, Risks, Events, Filings,
Peers, Ownership, Quant and Research. Keep existing advanced views in a secondary research-tools
row. Business/Guidance/Catalysts/Risks should use Company Brain domain references; Earnings and
Valuation must remain readiness/blocked surfaces; Peers must not imply a formal peer registry;
Ownership remains unknown without authoritative ownership data; legacy fair-value screens must be
visually and semantically separate from formal CI valuation. Add no browser-side business logic,
financial calculation, forecast or inference.

Acceptance gates for that wave: exact 17-tab registry and routing, exact 20-company rendering,
explicit unknown/blocked states, no weakening of owner auth, no duplicate producer logic, focused
UI/security checks, Python compile, JavaScript syntax, full preflight and final diff review.

## Resume update — Main Company Navigation completed

The CI company surface now has the specification's exact 17 primary tabs: Overview, Intelligence,
Financials, Earnings, Business, Operations, Scenarios, Valuation, Guidance, Catalysts, Risks,
Events, Filings, Peers, Ownership, Quant and Research. Existing specialist products are preserved
in a separate research-tools row with its own keyboard navigation boundary. Business, Guidance,
Catalysts and Risks display only Company Brain typed references. Earnings and formal valuation
remain readiness/blocked surfaces; legacy fair value is visibly separate. Peers remain unavailable
without a formal registry, and ownership remains unknown without authoritative ownership data.
No browser-side peer derivation, financial calculation, forecast, inference, auth change or state
producer was added. `check_company_navigation_ui.mjs` is preflight-wired and verifies the exact
registry, routing, 20-company boundary, explicit states and navigation isolation.

## Resume update — CI gate recovery and bounded qualification audit

The full CI preflight is green after four conservative repairs: Ask Henneth now limits projected
event studies so all 20 same-company contexts remain inside its hard context budget; the Evidence
Watchlist tab is registered from its emitted row; Scenario Lab top-level provenance is derived only
from its published per-company inputs; and Forecast Readiness counts the canonical `input_ready`
status. The current real readiness remains 0/20; none of these repairs activates a forecast,
valuation, or numerical impact model.

Financial Coverage now recognises explicit annual title forms `Year Ended 30.06.2025` and `year
ended - June 30, 2025`, while retaining the half-year rejection. The original owner-approved exact
Batch B documents were checked one at a time and remained safely quarantined: two annual reports
exceeded the 120-page cap, one exceeded the declared 12 MB cap, and one quarterly report was
image-only. A transactional v4 re-evaluation rolled back when then-unfixed CI gates failed; no
receipt or canonical financial state was retained. Do not raise caps, crop documents, OCR the
image-only file, or promote legacy audit-only facts.

The next financial qualification route needs a separate explicit approval for four newly identified
compact official counterparts, then exact-ID diagnose before consume: MLCF `psx:257465`, DGKC
`psx:258454`, LUCK `psx:257573`, and LUCK `psx:275898`. They must be added to an exact new
allowlist manifest only after approval, must pass the unchanged transport caps and v4 provenance
checks, and may still leave readiness blocked pending three aligned annual consolidated periods.

## Resume update — Formal Peer Registry v1 completed

The CI Peers tab now reads an emitted formal registry instead of remaining unavailable. The backend
builds `state/company_intel/peer_registry.json` for the exact 20-company pilot after the retained
PSX sector map refreshes and before the CI slice. Its only grouping rule is the official/exchange
sector label/code already retained in `state/sectors.json`; missing or duplicate pilot/sector state
fails closed. Formal peers are explicit pilot-sector cohorts, singleton sectors publish empty
`formal_peers` arrays, and international peers remain explicitly unavailable. No browser-side peer
derivation, valuation, performance, rank, similarity or advice path was added.

Verification after this wave:

- `peer_registry: PASS (20 companies, 9 sector groups, 5 singleton cohorts)`
- `company_navigation_ui: PASS (309 assertions, 20 company rows)`
- Full `scripts/preflight.py`: `RESULT: OK — all checks passed, safe to deploy`
- Existing non-gating warning only: 101 newly-added universe tickers still backfilling history
- No files were staged, committed, deployed, published, SQL-applied or document-reprocessed.

### Major work still required for the complete 68-section goal

1. Qualified multi-period consolidated financial histories and evidence-linked earnings bridges.
2. Genuine deterministic forecasts and implemented sector-specific financial models.
3. Formal valuation, full market-expectations and mispricing engines.
4. International analogue registry beyond the domestic pilot-sector peer registry.
5. First-class guidance/contradiction objects and broader management execution scoring.
6. Hiring, permits, tenders and other bounded alternative-data pipelines.
7. Calibrated scenario probabilities and the specification's deeper operational numeric examples.
8. Point-in-time proprietary factors, CI-specific backtests and advanced TimesFM/Qlib/RD-Agent
   layers only where sufficient evidence and history justify them.
9. Live activation and independent verification of private-thesis SQL/RLS.
10. Continuous monitoring, full 68-section completion audit, deployment readiness and a separate
    owner-approved release. Do not run `scripts/publish.py`, deploy, apply SQL or consume documents
    as part of this paused milestone commit.

Resume workflow: root/Terra orchestrates and timeboxes; GPT-5.5 handles most implementation and
quick review; Luna-high handles difficult logic and independent review; deterministic checks cover
testing. Move on when focused and full gates pass rather than reopening failed parser loops.

## Resume update — approved compact filing pass and management assertions v2

The owner-approved compact official PSX filing batch was processed through the exact-ID v4
transaction path. MLCF `psx:257465` was durably retained with its verified content hash and an
explicit `processed_unsupported` receipt: the filing yielded no qualified facts, so no financial
values were created. DGKC `psx:258454` and LUCK `psx:275898` were image-only; LUCK `psx:257573`
exceeded the declared safe file cap. They remain explicitly blocked with no receipt or canonical
financial-state mutation. The caps, no-crop policy and no-OCR rule remain unchanged.

Guidance & Contradictions v2 now preserves a closed qualitative assertion type for every accepted
same-company official-evidence object: management priority, delivery promise, project/capacity
action, stated risk or operating constraint. Exact normalized-key contradictions, no-lookahead
provenance, and the ban on numeric forecasts, valuation and advice remain intact. The monitoring
state, Company Brains and CI slice were rebuilt afterwards. Focused guidance, monitoring, Brain and
UI checks and the full preflight gate passed; the only warning remains the non-gating 101-ticker
history backfill.

Next financial approval candidate: the MLCF annual sequence needs compact filings `psx:236626`
(FY2024) and `psx:280589` (FY2026), alongside the already retained FY2025 counterpart. Approval
must be explicit before they replace the current exact restage allowlist; they must still pass
unchanged bounded transport and provenance checks and may remain unsupported.

## Resume update — conditional candidate-evidence summaries

Conditional Historical Benchmarks now emit a display-safe candidate-evidence summary for every
event: exact same-company and same-sector candidate counts, mature outcome count per horizon, the
latest strictly-prior candidate date, and an explicit evidence status. It is derived only from the
already retained strict candidates, adds no return calculation, and repeats that the result is
descriptive—not causal, a forecast, valuation or advice. The CI view renders this backend-owned
summary beside the unchanged candidate lists and thin-sample-suppressed aggregates.

Verification: the 20-company resolver check passed for 23 event benchmarks; the UI check passed
1,815 assertions with 91 suppressed aggregates and one mature aggregate; Company Brain checks and
the full preflight gate passed with only the existing 101-ticker non-gating history-backfill warning.

## Resume update — MLCF three-year financial qualification attempt blocked by image-only filings

After explicit owner approval, MLCF FY2024 `psx:236626` and FY2026 `psx:280589` passed the exact
two-ID allowlist, retained-index, official-PSX URL and transaction self-checks. Diagnostic transport
retrieved 4,428,106 bytes across 12 pages, then rejected both PDFs as `unsupported_image_only`.
Together with the prior FY2025 `psx:257465` `processed_unsupported` receipt, all three annual
counterparts are unavailable to the canonical geometry-based financial parser. No receipt was added
for the two rejected filings, and no financial observation, forecast, valuation, market expectation
or impact value was created. The source caps, no-OCR policy and audit-only quarantine remain binding.

The two-document review manifest and exact execution allowlist now record this completed approved
batch. `check_ci_reprocess_manifest.py` and the full preflight gate passed, with only the existing
101-ticker non-gating history-backfill warning.
