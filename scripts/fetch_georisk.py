"""Geopolitical & market-stress radar — the worldmonitor-style capability, built
from the desk's FREE signals instead of worldmonitor's paid API (which gates its
Country Instability Index behind a wm_ key).

Synthesizes the same factor families worldmonitor tracks, scored for their PSX
read-through:
  - Global fear (VIX level + spike)          -> risk-off pressure on frontier flows
  - Energy shock (Brent/WTI 1d + 1mo)        -> Pakistan import bill / PKR / inflation
  - Safe-haven demand (gold move)            -> flight-to-safety signal
  - USD strength (DXY)                       -> EM/frontier currency pressure
  - PKR stress (USD/PKR move)                -> imported inflation, rate-hike risk
  - Conflict/escalation (impact>=4 MACRO news last 10d) -> the shocks that hit PSX hardest

Each -> a 0-100 stress sub-score; weighted into an overall geo-risk score + a plain
read + which PSX sectors it pressures. Deterministic. Writes state/georisk.json.

If the owner later buys a worldmonitor key, wire its true CII for Pakistan here as an
extra factor (set WORLDMONITOR_KEY env)."""
import os
import time
from datetime import date, datetime, timedelta

from psx_data import STATE, load_json, save_json


def clamp(x):
    return max(0, min(100, x))


def main():
    gl = load_json(STATE / "global.json", {"instruments": {}})["instruments"]
    news = load_json(STATE / "newslog.json", [])

    def inst(sym):
        return gl.get(sym, {})

    vix = inst("^VIX")
    brent = inst("BZ=F")
    wti = inst("CL=F")
    gold = inst("GC=F")
    dxy = inst("DX-Y.NYB")
    pkr = inst("PKR=X")

    factors = []

    # 1. global fear — VIX. calm ~13, elevated >20, panic >30
    if vix.get("price") is not None:
        lvl = vix["price"]
        spike = vix.get("chg_1d_pct") or 0
        s = clamp((lvl - 12) / (32 - 12) * 100 + max(0, spike) * 1.5)
        factors.append({"factor": "Global fear (VIX)", "value": f"{lvl:g} ({spike:+.1f}% 1d)",
                        "stress": round(s), "read": "high VIX = global risk-off = foreign outflows from PSX"})

    # 2. energy shock — oil up is bad for Pakistan's import bill (net importer)
    if brent.get("price") is not None:
        d1, d30 = brent.get("chg_1d_pct") or 0, brent.get("chg_1mo_pct") or 0
        s = clamp(50 + d30 * 2 + d1 * 3)  # rising oil raises stress
        factors.append({"factor": "Energy shock (Brent)", "value": f"${brent['price']:g} ({d1:+.1f}% 1d, {d30:+.1f}% 1mo)",
                        "stress": round(s), "read": "rising crude widens the import bill, pressures PKR & inflation; helps E&P/refiners only"})

    # 3. safe-haven demand — gold surging = fear
    if gold.get("price") is not None:
        d1 = gold.get("chg_1d_pct") or 0
        d30 = gold.get("chg_1mo_pct") or 0
        s = clamp(45 + d30 * 2 + max(0, d1) * 3)
        factors.append({"factor": "Safe-haven (Gold)", "value": f"${gold['price']:g} ({d30:+.1f}% 1mo)",
                        "stress": round(s), "read": "gold bid = flight to safety; risk sentiment defensive"})

    # 4. USD strength — strong dollar pressures EM/frontier
    if dxy.get("price") is not None:
        d1 = dxy.get("chg_1d_pct") or 0
        d30 = dxy.get("chg_1mo_pct") or 0
        s = clamp(50 + d30 * 4 + d1 * 4)
        factors.append({"factor": "USD strength (DXY)", "value": f"{dxy['price']:g} ({d30:+.1f}% 1mo)",
                        "stress": round(s), "read": "a strong dollar drains capital from frontier markets and pressures the rupee"})

    # 5. PKR stress — rupee weakness
    if pkr.get("price") is not None:
        d30 = pkr.get("chg_1mo_pct") or 0  # PKR=X up = rupee weaker
        s = clamp(45 + d30 * 6)
        factors.append({"factor": "Rupee stress (USD/PKR)", "value": f"{pkr['price']:g} ({d30:+.1f}% 1mo)",
                        "stress": round(s), "read": "a weakening rupee imports inflation and keeps SBP hawkish — an equity headwind"})

    # 6. conflict/escalation — count impact>=4 MACRO news in last 10 days
    cutoff = (date.today() - timedelta(days=10)).isoformat()
    hot = [n for n in news if (n.get("impact") or 0) >= 4 and (n.get("ts") or "") >= cutoff]
    esc_stress = clamp(len(hot) * 28)
    factors.append({"factor": "Conflict / escalation", "value": f"{len(hot)} high-impact macro shocks (10d)",
                    "stress": round(esc_stress), "read": "geopolitical shocks (oil, conflict, policy) are what hit PSX hardest and fastest",
                    "recent": [{"ts": n["ts"], "headline": n["headline"], "url": n.get("url")} for n in hot[:4]]})

    # weighted composite
    weights = {"Global fear (VIX)": 1.3, "Energy shock (Brent)": 1.4, "Safe-haven (Gold)": 0.7,
               "USD strength (DXY)": 1.0, "Rupee stress (USD/PKR)": 1.3, "Conflict / escalation": 1.5}
    tw = sum(weights.get(f["factor"], 1) for f in factors)
    score = round(sum(f["stress"] * weights.get(f["factor"], 1) for f in factors) / tw) if tw else 50

    band = ("elevated" if score >= 65 else "calm" if score <= 40 else "moderate")
    reads = {
        "elevated": "Risk gauge is elevated — the external backdrop argues for smaller size, defensives, and patience on new longs.",
        "moderate": "Risk gauge is moderate — a mixed external backdrop; normal caution, favour quality.",
        "calm": "Risk gauge is calm — the external backdrop is supportive for taking measured long exposure.",
    }
    # sector pressure tally
    pressured = []
    if brent.get("chg_1mo_pct", 0) and brent["chg_1mo_pct"] > 3:
        pressured.append("OMCs & cement (fuel/energy cost)")
    if brent.get("chg_1mo_pct", 0) and brent["chg_1mo_pct"] > 0:
        pressured.append("E&P benefits (OGDC/PPL/MARI)")
    if pkr.get("chg_1mo_pct", 0) and pkr["chg_1mo_pct"] > 1:
        pressured.append("import-heavy autos & pharma")

    wm_key = os.environ.get("WORLDMONITOR_KEY")
    save_json(STATE / "georisk.json", {
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "score": score, "band": band, "read": reads[band],
        "factors": sorted(factors, key=lambda f: -f["stress"]),
        "sector_pressure": pressured,
        "source": "desk composite from free signals (VIX/oil/gold/DXY/PKR/news)",
        "upgrade_note": None if wm_key else "For true Country Instability Index (Pakistan), add a worldmonitor.app API key as WORLDMONITOR_KEY.",
    })
    print(f"georisk: score {score}/100 ({band}) from {len(factors)} factors, {len(hot)} recent shocks")


if __name__ == "__main__":
    main()
