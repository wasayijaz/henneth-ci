"""Audit-only: does PSX's own DPS company profile carry a usable incorporation date
for the tickers company_charts.json currently marks `unavailable`?

astro_charts.py's own comment (as of this audit) dismissed DPS company pages as carrying
only "incorporated under the Companies Act, 1913" boilerplate with no date. Spot-checks
showed that's wrong for at least some tickers (dps.psx.com.pk/company/<TICKER> Profile tab
has a free-text "BUSINESS DESCRIPTION" with a specific incorporation sentence). This script
checks ALL of them and reports real coverage numbers before anyone decides whether/how to
use incorporation date as a chart birth moment.

NOTE: incorporation date is NOT first-trade date (company_charts.json's stated convention).
This script only measures data availability. It does not build charts and does not change
company_charts.json.

Writes state/incorporation_audit.json. Network failure on an individual ticker -> record the
failure and continue; never crash the run.
"""
import datetime as dt
import json
import pathlib
import re
import time

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
OUT = STATE / "incorporation_audit.json"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
DELAY_SECONDS = 0.4

DESC_RE = re.compile(
    r'BUSINESS DESCRIPTION</div><p>(.*?)</p>', re.S
)
TAG_RE = re.compile(r'<[^>]+>')

MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
FULL_DATE_RES = [
    re.compile(rf'\b{MONTH}\s+\d{{1,2}},?\s+\d{{4}}\b'),   # July 02, 1948
    re.compile(rf'\b\d{{1,2}}\s+{MONTH}\s*,?\s+\d{{4}}\b'),  # 12 April 1995
]
YEAR_RE = re.compile(r'\b(18|19|20)\d{2}\b')


def classify(desc_text):
    """Return (precision, matched_text) for the incorporation sentence in desc_text."""
    idx = desc_text.lower().find('incorporat')
    if idx == -1:
        return "no_mention", None
    window = desc_text[idx:idx + 220]
    for pat in FULL_DATE_RES:
        m = pat.search(window)
        if m:
            return "full_date", m.group(0)
    m = YEAR_RE.search(window)
    if m:
        return "year_only", m.group(0)
    return "no_date", window[:120]


def fetch_description(ticker):
    url = f"https://dps.psx.com.pk/company/{ticker}"
    r = requests.get(url, headers=HDRS, timeout=15)
    r.raise_for_status()
    m = DESC_RE.search(r.text)
    if not m:
        return None
    return TAG_RE.sub('', m.group(1)).strip()


def main():
    charts_path = STATE / "company_charts.json"
    charts = json.loads(charts_path.read_text(encoding="utf-8"))
    tickers = sorted(charts.get("unavailable", {}).keys())

    results = {}
    counts = {"full_date": 0, "year_only": 0, "no_date": 0, "no_mention": 0, "fetch_error": 0}

    for i, tk in enumerate(tickers):
        try:
            desc = fetch_description(tk)
        except requests.RequestException as e:
            results[tk] = {"status": "fetch_error", "error": str(e)}
            counts["fetch_error"] += 1
            time.sleep(DELAY_SECONDS)
            continue

        if desc is None:
            results[tk] = {"status": "no_profile_page"}
            counts["fetch_error"] += 1
            time.sleep(DELAY_SECONDS)
            continue

        precision, matched = classify(desc)
        results[tk] = {"status": precision, "matched": matched, "description": desc[:400]}
        counts[precision] += 1

        if (i + 1) % 25 == 0:
            print(f"{i + 1}/{len(tickers)} checked...", flush=True)

        time.sleep(DELAY_SECONDS)

    out = {
        "updated": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "purpose": "Audit only: does DPS company profile carry a usable incorporation date "
                   "for company_charts.json's `unavailable` tickers. Does NOT imply "
                   "incorporation date is a valid substitute for first-trade date "
                   "(company_charts.json's stated birth-moment convention) — that is a "
                   "separate methodology decision.",
        "source": "https://dps.psx.com.pk/company/<TICKER> — Profile tab, BUSINESS DESCRIPTION",
        "total_checked": len(tickers),
        "counts": counts,
        "results": results,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
