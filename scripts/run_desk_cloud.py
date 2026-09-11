#!/usr/bin/env python3
"""Deterministic Henneth Desk pipeline only; Company Intelligence is separate."""
import subprocess
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent
STEPS = [
    ("update_universe.py",), ("fetch_history.py",), ("fetch_deep_history.py",),
    ("liquidity.py",), ("fetch_company_profiles.py",), ("correlation.py",),
    ("fetch_dividends.py",), ("fetch_dividends_deep.py",), ("fetch_fundamentals.py",),
    ("fetch_insider_offmarket.py",), ("build_calendar.py",), ("quant.py",),
    ("predictability.py",), ("backtest.py",), ("snapshot.py",),
    ("score_fundamentals.py",), ("fetch_indices.py",), ("fetch_sectors.py",),
    ("fetch_intraday.py",), ("fetch_global.py",), ("fetch_georisk.py",),
    ("astro_engine.py",), ("astro_history.py",), ("astro_charts.py",),
    ("astro_natal.py",), ("astro_context.py",), ("astro_claims.py",),
    ("fetch_macro_history.py",), ("sector_macro.py",), ("sector_dossier.py",),
    ("tv_crosscheck.py",), ("data_health.py",), ("compute_fairvalue.py",),
    ("build_signals.py",), ("build_checkpoint_trigger.py", "--desk"),
    ("fetch_research.py",), ("build_explainer.py",), ("room_dossier.py",),
    ("room_queue.py",), ("room_gate.py",), ("room_score.py",),
    ("room_verify.py",), ("design_lint.py",), ("build_astro_lite.py",),
    ("build_public_slice.py",), ("changelog_tickers.py",),
    ("build_changelog.py",), ("build_dashboard.py",),
]
ADVISORY = {"tv_crosscheck.py"}


def main() -> None:
    failed = []
    for step in STEPS:
        name, *args = step
        print(f"\n=== {name} {' '.join(args)} ===".rstrip())
        result = subprocess.run([sys.executable, str(SCRIPTS / name), *args])
        if result.returncode != 0 and name not in ADVISORY:
            failed.append(name)
            print(f"  ! {name} exited {result.returncode}")
    print("\n" + ("ALL OK" if not failed else f"FAILED: {', '.join(failed)}"))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
