#!/usr/bin/env python3
"""Publish the desk to the live site (Vercel) — the one efficient push path.

Every loop/task calls this instead of re-implementing git. It:
  1. runs the preflight gate (never publish a structurally broken cycle),
  2. stages everything,
  3. commits + pushes ONLY if state actually changed,
  4. a push to `main` auto-deploys on Vercel (~60s) — no other step.

Deterministic, zero tokens. Safe to call every run: a no-op when nothing changed.

Usage:
  python scripts/publish.py "Hourly desk refresh 11:20 PKT"
  python scripts/publish.py            # uses a timestamped default message
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kw)


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else f"Desk refresh {time.strftime('%Y-%m-%d %H:%M')}"

    # 1) preflight gate
    pf = _run([sys.executable, "scripts/preflight.py"])
    print(pf.stdout.strip()[-400:])
    if pf.returncode != 0:
        print("publish: PREFLIGHT FAILED — not publishing (last-good site stays live).")
        sys.exit(1)

    # 2) stage
    _run(["git", "add", "-A"])

    # 3) commit only if there is something staged
    if _run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print("publish: nothing changed — no deploy needed.")
        return

    c = _run(["git", "commit", "-m", msg])
    if c.returncode != 0:
        print("publish: commit failed:\n" + (c.stderr or c.stdout)[:300])
        sys.exit(1)

    # 4) push -> Vercel auto-deploys. RACE-SAFE: the cloud GitHub-Actions cron and the
    # app loops both push to main, so a push can be rejected (non-fast-forward) if the
    # other side pushed since our last pull. On rejection, rebase our commit onto the
    # latest origin, preferring OUR just-generated state on any conflict (`-X theirs`
    # keeps the replayed commit's version — the fresh full state we just built), then
    # retry. Whatever the other side raced in is regenerated next cycle, so nothing is lost.
    def _push():
        return _run(["git", "push", "origin", "main"]).returncode == 0

    if not _push():
        ok = False
        for _ in range(3):
            _run(["git", "fetch", "origin", "main"])
            rb = _run(["git", "rebase", "-X", "theirs", "origin/main"])
            if rb.returncode != 0:
                _run(["git", "rebase", "--abort"])
                print("publish: rebase conflict during concurrent push — skipping; next cycle republishes.")
                sys.exit(1)
            if _push():
                ok = True
                break
            time.sleep(2)
        if not ok:
            print("publish: could not push after retries (heavy concurrent activity) — next cycle republishes.")
            sys.exit(1)
    print(f"publish: pushed '{msg}' -> Vercel is deploying (~60s to https://psx-trade-desk.vercel.app/).")


if __name__ == "__main__":
    main()
