"""PSX sector map — the authoritative code -> name list, straight from PSX.

WHY THIS EXISTS
The DPS market-watch feed tags every symbol with a NUMERIC sector code ("0809") and no name.
Nothing in the desk turned those into sectors, which silently broke real things:
  * CLAUDE.md Rule 4 ("no two positions in the same sector") — build_signals.py was comparing
    COMPANY NAMES, which are unique per ticker, so the limit could never bind.
  * compute_fairvalue.py's "relative_pe" was documented and rendered as "priced like its PEERS"
    but was computed against the median P/E of the WHOLE market.
  * The astro lens needs real sectors to map planetary significators onto.

WHERE THE NAMES COME FROM (Rule 2: from the data layer, never from memory)
PSX's own screener page ships a <select> of every sector as value=code, label=name. That is the
authority, so we parse it rather than hardcoding a list. A hand-written map was tried first and
was wrong on most codes (0820 is Exploration, not Marketing; 0828 is Technology, not Textile) —
which is exactly why this is fetched and then cross-checked below.

SELF-CHECK
Fetching a mapping is worthless if it silently binds to the wrong names, so the parsed map is
verified against ANCHOR tickers whose sector is not in doubt (OGDC must be Exploration, LUCK must
be Cement, UBL must be a Bank...). Any anchor mismatch = the mapping is wrong = keep the last
good file and exit degraded, never overwrite good data with bad.

Network failure -> keeps the existing file, exits 0 (never crashes the cycle).
Writes state/sectors.json.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psx_data  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
OUT = STATE / "sectors.json"

# Tickers whose sector is beyond argument — the mapping must agree with every one of these or it
# is not trustworthy. Keyed by ticker -> a substring that MUST appear in the resolved sector name.
ANCHORS = {
    "OGDC": "EXPLORATION", "PPL": "EXPLORATION", "MARI": "EXPLORATION",
    "PSO": "MARKETING", "APL": "MARKETING",
    "LUCK": "CEMENT", "DGKC": "CEMENT", "MLCF": "CEMENT",
    "UBL": "BANK", "HBL": "BANK", "MCB": "BANK",
    "FFC": "FERTILIZER", "EFERT": "FERTILIZER",
    "HUBC": "POWER", "KAPCO": "POWER",
    "SYS": "TECHNOLOGY", "PTC": "TECHNOLOGY",
    "SEARL": "PHARMACEUTICAL",
    "NML": "TEXTILE",
}


def _clean(name: str) -> str:
    """'FOOD &amp; PERSONAL CARE PRODUCTS' -> 'Food & Personal Care Products'."""
    n = name.replace("&amp;", "&").replace("&nbsp;", " ").strip()
    n = re.sub(r"\s+", " ", n)
    small = {"and", "or", "of", "the", "&", "/"}
    out = []
    for w in n.split(" "):
        if w.upper() in ("INV.", "COS.", "CO."):
            out.append(w.title())
        elif w.lower() in small:
            out.append(w.lower())
        else:
            out.append(w.capitalize() if w.isalpha() or "&" not in w else w)
    s = " ".join(out)
    return s[:1].upper() + s[1:]


def fetch_map() -> dict:
    html = psx_data._get("/screener").text
    pairs = re.findall(r'<option[^>]*value="(08\d{2})"[^>]*>([^<]{3,80})</option>', html)
    return {code: _clean(name) for code, name in pairs}


def main():
    STATE.mkdir(exist_ok=True)
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    try:
        code_name = fetch_map()
    except Exception as e:
        print(f"sectors: fetch failed ({type(e).__name__}: {e}) — keeping the existing map")
        sys.exit(0)

    if len(code_name) < 20:
        print(f"sectors: only {len(code_name)} sectors parsed — PSX markup likely changed. "
              f"Keeping the existing map rather than overwriting it with a partial one.")
        sys.exit(0)

    # per-ticker sector from the live feed (already fetched by snapshot.py)
    live = {}
    lp = STATE / "live.json"
    if lp.exists():
        live = json.loads(lp.read_text(encoding="utf-8")).get("tickers", {})
    by_ticker = {}
    for sym, row in live.items():
        code = str(row.get("sector") or "").strip()
        if code in code_name:
            by_ticker[sym] = {"code": code, "sector": code_name[code]}

    # --- the self-check: every anchor must land in the sector it obviously belongs to
    bad, checked = [], 0
    for sym, must in ANCHORS.items():
        got = by_ticker.get(sym, {}).get("sector")
        if not got:
            continue
        checked += 1
        if must.lower() not in got.lower():
            bad.append(f"{sym} resolved to '{got}' but must contain '{must}'")
    if bad:
        print("sectors: MAPPING FAILED its anchor checks — refusing to publish a wrong map:")
        for b in bad:
            print(f"  x {b}")
        sys.exit(0 if prev else 1)     # keep the old good map; only hard-fail if we never had one
    if checked < 8:
        print(f"sectors: only {checked} anchors present in live.json — mapping unverified, keeping existing")
        sys.exit(0)

    counts = {}
    for v in by_ticker.values():
        counts[v["sector"]] = counts.get(v["sector"], 0) + 1

    out = {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "source": "https://dps.psx.com.pk/screener (PSX's own sector <select>)",
        "note": ("Authoritative PSX sector classification, parsed from PSX rather than hardcoded. "
                 "Verified on every run against anchor tickers whose sector is not in doubt; a "
                 "mismatch keeps the last good map instead of publishing a wrong one."),
        "anchors_checked": checked,
        "n_sectors": len(code_name),
        "codes": code_name,
        "tickers": by_ticker,
        "universe_counts": dict(sorted(counts.items(), key=lambda x: -x[1])),
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"sectors: {len(code_name)} PSX sectors | {len(by_ticker)} universe tickers mapped | "
          f"{checked} anchors verified")
    for s, n in list(sorted(counts.items(), key=lambda x: -x[1]))[:10]:
        print(f"  {n:3}  {s}")


if __name__ == "__main__":
    main()
