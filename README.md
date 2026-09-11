# Henneth CI

Henneth CI (Company Intelligence) is the private, static company-research surface split from the
Henneth Desk. It turns retained company documents, financial evidence, operating events, and
deterministic analysis into the `Henneth Desk 2.CI.0` Vercel app. It never places orders and never
turns research into personalized advice.

## Layout

- `Henneth Desk 2.CI.0/` — the static Vercel app. Its Vercel root is exactly this folder; do not
  move or rename it. The app reads only `data/company_intelligence.json`.
- `scripts/` — CI producers, checks, the workflow gates, and `fetch_desk_inputs.py`.
- `state/company_intel/` — CI-owned generated state.
- Selected top-level `state/` files — CI-owned document, brief, queue, and financial ledgers.
- `scripts/ci_inputs_manifest.json` — SHA-256-pinned shared Desk inputs used for local and release
  builds. The copies under `state/` are inputs, not CI-owned data.
- `config/` — retained configuration. `config/desk.json` is sensitive and must never be served.
- `.github/workflows/` — the CI contract and protected production release workflows.

## Build the slice

With `DESK_READ_TOKEN` or `GITHUB_TOKEN` available:

```text
python scripts/fetch_desk_inputs.py
python scripts/build_ci_slice.py
```

The fetch step downloads every manifest entry from the pinned Desk commit, verifies its SHA-256,
and replaces files atomically. It exits non-zero for a missing token, failed download, missing
input, or hash mismatch. The builder then rewrites:

```text
Henneth Desk 2.CI.0/data/company_intelligence.json
```

For a local checkout that already contains the materialized inputs, only the second command is
needed.

## Releases

Pull requests and pushes to `main` run `ci-contract.yml`. Production is released through
`ci-production-release.yml` using `workflow_dispatch`, a protected environment, a tested immutable
preview, and an exact commit/deployment check before promotion. Release credentials, owner identity,
and provider secrets belong in protected environment configuration; no token or owner UUID belongs
in this repository or the static app.

## Research rules

- Every displayed fact must trace to retained `state/` evidence or a primary source.
- Unknown or unavailable data remains explicitly unknown; numbers are never fabricated.
- The product uses research language such as “the setup” or “the desk’s read”, never advice such as
  “you should buy”.
- CI is read-only with respect to trading execution. Any execution decision remains manual and
  outside this repository.
