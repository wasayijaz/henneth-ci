#!/usr/bin/env python3
"""Refresh the standalone CI snapshot from a committed Desk revision.

This is deliberately a manual, read-only-source entrypoint.  It never pushes,
publishes, dispatches a workflow, or changes the historical pinned importer
(``fetch_desk_inputs.py``).  The current Desk revision is resolved once, all
manifest inputs are staged and parsed before any state file is replaced, and
the original Desk producer order is reused from the historical run_cloud pin.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Callable

if os.name != "nt":
    import fcntl


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
MANIFEST_PATH = Path(__file__).with_name("ci_inputs_manifest.json")
RECEIPT_PATH = ROOT / ".cache" / "ci_refresh_receipt.json"
LOCK_PATH = ROOT / ".cache" / "ci_refresh.lock"
DESK_REPOSITORY = "wasayijaz/henneth-desk"
CI_REPOSITORY = "wasayijaz/henneth-ci"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ADVISORY_STEPS = {"tv_crosscheck.py"}
COMMAND_TIMEOUT_S = 120
PRODUCER_TIMEOUT_S = 900

# Audited against ecd2bb3d:scripts/run_cloud.py.  This is intentionally static:
# a later Desk-chain edit cannot silently widen or shrink a standalone refresh.
# Every entry is CI-owned and present in this clone; build_calendar.py and other
# Desk-owned producers are deliberately excluded because they can overwrite
# imported Desk inputs.
AUDITED_CI_CHAIN = (
    "fetch_company_documents.py",
    "document_intelligence.py",
    "build_financial_series.py",
    "stage_issuer_documents.py",
    "document_intelligence.py",
    "build_financial_series.py",
    "build_financial_model_inputs.py",
    "build_financial_coverage.py",
    "build_financial_statement_v2_candidate_queue.py",
    "build_forecast_readiness.py",
    "build_financial_reprocess_blockers.py",
    "import_owner_financial_assumptions.py",
    "build_financial_engine_assumptions.py",
    "build_formal_financial_engines.py",
    "build_owner_financial_assumption_handoff.py",
    "build_financial_evidence_reconciliation.py",
    "cement_historical_reconciliation.py",
    "build_company_graph.py",
    "build_change_intelligence.py",
    "build_operating_events.py",
    "build_thesis_monitoring.py",
    "build_management_delivery.py",
    "build_evidence_watchlist.py",
    "build_ci_monitoring.py",
    "build_event_studies.py",
    "build_conditional_benchmarks.py",
    "build_causal_foundations.py",
    "build_company_scenario_lab.py",
    "build_company_brains.py",
    "build_ci_work_routing_policy.py",
    "build_ownership_source_manifest.py",
    "build_ci_completion_matrix.py",
    "build_ci_slice.py",
    "build_ci_artifact_integrity.py",
    "check_ci_artifact_integrity.py",
    "check_ci_product_contracts.py",
    "preflight.py",
)


class RefreshError(RuntimeError):
    """A refresh failed before a releasable result existed."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RefreshError(f"cannot read manifest: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("inputs"), dict):
        raise RefreshError("manifest must contain an inputs object")
    pin = str(payload.get("desk_pin_sha") or "").lower()
    if not SHA_RE.fullmatch(pin):
        raise RefreshError("manifest has an invalid desk_pin_sha")
    for relative, metadata in payload["inputs"].items():
        if not isinstance(relative, str) or not isinstance(metadata, dict):
            raise RefreshError(f"invalid manifest entry: {relative!r}")
        path_value = Path(relative)
        if path_value.is_absolute() or ".." in path_value.parts or path_value.suffix.lower() != ".json":
            raise RefreshError(f"invalid manifest path: {relative}")
    return payload


def manifest_snapshot_hash(manifest: dict) -> str:
    payload = copy.deepcopy(manifest)
    payload.pop("snapshot_sha256", None)
    return sha256_bytes(_canonical(payload))


def refreshed_manifest(manifest: dict, source_sha: str, staged_hashes: dict[str, str]) -> dict:
    result = copy.deepcopy(manifest)
    result["desk_pin_sha"] = source_sha
    result["inputs"] = {
        relative: {"sha256": staged_hashes[relative]}
        for relative in sorted(staged_hashes)
    }
    result["snapshot_sha256"] = manifest_snapshot_hash(result)
    return result


