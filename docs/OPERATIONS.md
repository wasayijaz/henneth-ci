# Henneth CI Operations

Henneth CI is a standalone, owner-only Company Intelligence product. This runbook describes the
current CI repository and release boundary only. The inherited Desk/shared-repository runbook is
preserved in `docs/OPERATIONS-HISTORICAL.md` and is not an instruction for this checkout.

## Repository boundary

- Deployable app root: `ci-app/`.
- CI-owned generated products: `state/company_intel/` and the selected CI ledgers under `state/`.
- Static app slice: `ci-app/data/company_intelligence.json`.
- CI validation: `.github/workflows/ci-contract.yml`.
- Controlled production release: `.github/workflows/ci-production-release.yml`.
- Vercel project: `ci.henneth.app`, externally configured with project root `ci-app`.

The Desk repository is an external source of retained inputs, not this repository's working tree or
publish path. `scripts/ci_inputs_manifest.json` records the pinned Desk revision and input hashes.
Use `scripts/fetch_desk_inputs.py` only when the exact pinned snapshot is required.

## Refresh status

There is no approved CI refresh cron. Desk cron and scheduled Desk tasks do not refresh or release
this product.

Manual refresh work is being developed in `scripts/refresh_ci.py`, with its current contract in
`docs/CI_REFRESH.md`. It is not an unattended service and does not commit, push, dispatch Actions,
or promote a release. Keep its source and receipt files outside unrelated rename or release work.

## Release path

The only production release path is the controlled workflow:

1. Validate the repository and CI contracts.
2. Restamp and verify the release artifacts for the target commit.
3. Deploy one immutable Vercel preview.
4. Verify the preview is bound to the target commit.
5. Run anonymous preview smoke, then authenticated owner/non-owner preview smoke.
6. Promote only that tested preview.
7. Verify production is the promoted deployment and retain authenticated production smoke.

The protected `ci-production` environment supplies deployment and smoke credentials. Credential
values never belong in this repository, state, logs, documentation, or the static app.

The workflow's `preview` job means a staged URL, not Vercel's Preview environment.
It uses `deploy --prod --skip-domain`: production configuration with no live-domain switch.
Promoting a Preview-environment deployment creates a new production deployment, so it cannot
satisfy the exact-tested-deployment contract. Both metadata checks require target `production`;
the post-promotion check must still match the staged deployment ID exactly.

The latest recorded attempt did not release: preview anonymous smoke passed, the authenticated
owner/non-owner check failed at the password grant with HTTP 400, and promotion was skipped.

Do not use `scripts/publish.py`, a raw `git push`, a Desk publish loop, or an unapproved cron to
release CI. A failed authentication or artifact gate is a stop condition.

## Data and security boundaries

`ci-app/data/company_intelligence.json` is the app's bounded data seam. Producers write state;
the app reads the generated slice. Middleware and the Ask endpoint enforce the owner-only boundary.
Do not weaken JWT verification, owner/non-owner isolation, no-store behavior, or protected data
routes.

`config/desk.json` is private configuration and must never be served. A metadata-only inspection on
2026-09-11 found the `capital_pkr` field and a blank `alerts.telegram_bot_token`; no credential
value is recorded here. Keep the file out of served roots and documentation.

## Verification

Run the focused checker for the changed surface, the relevant Python/JavaScript syntax checks,
`scripts/preflight.py` when generated CI state is involved, and `git diff --check`. Report generated
artifact changes exactly. Do not claim a production release until both authenticated smoke stages
and the promotion/deployment checks pass.
