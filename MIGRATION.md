# Henneth CI migration

This repository is the Company Intelligence split from the Desk repository.

- Baseline repository: `wasayijaz/henneth-desk`
- Desk baseline pin: `ecd2bb3db8626f72234adf69a779c8e5f6b66187`
- CI slice baseline SHA-256: `B02B0C419F6C32EAC750405DE801D9EAD7BD48DF28A86CD631ADB0D2AE8D609B`
- Split date: `2026-09-11`
- CI app root: `Henneth Desk 2.CI.0/`

The standalone repository keeps the CI-owned state and deterministic producers. Shared Desk state
is fetched locally from the pinned manifest by `scripts/fetch_desk_inputs.py`; those inputs are not
Company Intelligence ownership. The generated private app slice is rebuilt with
`python scripts/build_ci_slice.py`.

Accepted debt:

- `config/desk.json` still lives in this CI repository. It contains owner capital and the Telegram
  bot token and must never be served. Extract it into a minimal CI-only config before the next
  configuration cleanup.
- Owner secrets and protected release environment values must be recreated in the standalone CI
  repository; they are not migrated into source control.
- `check_root_ask_ui.mjs` was deleted because it tests the Desk root `dashboard/app.js` endpoint,
  not the CI app. CI Ask checks remain under `check_ask_henneth*`.

## Migration journal

- 2026-09-11: Repository created on GitHub and standalone `main` pushed from the desk
  baseline `ecd2bb3d`. Initial contract validation pending on Actions.
- 2026-09-11: The standalone CI app root is `ci-app/`; this supersedes the earlier
  `Henneth Desk 2.CI.0/` path while preserving that historical entry above.
- 2026-09-11: Owner and protected release credentials were securely transferred to the
  external protected environment configuration. No credential values are stored in this journal.
- 2026-09-11: Metadata-only configuration review found `config/desk.json` has a private
  `capital_pkr` field and a blank `alerts.telegram_bot_token`; no credential value is recorded.
  The file remains private and must never be served.
- 2026-09-11: The controlled release attempt did not succeed. Preview anonymous smoke passed;
  the authenticated owner/non-owner password grant returned HTTP 400, so promotion was skipped.
- 2026-09-11: Dedicated non-owner smoke identity provisioned with owner approval; both saved
  credential pairs passed GitHub diagnostic 34634153663. No personal account was modified.
- 2026-09-11: Release 34635318113 passed all preview checks but `promote` created a different
  production deployment. The unchanged exact-ID gate rejected it. Corrected staging to
  `--prod --skip-domain` and added missing-flag/Preview-target regression tests. Same-ID and
  owner/non-owner gates remain mandatory. Sources: https://vercel.com/docs/cli/promote and
  https://vercel.com/docs/cli/deploy#skip-domain.
