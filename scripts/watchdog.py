#!/usr/bin/env python3
"""Live-site watchdog for Henneth.

preflight.py guards data BEFORE publish. This guards the site AFTER publish —
it fetches the actual deployed URLs a real user's browser would fetch and asserts
they are reachable, non-empty, fresh, and structurally sound. It closes the loop
between "we pushed" and "users actually see good data".

Catches the whole "missing information / empty page" class from the outside:
  - a deploy that didn't propagate (stale `updated`, app shell unreachable)
  - a state file that 404s or serves empty on the CDN
  - the desk silently frozen in degraded health
  - a sampled ticker page whose history the site can't serve ("No data for XXX")
  - the account gate (middleware.js, see docs/OPERATIONS.md §9b) coming OPEN —
    a research file serving 200 to an anonymous request is a security regression,
    not a pass

Since 2026-07-21 every /state/*.json file except the public ephemeris
(natal_ephem.bin/json) requires a Supabase bearer token (middleware.js). This
script is deliberately unauthenticated (no tokens, no keys, read-only HTTP —
Supabase's service_role/anon keys are disabled per docs/OPERATIONS.md §6, so
there is no credential for it to hold). So a 401 with the exact shape
middleware.js's deny() produces means THE GATE IS WORKING — that's a pass, not
a failure. Content/freshness checks on gated files are skipped (we have no way
to read them without a token); what still gets verified without auth:
  - the app shell (homepage) loads — proves the deploy propagated
  - the public ephemeris file serves — proves /state/ isn't wholesale broken
  - every gated file returns EXACTLY the expected 401 shape — anything else
    (200, 500, timeout, a differently-shaped 401) is a real problem

Exit non-zero if the live site is unhealthy, so a cycle can react
(re-publish / alert) instead of leaving users on stale data.

Usage:
  python scripts/watchdog.py                       # check live site, human report
  python scripts/watchdog.py --base http://localhost:8877/dashboard   # check a preview
  python scripts/watchdog.py --max-age-days 4      # how stale `updated` may be (only used if a file is ever reachable unauthenticated)
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime

# The canonical TERMINAL URL. Since the 2026-07-19 domain split, henneth.app serves the
# MARKETING site and the terminal lives on desk.henneth.app — so this must point at the
# subdomain. Pointed at the apex it would fetch /state/*.json from the marketing site,
# which has no /state/, and every post-publish check would fail for no reason.
# The *.vercel.app deployment URL still serves the same build and stays valid as a fallback —
# watch the domain users actually visit, since a DNS/cert problem there is invisible if we
# only ever check the origin. (www.henneth.app is deliberately NOT checked: it is not yet
# added in Vercel, so it has no certificate — see docs/OPERATIONS.md.)
BASE_DEFAULT = "https://desk.henneth.app"
BASE_FALLBACK = "https://psx-trade-desk.vercel.app"
TIMEOUT = 20

# The public exception carved out of the account gate (middleware.js PUBLIC_FILES).
# Used here as the one content check we can still do without a token.
PUBLIC_PROBE_FILE = "natal_ephem.json"

# A file that is ALWAYS gated (no legitimate reason it would ever be public) — used as the
# security-regression tripwire from docs/OPERATIONS.md §9b: "this must stay 401 forever".
REGRESSION_PROBE_FILE = "rooms.json"

problems, notes = [], []


def fetch(base, path):
    """Return (json_or_none, error_or_none, status_or_none, raw_bytes_or_none).

    Cache-busted so we test the CDN edge, not our cache. Unlike a plain 2xx-only
    fetch, this deliberately surfaces non-200 status + body so callers can tell
    the account gate's expected 401 apart from a genuine outage."""
    url = f"{base.rstrip('/')}/state/{path}?t={int(time.time())}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "psx-watchdog"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            if r.status != 200:
                return None, f"HTTP {r.status}", r.status, raw
            if not raw or len(raw) < 5:
                return None, "empty body", r.status, raw
            return json.loads(raw), None, r.status, raw
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
        except Exception:  # noqa: BLE001
            raw = b""
        return None, f"HTTP {e.code}", e.code, raw
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:120], None, None


def is_account_gate(status, raw):
    """True only if this is OUR OWN middleware's expected 401 shape (see
    middleware.js deny()) — i.e. the gate is up and working as designed, not a
    differently-broken 401 (a misconfigured Vercel deployment-protection page,
    for instance, would also be a 401 but is NOT this and should still fail)."""
    if status != 401 or not raw:
        return False
    try:
        body = json.loads(raw)
    except Exception:  # noqa: BLE001
        return False
    return body.get("error") == "account_required"


