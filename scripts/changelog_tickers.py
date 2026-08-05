"""Auto-append a CHANGELOG.md entry when the ticker universe grows.

Diffs state/universe.json symbols against the last-seen set (state/.ticker_seen.json).
New symbols -> one templated, always-safe public entry (symbols only, no internals) is
appended to CHANGELOG.md, then the seen-set is updated so the same tickers are never
announced twice.

Deliberately bypasses the hand-curated <!--public--> rule in build_changelog.py for this
ONE category only: the content is fully templated (a symbol list), so there is nothing an
author could accidentally leak. Every other release still requires a hand-written block.

Free, deterministic, no network. Safe to re-run — a no-op when the universe hasn't grown.
"""
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "state" / "universe.json"
SEEN = ROOT / "state" / ".ticker_seen.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def main():
    if not UNIVERSE.exists():
        print("changelog_tickers: no universe.json — skipping")
        return

    uni = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    symbols = set(uni.get("symbols", {}))
    if not symbols:
        print("changelog_tickers: universe.json has no symbols — skipping")
        return

    seen = set(json.loads(SEEN.read_text(encoding="utf-8"))) if SEEN.exists() else set()
    new = sorted(symbols - seen)

    if not seen:
        # first run ever — record the baseline, announce nothing (avoid a false
        # "N new tickers" entry for the desk's entire existing universe)
        SEEN.write_text(json.dumps(sorted(symbols), indent=1), encoding="utf-8")
        print(f"changelog_tickers: baseline recorded ({len(symbols)} tickers) — skipping")
        return

    if not new:
        print("changelog_tickers: no new tickers this cycle")
        return

    date = time.strftime("%Y-%m-%d")
    version = date.replace("-", ".")
    # avoid colliding with a same-day release already in the file
    existing = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else ""
    n = 2
    v = version
    while f"v{v}" in existing:
        v = f"{version}.{n}"
        n += 1

    ticker_list = ", ".join(new)
    count = len(new)
    plural = "ticker" if count == 1 else "tickers"
    entry = (
        f"\n## {date} — v{v} — {count} new {plural} added to coverage\n\n"
        f"<!--public\n"
        f"The desk now also tracks: {ticker_list}. History is backfilling, so charts fill "
        f"in over the next few sessions.\n"
        f"-->\n\n"
        f"### Universe expansion\n\n"
        f"Auto-recorded by scripts/changelog_tickers.py: {ticker_list} added to "
        f"state/universe.json this cycle.\n"
    )

    with CHANGELOG.open("a", encoding="utf-8") as f:
        f.write(entry)

    SEEN.write_text(json.dumps(sorted(symbols), indent=1), encoding="utf-8")
    print(f"changelog_tickers: recorded {count} new ticker(s) as v{v}: {ticker_list}")


if __name__ == "__main__":
    main()
