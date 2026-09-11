# Henneth CI Architecture

Henneth CI is a standalone Company Intelligence repository and product. It owns the deterministic
CI producers, generated CI state, bounded app slice, validation workflow, and controlled production
release. The Henneth Desk repository remains an external input source; its publish loop and cron are
not part of CI ownership.

## System shape

```text
pinned Desk inputs
        |
        v
manual input fetch or refresh-in-development
        |
        v
CI producers -> state/company_intel/*.json -> build_ci_slice.py
                                             |
                                             v
                                ci-app/data/company_intelligence.json
                                             |
                                             v
                             controlled Vercel release workflow
                                             |
                                             v
                                      ci.henneth.app
```

The app does not call market providers and does not reach around the generated slice into Desk
working files. The state directory is the seam between deterministic producers and the static app.

## Ownership

| Area | Current owner | Boundary |
| --- | --- | --- |
| CI producers and checks | `scripts/` in this repository | deterministic, source-backed, no order path |
| Generated CI products | `state/company_intel/` | rebuilt only by the CI chain and checked for integrity |
| Selected imported ledgers | explicitly selected top-level `state/` files | retained inputs or CI products as defined by the manifest |
| App | `ci-app/` | reads only `data/company_intelligence.json` plus its static assets |
| Input pin | `scripts/ci_inputs_manifest.json` | Desk revision and per-file SHA-256 values |
| Contract validation | `.github/workflows/ci-contract.yml` | validates; does not promote production |
| Production release | `.github/workflows/ci-production-release.yml` | protected preview, authenticated smoke, exact promotion |

## External inputs

The Desk repository is external to this checkout. The manifest pins the Desk revision and the exact
JSON inputs consumed by CI. `scripts/fetch_desk_inputs.py` preserves a historical pinned snapshot.
The manual `scripts/refresh_ci.py` path is still being developed and is not an approved cron or
unattended release mechanism.

## Release and deployment

Pull requests and pushes to `main` run the CI contract workflow. Production uses only the manual
controlled workflow: it validates the target commit, finalizes artifacts, deploys one preview,
verifies the preview commit, runs anonymous and authenticated owner/non-owner smoke checks, promotes
that exact preview, verifies production identity, and retains post-promotion smoke evidence.

The Vercel project is externally configured with root directory `ci-app`. The root `.vercel/project.json`
only links this checkout to the CI project; deployment credentials and smoke credentials remain in
the protected environment.

Release staging uses Vercel's Production environment with `--skip-domain`, not its Preview
environment. This gives a tested production-configured deployment whose ID is retained when
promoted. The live domain is assigned only after anonymous and authenticated staging checks pass.

No CI cron is approved. `scripts/publish.py` is a Desk/shared-repository publish mechanism and must
never be used for CI. CI does not commit or push as part of refresh or release preparation.

## Security and product boundaries

The CI app is owner-only for protected data. Middleware and the Ask endpoint verify the configured
owner boundary and must fail closed for invalid, expired, or non-owner credentials. Auth behavior is
not duplicated or relaxed by documentation or refresh tooling.

`config/desk.json` is private and never served. Its capital and alert configuration are not part of
the app slice. No credential value belongs in source, generated state, logs, documentation, or the
static app. CI is research-only: it never places orders, executes trades, or publishes personalized
advice.

## Current release status

The latest controlled release attempt did not succeed: anonymous preview smoke passed, authenticated
owner/non-owner password grant returned HTTP 400, and promotion was skipped. This remains a release
failure until the protected credentials are corrected and both smoke stages pass.

## Verification seam

Important behavior is checked through stable interfaces: Python/JavaScript syntax checks, focused CI
contract checkers, artifact-integrity verification, `preflight.py`, and the release-workflow checker.
Generated artifact changes must be reported; no production release is complete without authenticated
preview and post-promotion verification.
