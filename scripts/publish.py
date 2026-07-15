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
    # other side pushed since our last pull. On rejection, rebase onto the latest origin.
    #
    # Auto-resolving a conflict is only safe for files under state/ — that's regenerated
    # deterministic data, so preferring our freshly-built version and letting the other
    # side's copy regenerate next cycle loses nothing. It is NOT safe for hand-authored
    # files (dashboard/*, scripts/*, docs/*, CLAUDE.md, ...) — this repo has no CI/PR
    # review, so silently picking a side there could permanently discard someone's actual
    # code edit with zero visibility. So: try a plain rebase; if it conflicts, auto-resolve
    # ONLY if every conflicted file is under state/; otherwise abort and fail loudly so a
    # human resolves it, instead of guessing.
    def _push():
        r = _run(["git", "push", "origin", "main"])
        return r.returncode == 0, (r.stderr or r.stdout or "").strip()

    ok, last_err = _push()
    if not ok:
        for attempt in range(3):
            _run(["git", "fetch", "origin", "main"])
            rb = _run(["git", "rebase", "origin/main"])
            if rb.returncode != 0:
                conflicted = _run(["git", "diff", "--name-only", "--diff-filter=U"]).stdout.split()
                non_state = [f for f in conflicted if not f.replace("\\", "/").startswith("state/")]
                if non_state or not conflicted:
                    _run(["git", "rebase", "--abort"])
                    print(f"publish: rebase conflict on hand-authored file(s) {non_state or conflicted} — "
                          f"refusing to auto-resolve (could silently discard a real code edit). "
                          f"Manual merge needed: git pull --rebase origin main, resolve by hand, re-run.")
                    sys.exit(1)
                # every conflict is confined to regeneratable state/ data — safe to keep our fresh build
                _run(["git", "checkout", "--theirs", "--"] + conflicted)  # "theirs" in a rebase = our replayed commit
                _run(["git", "add"] + conflicted)
                cont = _run(["git", "rebase", "--continue"])
                if cont.returncode != 0:
                    _run(["git", "rebase", "--abort"])
                    print(f"publish: rebase --continue failed after state-only auto-resolve: {(cont.stderr or cont.stdout)[:300]}")
                    sys.exit(1)
            ok, last_err = _push()
            if ok:
                break
            time.sleep(2 + attempt)  # small backoff growth so repeated collisions don't lockstep
        if not ok:
            print(f"publish: could not push after retries — last git error:\n{last_err[:400]}")
            sys.exit(1)
    print(f"publish: pushed '{msg}' -> Vercel is deploying (~60s to https://psx-trade-desk.vercel.app/).")


if __name__ == "__main__":
    main()
