#!/usr/bin/env python3
"""Publish the desk to the live site (Vercel) — the one efficient push path.

Every loop/task calls this instead of re-implementing git. It:
  1. runs the preflight gate (never publish a structurally broken cycle),
  2. stages state/ ONLY (add --code to also ship hand-authored files),
  3. commits + pushes ONLY if something actually changed,
  4. a push to `main` auto-deploys on Vercel (~60s) — no other step.

Deterministic, zero tokens. Safe to call every run: a no-op when nothing changed.

Staging is scoped on purpose — the cloud cron and any number of interactive sessions
share one checkout, so a blanket stage publishes whoever else's half-finished edits are
lying around. Data refreshes stay automatic; shipping code stays deliberate.

Usage:
  python scripts/publish.py "Hourly desk refresh 11:20 PKT"      # state/ only
  python scripts/publish.py "Fix sizing bug" --code              # + code/docs changes
  python scripts/publish.py                                      # timestamped default msg
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kw)


def main():
    # positional message only — otherwise `publish.py --code` would commit with the literal
    # message "--code"
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    msg = positional[0] if positional else f"Desk refresh {time.strftime('%Y-%m-%d %H:%M')}"

    # 1) preflight gate
    pf = _run([sys.executable, "scripts/preflight.py"])
    print(pf.stdout.strip()[-400:])
    if pf.returncode != 0:
        print("publish: PREFLIGHT FAILED — not publishing (last-good site stays live).")
        sys.exit(1)

    # 2) stage — SCOPED. This used to be a blanket `git add -A`, which is the same mistake
    # the rebase logic below already refuses to make (see the note at step 4: auto-resolving
    # is safe for state/ but NOT for hand-authored files). Staging had no such care, so a
    # publish swept up whatever happened to be in the working tree.
    #
    # That is not just cosmetic. Multiple sessions and the cloud cron share this checkout.
    # On 2026-07-19 three commits carried work their message never mentioned — a Desk Room
    # commit shipped another session's in-progress dashboard/app.js and scripts/push_send.py.
    # Committing a file nobody has finished editing can publish broken code, and the message
    # gives no clue it happened.
    #
    # So: state/ (regenerated deterministic data — always safe to publish) stages by default.
    # Hand-authored files require --code, which makes a code release a deliberate act rather
    # than a side effect of whoever happens to run the next data refresh.
    code_mode = "--code" in sys.argv
    _run(["git", "add", "-A", "--", "state/"])

    # what else is dirty? report it rather than silently including or silently dropping it
    other = [ln[3:].strip().strip('"') for ln in
             _run(["git", "status", "--porcelain"]).stdout.splitlines()
             if ln[3:].strip().strip('"') and not ln[3:].strip().strip('"').replace("\\", "/").startswith("state/")]

    if code_mode and other:
        _run(["git", "add", "-A"])
        print(f"publish: --code — also staging {len(other)} hand-authored file(s): {', '.join(other[:8])}"
              + (f" (+{len(other)-8} more)" if len(other) > 8 else ""))
    elif other:
        print(f"publish: NOT committing {len(other)} hand-authored file(s) — data-only publish.")
        for f in other[:12]:
            print(f"    · {f}")
        if len(other) > 12:
            print(f"    · (+{len(other)-12} more)")
        print("  These may belong to another session mid-edit. If they are YOURS and ready, "
              "re-run: python scripts/publish.py \"<msg>\" --code")

    # 3) commit only if there is something staged
    if _run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        if other:
            # loud, not silent: code changed but this was a data-only publish, so nothing shipped
            print("publish: no state change, and code changes were left unstaged — NOTHING PUBLISHED. "
                  "Re-run with --code if those edits are yours and ready to ship.")
            return
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
    print(f"publish: pushed '{msg}' -> Vercel is deploying (~60s to https://henneth.app/).")


if __name__ == "__main__":
    main()
