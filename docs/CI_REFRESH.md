# Manual CI refresh

`scripts/refresh_ci.py` is the standalone Henneth CI refresh entrypoint. It is
manual by design; it adds no schedule and does not replace the protected manual
release workflow.

## Run

From the standalone repository:

```text
python scripts/refresh_ci.py
```

The normal path resolves `wasayijaz/henneth-desk` `main` once through `gh api`,
then reads every declared `state/` input from that committed SHA. For local
verification, use a Desk checkout; the script reads committed `origin/main`,
never the checkout's dirty files:

```text
python scripts/refresh_ci.py --source-repo "D:\PSX Trader X Claude"
```

All downloaded blobs are staged first, parsed as JSON, and hash-recorded. A
missing input, invalid JSON, download error, or replacement error leaves the
existing snapshot and its `desk_pin_sha` unchanged. The manifest then records
the new Desk source SHA, per-file SHA-256 values, and a deterministic
`snapshot_sha256`. Generated CI artifacts receive the current standalone CI
`HEAD` as `HENNETH_CI_SOURCE_COMMIT_SHA`; the Desk pin remains in the manifest
and refresh receipt. Concurrent refreshes are serialized by the ignored lock
under `.cache/`.

## Producer behavior

After the snapshot is installed, the script runs the explicit, audited CI-owned
subset of the ordered chain from the original Desk `scripts/run_cloud.py` at
commit `ecd2bb3db8626f72234adf69a779c8e5f6b66187`, preserving its duplicate
document-consumption steps and order. The list is static and every listed file
must be present; a missing audited producer is a hard failure, never a silent
skip. Desk-owned producers such as `build_calendar.py` are excluded because
they can overwrite imported Desk inputs. `supabase_ci_store.py` is excluded
because the refresh has no external write path. A same-SHA run still executes
the chain so pending PSX/issuer filings are not skipped; it is a no-op only
when those producers also produce no changes. The optional owner-assumption
import is explicitly skipped, with retained state preserved, when its three
credentials are unavailable.

Every run writes a local receipt to `.cache/ci_refresh_receipt.json` and prints
the result. Any producer failure reports `release not attempted` and exits
non-zero. The script never commits, pushes, publishes, dispatches Actions, or
promotes a release. The historical pinned replay importer remains available:

```text
python scripts/fetch_desk_inputs.py
```

Use that command when the exact historical `desk_pin_sha` snapshot is required;
use `refresh_ci.py` when advancing the standalone CI snapshot to current Desk
`main`.

## Routine mapping

The existing Henneth daily refresh routine is unchanged: automation id
`henneth-daily-refresh`, target thread
`01a0900a-4ba9-7210-bd96-1610d0fa474b`, weekday 17:20 heartbeat. Its prompt
explicitly excludes Henneth CI artifacts, so this entrypoint is a separately
invoked manual CI operation. The automation file declares no parent model;
its prompt specifies `gpt-5.6-luna` with high reasoning for spawned judgment
agents. No automation schedule or target was changed for this refresh. This
manual CI entrypoint is not owned by that Desk routine.

## Regression check

```text
python scripts/check_ci_refresh.py
```

The check covers transactional missing-input failure, stable source pin and
snapshot hash, explicit chain completeness, and the rule that a same-source run
cannot be skipped while producer work is pending.