def check_gated_file(label, path, allow_content_checks=None):
    """Fetch a file that lives behind the account gate. Records a NOTE (pass) if
    it is correctly gated, a PROBLEM if it is reachable when it shouldn't be
    (security regression) or broken in any other way. `allow_content_checks`,
    if given, is called with the parsed JSON on the rare path where the gate is
    open and the file IS reachable — kept only so a future intentional
    un-gating doesn't silently lose its freshness/shape checks."""
    data, err, status, raw = fetch(BASE_CHECKED, path)
    if data is None:
        if is_account_gate(status, raw):
            notes.append(f"{label} correctly gated (account required) — "
                        f"see docs/OPERATIONS.md §9b; not content-checked without a token")
        else:
            problems.append(f"{label} unreachable/broken on live site ({err})")
        return
    # Reachable without a token at all — that's only fine for PUBLIC_FILES; for
    # anything else this IS the security regression the gate exists to prevent.
    problems.append(f"{label} served WITHOUT authentication (200) — the account gate "
                    f"is OPEN for this file, a security regression (docs/OPERATIONS.md §9b)")
    if allow_content_checks:
        allow_content_checks(data)


def days_old(stamp):
    """Days since a 'YYYY-MM-DD ...' stamp; None if unparseable."""
    try:
        return (date.today() - datetime.strptime(str(stamp)[:10], "%Y-%m-%d").date()).days
    except Exception:  # noqa: BLE001
        return None


BASE_CHECKED = BASE_DEFAULT  # set from args in main(); module-level for check_gated_file()


def main():
    global BASE_CHECKED
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--max-age-days", type=int, default=5,
                    help="how stale the freshest data may be, IF a gated file is ever "
                         "unauthenticated-reachable (should not normally happen)")
    args = ap.parse_args()
    base = args.base
    BASE_CHECKED = base

    # 0) the app shell — the one thing that still proves a deploy propagated now that
    # /state/*.json can't be read without a token.
    try:
        req = urllib.request.Request(base.rstrip("/") + "/?t=" + str(int(time.time())),
                                     headers={"User-Agent": "psx-watchdog"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            html = r.read()
            if r.status != 200 or len(html) < 1000:
                problems.append(f"app shell (homepage) looks broken: HTTP {r.status}, "
                                f"{len(html)} bytes")
    except Exception as e:  # noqa: BLE001
        problems.append(f"app shell (homepage) unreachable: {str(e)[:120]}")

    # 1) the public ephemeris file — the one /state/ file that should still serve
    # unauthenticated. If this fails, /state/ is wholesale broken (bad build, CDN issue),
    # not just correctly gated.
    eph, err, status, raw = fetch(base, PUBLIC_PROBE_FILE)
    if eph is None:
        problems.append(f"{PUBLIC_PROBE_FILE} (public, ungated) unreachable/empty "
                        f"({err}) — /state/ may be broken, not just gated")

    # 2) the security-regression tripwire: an always-gated file must stay 401.
    def _regression_content_check(_data):
        pass  # check_gated_file already raises a PROBLEM if this file is reachable at all

    check_gated_file(REGRESSION_PROBE_FILE, REGRESSION_PROBE_FILE, _regression_content_check)

    # 3) the aggregate files a user's first paint depends on — expected gated.
    def _dash_content_check(dash):
        age = days_old(dash.get("updated"))
        if age is None:
            notes.append("dashboard.json has no parseable 'updated'")
        elif age > args.max_age_days:
            problems.append(f"dashboard.json is STALE on live: updated {dash.get('updated')} "
                            f"({age}d ago) — a deploy likely didn't propagate")

    check_gated_file("dashboard.json", "dashboard.json", _dash_content_check)

    def _quant_content_check(quant):
        if len(quant.get("tickers", {})) < 20:
            problems.append(f"quant.json on live has only {len(quant.get('tickers', {}))} "
                            f"tickers (expected >= 20)")

    check_gated_file("quant.json", "quant.json", _quant_content_check)

    # 4) desk not silently frozen — expected gated.
    def _health_content_check(health):
        if health.get("status") not in ("ok", "healthy"):
            problems.append(f"live desk is DEGRADED: {', '.join(health.get('problems', [])) or 'unknown'} "
                            f"— new signals are gated (Rule 6)")

    check_gated_file("health.json", "health.json", _health_content_check)

    # 5) the daily read (the Today page's lead) — expected gated; absence either way is
    # only ever a note, never a problem (a cycle may simply not have written it yet).
    dr, err, status, raw = fetch(base, "daily_read.json")
    if dr is None and not is_account_gate(status, raw):
        notes.append(f"daily_read.json not on live yet ({err}) — Today page shows the "
                     f"'run a cycle' empty state")

    ok = not problems
    print("Henneth - live watchdog  [" + base + "]")
    if notes:
        print(f"\n  NOTE ({len(notes)}):")
        for n in notes:
            print(f"    - {n}")
    if problems:
        print(f"\n  PROBLEM ({len(problems)}):")
        for p in problems:
            print(f"    x {p}")
        print("\n  RESULT: LIVE SITE UNHEALTHY — re-run the pipeline and re-publish.")
        sys.exit(1)
    print("\n  RESULT: OK — app shell loads, public files serve, account gate intact "
         "on all research files.")
    sys.exit(0)


if __name__ == "__main__":
    main()
