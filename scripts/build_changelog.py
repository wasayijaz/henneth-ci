"""Extract the PUBLIC release notes from CHANGELOG.md into state/changelog.json.

ONE SOURCE, TWO AUDIENCES
CHANGELOG.md is the engineering record and must stay that way — it names database migrations,
describes a self-promotion hole that was found and closed, and discusses internals like
BILLING_LIVE. None of that belongs in front of a subscriber. But maintaining a second, parallel
"user changelog" file guarantees the two drift, and the desk has enough of those already.

So: one file, with an explicit public block per release.

    ## 2026-07-22 — v2026.07.22 — Mobile tables and the sizing calculator

    <!--public
    Tables fit your phone screen now instead of scrolling sideways.
    A free position-size calculator is on the website.
    -->

    ### Engineering detail nobody outside needs...

FAIL CLOSED, DELIBERATELY. A release with no `<!--public ... -->` block publishes NOTHING for that
version. The failure mode of forgetting the marker is "the user sees no note", which is a shrug.
The failure mode of an opt-out design — publish everything unless marked secret — is leaking a
migration name or a security detail the first time someone forgets. Those are not comparable, so
the safe one is the default.

The same reasoning bans any auto-summarising of the engineering prose: a generated summary of a
paragraph about a closed vulnerability is still about a closed vulnerability.

VERSIONING — CalVer, `YYYY.MM.DD`, plus `.N` for a second release on the same day.
Chosen over semver because releases here are date-driven rather than milestone-driven, and because
the number should answer the question a user actually has, which is "how current is my desk?".
"v2026.07.22" answers that instantly; "v1.14.2" answers nothing. It also sorts and compares as a
plain string, which is what the terminal's "is there something new?" check needs.

Writes state/changelog.json. Free, deterministic, no network. Safe to re-run.
"""
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "CHANGELOG.md"
OUT = ROOT / "state" / "changelog.json"

# "## 2026-07-22 — v2026.07.22 — Mobile tables"  (version and title both optional)
HEAD = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*(?:[—–-]\s*v([\d.]+))?\s*(?:[—–-]\s*(.*))?$")
PUBLIC = re.compile(r"<!--\s*public\s*(.*?)-->", re.S)

# A last-resort tripwire. The public block is hand-written, so this is not a sanitiser and must not
# be treated as one — it is a shout when an obvious internal term slips through, on the assumption
# that whoever wrote it was moving fast. Anything matching blocks the build rather than publishing.
FORBIDDEN = re.compile(
    r"\b(service_role|anon key|api[_ ]key|secret|token|password|supabase|migration|RLS|"
    r"BILLING_LIVE|capital_pkr|\.env|vulnerab|exploit|CVE)\b", re.I)


def parse(md: str):
    releases, cur, buf = [], None, []

    def flush():
        if not cur:
            return
        body = "\n".join(buf)
        m = PUBLIC.search(body)
        if not m:
            return                      # no marker -> nothing published for this release
        # ONE NOTE PER PARAGRAPH, not per line. Markdown source wraps at ~100 chars, so a
        # line-per-note rule chopped every wrapped sentence into two or three fragments — each
        # rendered as its own bullet, mid-clause. Blank lines separate notes; wrapped lines join.
        notes = [" ".join(p.split()) for p in re.split(r"\n\s*\n", m.group(1).strip())]
        notes = [n.lstrip("-•* ").strip() for n in notes if n.strip()]
        if notes:
            releases.append({**cur, "notes": notes})

    # FENCE-AWARE, and this is not hypothetical: the "How to write an entry" section at the top of
    # CHANGELOG.md contains a worked EXAMPLE release inside a code fence. Without this the parser
    # read that example as a real release and published its sample notes as the current version —
    # documentation poisoning the artefact it documents. Anything inside ``` is prose about the
    # format, never an entry.
    fenced = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        h = HEAD.match(line)
        if h:
            flush()
            date, ver, title = h.group(1), h.group(2), (h.group(3) or "").strip()
            cur = {"date": date, "version": ver or date.replace("-", "."), "title": title}
            buf = []
        elif cur:
            buf.append(line)
    flush()
    return releases


def main():
    if not SRC.exists():
        print("build_changelog: no CHANGELOG.md — skipping")
        sys.exit(0)

    releases = parse(SRC.read_text(encoding="utf-8"))

    bad = []
    for r in releases:
        for n in r["notes"]:
            hit = FORBIDDEN.search(n)
            if hit:
                bad.append(f"{r['version']}: '{hit.group(0)}' in {n[:60]}…")
    if bad:
        print("build_changelog: REFUSING to publish — internal terms in a public block:")
        for b in bad:
            print(f"  · {b}")
        sys.exit(1)          # loud: a release note is not worth leaking an internal detail over

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "current": releases[0]["version"] if releases else None,
        "note": "Public release notes only. The engineering record is CHANGELOG.md and is not published.",
        "releases": releases[:20],       # the terminal only ever shows a handful
    }, indent=1, ensure_ascii=False), encoding="utf-8")

    cur = releases[0]["version"] if releases else "none"
    print(f"changelog: {len(releases)} public release(s), current v{cur}")
    sys.exit(0)


if __name__ == "__main__":
    main()
