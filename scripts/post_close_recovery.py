#!/usr/bin/env python3
"""Single-shot post-close Desk recovery; never touches Company Intelligence."""
import subprocess
import sys
from pathlib import Path

from post_close_integrity import evaluate


SCRIPTS = Path(__file__).resolve().parent
RECOVERY_STEPS = [
    "fetch_history.py", "liquidity.py", "correlation.py", "quant.py",
    "predictability.py", "backtest.py", "snapshot.py", "score_fundamentals.py",
    "fetch_indices.py", "fetch_sectors.py", "fetch_intraday.py", "data_health.py",
    "compute_fairvalue.py", "build_signals.py", "build_checkpoint_trigger.py --desk",
    "fetch_research.py", "build_explainer.py", "room_dossier.py", "room_queue.py",
    "room_gate.py", "room_score.py", "room_verify.py", "build_public_slice.py",
    "build_dashboard.py",
]


def main() -> None:
    first = evaluate()
    if not first["required"] or first["status"] == "ok":
        print(f"post-close recovery: {first['status']} — no retry needed")
        return
    print("post-close recovery: stale/mixed snapshot detected — running one Desk-only retry")
    for spec in RECOVERY_STEPS:
        name, *args = spec.split()
        result = subprocess.run([sys.executable, str(SCRIPTS / name), *args])
        if result.returncode != 0:
            raise SystemExit(f"post-close recovery failed at {name}")
    final = evaluate()
    if final["status"] != "ok":
        for problem in final["problems"]:
            print(f"  ! {problem}")
        raise SystemExit("post-close recovery did not produce a coherent session")
    print(
        f"post-close recovery: OK — {final['same_day_symbols']}/"
        f"{final['traded_symbols']} traded counters current"
    )


if __name__ == "__main__":
    main()
