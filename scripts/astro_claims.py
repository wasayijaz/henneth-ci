"""Put the astro readings on the record, so they can be wrong in public.

The owner's framing decision: the astro lens presents the TRADITION'S reading, and that reading is
scored like a broker call. This file is what makes that true rather than a slogan. Without it the
astro board would make claims that nothing ever grades — which is the definition of a horoscope.

WHAT BECOMES A CLAIM
Only statements the tradition makes SHARPLY enough to be wrong:
  * Sade Sati       — tradition's heaviest weather. Claim: this name underperforms the market over
                      the passage. Resolves on the phase's own horizon.
  * Dhaiya          — the lesser Saturn affliction. Same shape.
  * Jupiter benefic — Jupiter in a classically benefic house from the natal Moon: outperformance.
Each is directional, dated, market-relative, and resolvable from prices alone. Vague readings
("a period of change") are deliberately NOT written: if it cannot fail, it does not go on the board.

WHAT MAKES THIS HONEST RATHER THAN CYNICAL
  * Claims are stated BEFORE the outcome, with resolve_by in the future.
  * They are market-RELATIVE, so a rising tide cannot score them for free.
  * The desk's own tests say these claims are unsupported (astro_natal_test.json) — and we file them
    anyway, because the tests are weakly powered on young charts, and the fair way to settle it is
    in public on dated calls rather than by assertion in either direction.
  * source_type "astro" keeps them separable on the leaderboard: nobody's broker record gets muddied
    by the desk's astrology, and astro's record cannot hide inside the desk's.

Idempotent: a claim id is a hash of (subject, condition, window start), so re-running never
duplicates. Appends to state/claims.json — the same ledger room_score.py already resolves.
"""
import datetime as dt
import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
PKT = dt.timezone(dt.timedelta(hours=5))


def load(p, d=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def cid(*parts):
    return "claim:as:" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def main():
    natal = load(STATE / "astro_natal.json")
    if not natal:
        print("astro_claims: no astro_natal.json — nothing to file")
        sys.exit(0)
    led = load(STATE / "claims.json", {"claims": []})
    claims = led.get("claims", [])
    have = {c.get("id") for c in claims}
    quant = (load(STATE / "quant.json", {}) or {}).get("tickers", {})
    sect = (load(STATE / "sectors.json", {}) or {}).get("tickers", {})
    # every claim here is market-RELATIVE, so the benchmark level must be stamped at claim time or
    # the claim can never be graded honestly (room_score leaves it pending rather than guess)
    bench = ((load(STATE / "indices.json", {}) or {}).get("live") or {}).get("KSE100")
    if not bench:
        print("astro_claims: no KSE100 level (run scripts/fetch_indices.py) — refusing to file "
              "market-relative claims that could never be scored")
        sys.exit(0)
    today = dt.datetime.now(PKT).date()
    added = []

    for sym, rec in (natal.get("subjects") or {}).items():
        if rec.get("kind") != "stock":
            continue
        px = (quant.get(sym) or {}).get("close")
        if not px:
            continue
        moon = (rec.get("natal") or {}).get("Moon", {}).get("sign")
        ss = rec.get("sade_sati") or {}
        base = {
            "source_type": "astro", "source": "Vedic (Lahiri) natal reading",
            "sector": (sect.get(sym) or {}).get("sector") or "unknown",
            "ticker": sym, "made_on": today.isoformat(), "made_at_price": px,
            "benchmark": {"name": "KSE100", "level": bench},
            "status": "pending",
            "basis": f"natal Moon {moon}; chart cast for the first trade {rec.get('birth', {}).get('date')} "
                     f"at the Karachi open (Meridian convention). Sidereal, Lahiri.",
            "desk_note": ("Filed BECAUSE the desk's own tests do not support it. The transit rules "
                          "showed no edge over 19 years and the natal methods are not demonstrated "
                          "either — but the natal tests are weakly powered on charts this young, so "
                          "the desk settles it in public on dated calls instead of by assertion."),
        }

        # 1. Sade Sati — the tradition's heaviest claim, so the first one to put at risk
        if ss.get("active"):
            phase = (ss.get("phase") or "").split(" (")[0]
            horizon = 180
            k = cid(sym, "sade_sati", phase, today.isoformat()[:7])
            if k not in have:
                added.append({**base, "id": k, "kind": "direction", "horizon_days": horizon,
                              "resolve_by": (today + dt.timedelta(days=horizon)).isoformat(),
                              "claim": {
                                  "direction": "down",
                                  "text": f"{sym} underperforms the KSE100 over the next {horizon} days: "
                                          f"tradition says Sade Sati ({phase}) is the heaviest passage a "
                                          f"chart runs, and Saturn is on {sym}'s natal Moon neighbourhood now.",
                                  "market_relative": True,
                                  "condition": f"Sade Sati — {phase}",
                              }})

        # 2. Dhaiya — the lesser Saturn affliction
        if (ss.get("phase") or "").startswith("Dhaiya"):
            horizon = 180
            k = cid(sym, "dhaiya", today.isoformat()[:7])
            if k not in have:
                added.append({**base, "id": k, "kind": "direction", "horizon_days": horizon,
                              "resolve_by": (today + dt.timedelta(days=horizon)).isoformat(),
                              "claim": {
                                  "direction": "down",
                                  "text": f"{sym} underperforms the KSE100 over the next {horizon} days: "
                                          f"tradition reads Saturn's Dhaiya from the natal Moon as a drag.",
                                  "market_relative": True, "condition": "Dhaiya",
                              }})

        # 3. Jupiter in a benefic house from the natal Moon — the positive side of the ledger,
        #    because a lens that only ever predicts trouble is unfalsifiable in practice
        nat_moon_lon = (rec.get("natal") or {}).get("Moon", {}).get("lon")
        jup = (load(STATE / "astro.json", {}) or {}).get("positions", {}).get("Jupiter", {})
        if nat_moon_lon is not None and jup.get("lon") is not None:
            rel = (int(jup["lon"] // 30) - int(nat_moon_lon // 30)) % 12
            if rel in (1, 4, 6, 8, 10):
                horizon = 120
                k = cid(sym, "jupiter_benefic", rel, today.isoformat()[:7])
                if k not in have:
                    added.append({**base, "id": k, "kind": "direction", "horizon_days": horizon,
                                  "resolve_by": (today + dt.timedelta(days=horizon)).isoformat(),
                                  "claim": {
                                      "direction": "up",
                                      "text": f"{sym} outperforms the KSE100 over the next {horizon} days: "
                                              f"Jupiter transits the {ordinal(rel + 1)} from its natal Moon, "
                                              f"which tradition counts among the benefic houses.",
                                      "market_relative": True,
                                      "condition": f"Jupiter in the {ordinal(rel + 1)} from natal Moon",
                                  }})

    if not added:
        print("astro_claims: nothing new to file (all current readings already on the record)")
        sys.exit(0)

    claims.extend(added)
    led["claims"] = claims
    led["updated"] = time.strftime("%Y-%m-%d %H:%M")
    (STATE / "claims.json").write_text(json.dumps(led, indent=1), encoding="utf-8")
    print(f"astro_claims: filed {len(added)} dated astro claims (now {len(claims)} on the ledger)")
    for c in added:
        print(f"   {c['ticker']:9} {c['claim']['condition'][:34]:34} -> {c['claim']['direction']:4} "
              f"by {c['resolve_by']}")


if __name__ == "__main__":
    main()