def _run(args: list[str], *, cwd: Path | None = None) -> bytes:
    try:
        result = subprocess.run(
            args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=COMMAND_TIMEOUT_S,
        )
    except FileNotFoundError as exc:
        raise RefreshError(f"required command is unavailable: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip().splitlines()
        message = detail[-1] if detail else f"exit {exc.returncode}"
        raise RefreshError(f"{' '.join(args[:3])}: {message[:180]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RefreshError(f"{' '.join(args[:3])}: timed out after {COMMAND_TIMEOUT_S}s") from exc
    return result.stdout


def _git(source_repo: Path, *args: str) -> list[str]:
    """Use a per-command trust exception; never mutate the user's Git config."""
    return ["git", "-c", f"safe.directory={source_repo}", "-C", str(source_repo), *args]


def resolve_source_sha(source_repo: Path | None) -> str:
    if source_repo is not None:
        raw = _run(_git(source_repo, "rev-parse", "--verify", "origin/main^{commit}"))
    else:
        raw = _run(["gh", "api", f"repos/{DESK_REPOSITORY}/commits/main", "--jq", ".sha"])
    source_sha = raw.decode("utf-8", "replace").strip().lower()
    if not SHA_RE.fullmatch(source_sha):
        raise RefreshError("Desk origin/main did not resolve to a full commit SHA")
    return source_sha


def resolve_ci_head() -> str:
    """Resolve the committed CI checkout/release SHA, separate from Desk input pin."""
    raw = _run(_git(ROOT, "rev-parse", "--verify", "HEAD^{commit}"))
    ci_sha = raw.decode("utf-8", "replace").strip().lower()
    if not SHA_RE.fullmatch(ci_sha):
        raise RefreshError("standalone CI HEAD did not resolve to a full commit SHA")
    return ci_sha


def _validate_source_path(relative: str) -> str:
    path_value = Path(relative)
    if path_value.is_absolute() or ".." in path_value.parts or path_value.suffix.lower() != ".json":
        raise RefreshError(f"unsafe source path: {relative}")
    return Path("state", *path_value.parts).as_posix()


def committed_reader(source_repo: Path | None, source_sha: str) -> Callable[[str], bytes]:
    def read(relative: str) -> bytes:
        source_path = _validate_source_path(relative)
        if source_repo is not None:
            return _run(_git(source_repo, "cat-file", "blob", f"{source_sha}:{source_path}"))
        encoded = source_path.replace(" ", "%20")
        return _run([
            "gh", "api", f"repos/{DESK_REPOSITORY}/contents/{encoded}?ref={source_sha}",
            "--header", "Accept: application/vnd.github.raw",
        ])

    return read


def stage_inputs(manifest: dict, reader: Callable[[str], bytes], stage_root: Path) -> dict[str, str]:
    """Fetch and validate every input without touching the live state tree."""
    staged_hashes: dict[str, str] = {}
    failures: list[str] = []
    for relative in sorted(manifest["inputs"]):
        try:
            content = reader(relative)
            json.loads(content.decode("utf-8"))
            target = stage_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            staged_hashes[relative] = sha256_bytes(content)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RefreshError) as exc:
            failures.append(f"{relative}: {type(exc).__name__}")
    if failures:
        raise RefreshError("input staging failed: " + ", ".join(failures))
    if set(staged_hashes) != set(manifest["inputs"]):
        raise RefreshError("input staging did not cover the complete manifest")
    return staged_hashes


def apply_snapshot(stage_root: Path, manifest: dict, new_manifest: dict) -> list[str]:
    """Replace only after staging succeeds; return changed relative paths."""
    targets: list[tuple[Path, Path]] = []
    for relative in sorted(manifest["inputs"]):
        targets.append((stage_root / relative, STATE / relative))
    manifest_stage = stage_root / "__ci_inputs_manifest.json"
    manifest_stage.write_text(json.dumps(new_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    targets.append((manifest_stage, MANIFEST_PATH))

    changed: list[str] = []
    backups: dict[Path, bytes | None] = {}
    replaced: list[Path] = []
    try:
        for staged, target in targets:
            content = staged.read_bytes()
            if target.exists() and target.read_bytes() == content:
                continue
            backups[target] = target.read_bytes() if target.exists() else None
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, target)
            replaced.append(target)
            changed.append("state/" + target.relative_to(STATE).as_posix() if target != MANIFEST_PATH else "scripts/ci_inputs_manifest.json")
    except OSError as exc:
        for target in reversed(replaced):
            prior = backups[target]
            if prior is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(prior)
        raise RefreshError(f"snapshot replacement failed: {type(exc).__name__}") from exc
    return changed


def audited_steps(scripts_dir: Path = ROOT / "scripts") -> list[str]:
    missing = [step for step in AUDITED_CI_CHAIN if not (scripts_dir / step).is_file()]
    if missing:
        raise RefreshError("audited CI producer missing: " + ", ".join(missing))
    return list(AUDITED_CI_CHAIN)


def _tree_fingerprint() -> dict[str, str]:
    result: dict[str, str] = {}
    for base in (STATE, ROOT / "ci-app", ROOT / "config"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                result[path.relative_to(ROOT).as_posix()] = sha256_file(path)
    return result


def should_noop(source_changed: bool, producer_changed: bool) -> bool:
    """Same-source runs are no-ops only after producers found no new CI work."""
    return not source_changed and not producer_changed


class RefreshLock:
    def __enter__(self):
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.handle = LOCK_PATH.open("a+b")
        if os.name == "nt":
            import msvcrt
            if self.handle.tell() == 0 and self.handle.seek(0, os.SEEK_END) == 0:
                self.handle.write(b"\0")
                self.handle.flush()
            self.handle.seek(0)
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                self.handle.close()
                raise RefreshError("another CI refresh is already running") from exc
        else:
            try:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                self.handle.close()
                raise RefreshError("another CI refresh is already running") from exc
        return self

    def __exit__(self, *_exc):
        if os.name == "nt":
            import msvcrt
            self.handle.seek(0)
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close()


def write_receipt(receipt: dict) -> None:
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(RECEIPT_PATH)


def run_chain(steps: list[str], ci_sha: str) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    skipped: list[str] = []
    build_env = os.environ.copy()
    build_env["HENNETH_CI_SOURCE_COMMIT_SHA"] = ci_sha
    build_env.setdefault(
        "HENNETH_CI_BUILD_CUTOFF_AT",
        datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    for step in steps:
        if step == "import_owner_financial_assumptions.py" and not all(
            os.environ.get(name, "").strip()
            for name in ("HENNETH_CI_SUPABASE_URL", "HENNETH_CI_SUPABASE_SERVICE_KEY", "HENNETH_CI_OWNER_USER_ID")
        ):
            skipped.append(step)
            print(f"SKIPPED {step}: optional owner-assumption credentials unavailable; retained state preserved", flush=True)
            continue
        print(f"=== {step} ===", flush=True)
        try:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / step)],
                cwd=ROOT,
                env=build_env,
                timeout=PRODUCER_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{step}:timeout>{PRODUCER_TIMEOUT_S}s")
            print(f"FAILED {step}: timed out after {PRODUCER_TIMEOUT_S}s", flush=True)
            continue
        except OSError as exc:
            failures.append(f"{step}:launch:{type(exc).__name__}")
            print(f"FAILED {step}: launch error {type(exc).__name__}", flush=True)
            continue
        if result.returncode and step not in ADVISORY_STEPS:
            failures.append(f"{step}:{result.returncode}")
            print(f"FAILED {step} exit={result.returncode}", flush=True)
    return failures, skipped


def run(source_repo: Path | None = None) -> int:
    receipt: dict = {"status": "failed", "release": "not attempted", "source_repo": str(source_repo) if source_repo else "github"}
    try:
        with RefreshLock():
            manifest = load_manifest()
            source_sha = resolve_source_sha(source_repo)
            steps = audited_steps()
            ci_sha = resolve_ci_head()
            receipt["source_sha"] = source_sha
            receipt["ci_head_sha"] = ci_sha
            receipt["steps"] = steps
            with tempfile.TemporaryDirectory(prefix="ci-refresh-", dir=ROOT / ".cache") as temporary:
                stage_root = Path(temporary)
                reader = committed_reader(source_repo, source_sha)
                staged_hashes = stage_inputs(manifest, reader, stage_root)
                new_manifest = refreshed_manifest(manifest, source_sha, staged_hashes)
                changed_inputs = apply_snapshot(stage_root, manifest, new_manifest)
            before = _tree_fingerprint()
            failures, skipped = run_chain(steps, ci_sha)
            after = _tree_fingerprint()
            producer_changed = any(before.get(path) != digest or path not in before for path, digest in after.items()) or any(path not in after for path in before)
            source_changed = bool(changed_inputs)
            receipt.update({
                "status": "failed" if failures else ("noop" if should_noop(source_changed, producer_changed) else "refreshed"),
                "release": "not attempted",
                "changed_inputs": changed_inputs,
                "producer_changed": producer_changed,
                "producer_failures": failures,
                "producer_skips": skipped,
                "snapshot_sha256": new_manifest["snapshot_sha256"],
            })
            write_receipt(receipt)
            if failures:
                print("REFRESH FAILED; release not attempted", flush=True)
                return 1
            print(f"CI refresh {receipt['status']}; release not attempted", flush=True)
            return 0
    except RefreshError as exc:
        receipt["error"] = str(exc)
        write_receipt(receipt)
        print(f"REFRESH FAILED: {exc}; release not attempted", flush=True)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, help="local Desk git checkout; reads committed origin/main only")
    args = parser.parse_args(argv)
    return run(args.source_repo.resolve() if args.source_repo else None)


if __name__ == "__main__":
    raise SystemExit(main())
