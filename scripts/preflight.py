#!/usr/bin/env python3
"""Final local gate for the standalone Henneth CI repository.

The Desk and CI products now have separate repositories. This gate therefore
checks only the CI app, CI state, and the committed CI workflow contract.
Focused product checks run in ``check_ci_product_contracts.py`` immediately
before this gate in both CI workflows.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
APP = ROOT / "Henneth Desk 2.CI.0"
SLICE = APP / "data" / "company_intelligence.json"


def _finite(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    return True


def _json(path: Path) -> object:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{path.relative_to(ROOT)}: {exc}") from exc
    if not _finite(value):
        raise RuntimeError(f"{path.relative_to(ROOT)}: contains NaN or Infinity")
    return value


def _run(*parts: str) -> None:
    result = subprocess.run(parts, cwd=ROOT, capture_output=True, text=True, timeout=45)
    if result.returncode:
        detail = (result.stderr or result.stdout or "child check failed").strip()[-1000:]
        raise RuntimeError(f"{' '.join(parts)}: {detail}")


def main() -> int:
    try:
        if not APP.is_dir() or not (APP / "vercel.json").is_file():
            raise RuntimeError("CI app root or its Vercel configuration is missing")
        payload = _json(SLICE)
        if not isinstance(payload, dict) or not isinstance(payload.get("tickers"), list):
            raise RuntimeError("CI slice must contain a tickers array")
        if not payload["tickers"]:
            raise RuntimeError("CI slice contains no ticker rows")
        profiles = _json(STATE / "company_profiles.json")
        pilot = profiles.get("pilot", {}).get("symbols", []) if isinstance(profiles, dict) else []
        if len(payload["tickers"]) != len(pilot):
            raise RuntimeError(f"CI slice has {len(payload['tickers'])} rows; pilot has {len(pilot)}")
        for path in sorted((STATE / "company_intel").glob("*.json")):
            _json(path)
        _run(sys.executable, str(ROOT / "scripts" / "check_ci_contract_workflow.py"))
        integrity = STATE / "company_intel" / "artifact_integrity.json"
        if integrity.exists():
            _run(sys.executable, str(ROOT / "scripts" / "check_ci_artifact_integrity.py"))
    except (OSError, RuntimeError) as exc:
        print(f"Henneth CI preflight: FAIL — {exc}")
        return 1
    print(f"Henneth CI preflight: OK ({len(payload['tickers'])} ticker rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
