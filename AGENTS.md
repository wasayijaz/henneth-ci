# Henneth CI Agent Instructions

Henneth CI is a standalone Company Intelligence repository. It is not the Henneth Desk
repository and must be operated as its own product.

## Read first

1. `README.md` — repository map and build entrypoints.
2. `docs/OPERATIONS.md` — current CI-only operating boundaries.
3. `docs/ARCHITECTURE.md` — current ownership, data seams, and release flow.
4. `MIGRATION.md` — append-only migration journal.
5. `docs/OPERATIONS-HISTORICAL.md` — inherited Desk/shared-repository guidance; historical only.

## Product boundary

- The deployable app root is `ci-app/`. It must remain a space-free directory name.
- The CI product reads the generated `ci-app/data/company_intelligence.json` slice and protected
  CI state. It does not read Desk working-tree files directly.
- `state/company_intel/` and the explicitly selected CI ledgers are CI-owned outputs.
- Shared Desk JSON is external input. `scripts/ci_inputs_manifest.json` pins the source files and
  their hashes; do not silently substitute dirty Desk files or guessed data.
- CI never places orders, executes trades, or turns research into personalized advice.

## Refresh and release

- No CI refresh cron is approved. Do not add a schedule or imply that Desk automation refreshes CI.
- `scripts/refresh_ci.py` and `docs/CI_REFRESH.md` are manual refresh work in development. Do not
  treat them as an unattended production service.
- The controlled release is `.github/workflows/ci-production-release.yml`: validate, deploy one
  preview, verify its commit, run anonymous and authenticated smoke checks, then promote only the
  tested preview and retain the post-promotion smoke.
- `ci-contract.yml` is validation, not a production deployment path.
- Never use `scripts/publish.py`, a raw push, or a Desk publish loop to release CI.

## Security and change discipline

- Never print, commit, serve, or document credential values. Protected environment secrets belong in
  the external release configuration.
- `config/desk.json` is private and must never be served. Treat its capital and alert fields as
  sensitive even when a token field is blank.
- Do not weaken middleware, JWT checks, owner/non-owner isolation, or no-store boundaries.
- Preserve unrelated staged, unstaged, and untracked work. Do not stage refresh-worker or lead-owned
  files unless the owner explicitly assigns them.
- Generated artifacts may be rebuilt only when the task requires it; report their exact changes.
- Do not commit or push unless explicitly requested.

## Verification

For meaningful changes, run the focused checks that cover the changed boundary, then inspect
`git diff --check` and the final worktree. The controlled release workflow must pass its structural
checker and self-test before anyone triggers it. A failed credential smoke check means promotion is
skipped; never bypass that gate.
