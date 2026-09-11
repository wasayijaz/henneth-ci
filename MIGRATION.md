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
