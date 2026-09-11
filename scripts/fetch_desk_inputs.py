#!/usr/bin/env python3
"""Fetch the pinned, hashed Desk state inputs required by Henneth CI."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

import requests


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path(__file__).with_name("ci_inputs_manifest.json")
STATE = ROOT / "state"
REPOSITORY = "wasayijaz/henneth-desk"


def _load_manifest() -> dict:
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {MANIFEST_PATH}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("inputs"), dict):
        raise SystemExit("ci_inputs_manifest.json must contain an inputs object")
    pin = str(payload.get("desk_pin_sha") or "")
    if len(pin) != 40 or any(ch not in "0123456789abcdef" for ch in pin.lower()):
        raise SystemExit("ci_inputs_manifest.json has an invalid desk_pin_sha")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    token = os.environ.get("DESK_READ_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("missing DESK_READ_TOKEN or GITHUB_TOKEN", flush=True)
        return 1

    manifest = _load_manifest()
    pin = manifest["desk_pin_sha"]
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

    failures: list[str] = []
    for relative, metadata in sorted(manifest["inputs"].items()):
        if not isinstance(relative, str) or not isinstance(metadata, dict):
            failures.append(f"invalid manifest entry: {relative!r}")
            continue
        expected = str(metadata.get("sha256") or "").lower()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            failures.append(f"{relative}: invalid sha256 in manifest")
            continue
        target = (STATE / relative).resolve()
        if not target.is_relative_to(STATE.resolve()):
            failures.append(f"{relative}: path escapes state/")
            continue
        url = f"https://raw.githubusercontent.com/{REPOSITORY}/{pin}/state/{relative.replace(chr(92), '/') }"
        try:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            content = response.content
        except requests.RequestException as exc:
            failures.append(f"{relative}: download failed ({exc.__class__.__name__})")
            continue
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected:
            failures.append(f"{relative}: sha256 mismatch")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile("wb", dir=target.parent, delete=False) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            temporary.replace(target)
        except OSError as exc:
            failures.append(f"{relative}: write failed ({exc.__class__.__name__})")

    if failures:
        for failure in failures:
            print(failure)
        return 1
    print(f"fetched and verified {len(manifest['inputs'])} Desk inputs at {pin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
