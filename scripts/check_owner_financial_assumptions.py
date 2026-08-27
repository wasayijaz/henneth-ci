#!/usr/bin/env python3
"""Focused checks for the private owner financial assumptions on-ramp."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import import_owner_financial_assumptions as importer
from formal_financial_engines import approved_records


SQL = ROOT / "docs" / "company_financial_assumptions.sql"


def fail(message: str) -> None:
    raise AssertionError(message)


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def sql_text() -> str:
    return SQL.read_text(encoding="utf-8")


def assert_sql_contract() -> None:
    text = sql_text()
    lower = " ".join(text.lower().split())
    required = [
        "reference-only sql: this file is not applied by the desk",
        "create table if not exists public.company_financial_assumptions",
        "symbol ~ '^[a-z0-9]{2,12}$'",
        "metric in ('revenue_growth_pct', 'net_margin_pct', 'exit_pe', 'net_debt')",
        "alter table public.company_financial_assumptions enable row level security",
        "revoke all on table public.company_financial_assumptions from public, anon",
        "grant select, insert on table public.company_financial_assumptions to authenticated",
        "for select to authenticated using (user_id = (select auth.uid()))",
        "for insert to authenticated with check (user_id = (select auth.uid()))",
    ]
    for marker in required:
        if marker not in lower:
            fail(f"SQL contract marker missing: {marker}")
    for forbidden in ("grant select, insert, update", "grant update", "grant delete", "to anon", "security definer", "user_metadata"):
        if forbidden in lower:
            fail(f"SQL contract contains forbidden marker: {forbidden}")
    symbols = [item for item in (
        "MLCF", "OGDC", "DGKC", "PPL", "UBL", "PSO", "NBP", "LUCK", "FFC", "BOP",
        "HUBC", "MEBL", "HBL", "ATRL", "ENGROH", "MARI", "CNERGY", "NRL", "GAL", "PRL",
    ) if f"'{item}'" in text]
    if len(symbols) != 20:
        fail(f"expected 20 pilot symbols in SQL, found {len(symbols)}")


def sample_state(root: Path, existing: list[dict] | None = None) -> Path:
    write_json(root / "company_profiles.json", {
        "updated": "2024-03-02",
        "pilot": {"symbols": ["MLCF", "DGKC"]},
    })
    write_json(root / "company_intel" / "forecast_readiness.json", {"as_of": "2024-03-02", "companies": {}})
    write_json(root / "company_intel" / "financial_model_inputs.json", {"as_of": "2024-03-02", "companies": {}})
    out = root / "company_intel" / "financial_engine_assumptions.json"
    write_json(out, {"schema_version": 1, "records": existing or []})
    return out


OWNER_ID = "11111111-1111-4111-8111-111111111111"


def row(row_id: str, metric: str, value: float, *, symbol: str = "MLCF", approved: bool = True, available_on: str = "2024-03-01") -> dict:
    unit = importer.ALLOWED_METRICS[metric][0]
    return {
        "id": row_id,
        "user_id": OWNER_ID,
        "symbol": symbol,
        "metric": metric,
        "value": value,
        "unit": unit,
        "available_on": available_on,
        "source_label": f"Owner source {metric}",
        "source_url": "https://example.com/source.pdf",
        "rationale": f"Owner rationale for {metric}",
        "approved": approved,
        "approved_at": available_on + "T10:00:00Z",
        "created_at": available_on + "T10:00:00Z",
    }


def assert_importer_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="henneth-owner-assumptions-") as td:
        root = Path(td)
        stale = {
            "symbol": "MLCF",
            "metric": "exit_pe",
            "value": 4.0,
            "approved": True,
            "available_on": "2024-02-01",
            "imported_by": importer.IMPORTED_BY,
            "source": {"id": importer.SOURCE_PREFIX + "stale", "label": "stale", "path": "supabase:old", "available_on": "2024-02-01"},
        }
        owner_manual = {
            "symbol": "MLCF",
            "metric": "current_price",
            "value": 10.0,
            "approved": True,
            "available_on": "2024-03-01",
            "record_type": "approved_market_operand",
            "source": {"id": "manual:close", "label": "manual close", "path": "state/history/MLCF.json", "available_on": "2024-03-01"},
        }
        out = sample_state(root, [stale, owner_manual])
        rows = [
            row("growth-old", "revenue_growth_pct", 5.0, available_on="2024-02-01"),
            row("growth-new", "revenue_growth_pct", 7.0, available_on="2024-03-01"),
            row("margin", "net_margin_pct", 12.0),
            row("pe", "exit_pe", 6.0),
            row("debt", "net_debt", -100.0),
            row("unapproved", "exit_pe", 8.0, approved=False),
            row("future", "net_margin_pct", 14.0, available_on="2024-03-03"),
            {**row("bad-url", "exit_pe", 9.0), "source_url": "javascript:alert(1)"},
            row("bad-symbol", "exit_pe", 9.0, symbol="ZZZZ"),
        ]
        result = importer.run(
            state_dir=root,
            output_path=out,
            env={
                importer.ENV_URL: "https://example.supabase.co",
                importer.ENV_KEY: "test-service-key",
                importer.ENV_OWNER_ID: OWNER_ID,
            },
            remote_rows=rows,
        )
        state = json.loads(out.read_text(encoding="utf-8"))
        imported = [record for record in state["records"] if record.get("imported_by") == importer.IMPORTED_BY]
        if result["imported"] != 4 or len(imported) != 4:
            fail(f"imported count mismatch: {result}")
        if any(record.get("source", {}).get("id", "").endswith("stale") for record in state["records"]):
            fail("stale imported record was preserved")
        if not any(record.get("source", {}).get("id") == "manual:close" for record in state["records"]):
            fail("non-imported manual record was not preserved")
        records = approved_records(state, "MLCF", "2024-03-02")
        for metric in ("revenue_growth_pct", "net_margin_pct", "exit_pe", "net_debt"):
            if metric not in records:
                fail(f"formal engine did not accept imported approved {metric}")
        if records["revenue_growth_pct"]["value"] != 7.0:
            fail("latest owner-approved growth row was not selected")
        if any(record.get("approved") is not True for record in imported):
            fail("unapproved row entered imported state")
        if result["rejected"].get("not_approved") != 1 or result["rejected"].get("available_on_after_state_cutoff") != 1:
            fail(f"expected rejection counters missing: {result['rejected']}")


def assert_missing_config_noop() -> None:
    with tempfile.TemporaryDirectory(prefix="henneth-owner-assumptions-noop-") as td:
        root = Path(td)
        out = sample_state(root)
        before = out.read_bytes()
        result = importer.run(state_dir=root, output_path=out, env={})
        after = out.read_bytes()
        if result["mode"] != "dry-run" or before != after:
            fail("missing Supabase config must be a no-op dry-run")


def assert_cli_noop() -> None:
    with tempfile.TemporaryDirectory(prefix="henneth-owner-assumptions-cli-") as td:
        root = Path(td)
        out = sample_state(root)
        child_env = dict(os.environ)
        for key in (importer.ENV_URL, importer.ENV_KEY, importer.ENV_OWNER_ID):
            child_env.pop(key, None)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "import_owner_financial_assumptions.py"), "--state-dir", str(root), "--output", str(out)],
            capture_output=True,
            text=True,
            timeout=30,
            env=child_env,
        )
        if result.returncode != 0 or "dry-run missing_config" not in result.stdout:
            fail("CLI missing-config no-op failed")


def main() -> None:
    assert_sql_contract()
    assert_importer_contract()
    assert_missing_config_noop()
    assert_cli_noop()
    print("owner_financial_assumptions: PASS (SQL/RLS, importer, approved-only gate, no-op without secrets)")


if __name__ == "__main__":
    main()
