"""Single entrypoint for the deterministic desk pipeline (NO agents, no tokens).
Runs every data script in order and rebuilds signals + dashboard. Used by the
update-live-desk skill locally, and mirrors what GitHub Actions runs in the cloud.

Idempotent and safe to re-run. Deep history is skipped for tickers already cached
(fetch_deep_history only pulls missing ones), so re-runs are fast.
Usage: python scripts/run_cloud.py"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STEPS = [
    "update_universe.py", "fetch_history.py", "fetch_deep_history.py",
    # Must run AFTER both history fetches and BEFORE fetch_fundamentals / predictability /
    # backtest: it writes the research gate those three read (psx_data.research_symbols), and
    # the per-symbol trading friction the backtest charges. Out of order, the gate falls back
    # to core-only and the backtest silently reverts to a flat friction assumption.
    "liquidity.py",
    # Needs the history fetches for closes and liquidity.py for the research gate it iterates
    # (psx_data.research_symbols). Earlier than this it would correlate core-only; it has no
    # other dependency and nothing downstream blocks on it. Pure local math, no network.
    "correlation.py",
    "fetch_dividends.py",
    "fetch_dividends_deep.py",  # 18y payout history (Yahoo events) — DPS only gives ~18 months
    "fetch_fundamentals.py", "score_fundamentals.py",
    # Insider/off-market activity — same family as fetch_fundamentals.py (no cadence gate here
    # either; the script itself is cheap/idempotent and degrades to the prior file on failure).
    "fetch_insider_offmarket.py",
    "build_calendar.py", "quant.py", "predictability.py", "backtest.py",
    "snapshot.py",
    "fetch_indices.py",  # append-only KSE100/KMI30 levels — the index history nobody else has
    "fetch_sectors.py",  # PSX code->name map (needs live.json); feeds Rule 4's sector limit + peer P/E
    "fetch_intraday.py", "fetch_global.py", "fetch_georisk.py",
    "astro_engine.py",   # sidereal ephemeris: positions + dated events. Pure math, no network.
    "astro_history.py",  # extends the cached daily sky (bounded per run; ~70ms/day once caught up)
    "astro_charts.py",   # verified birth dates only (Exchange workbooks first, then careful Yahoo)
    "astro_natal.py",    # natal + Vimshottari + transits-to-natal, bracketed for the unknown time
    # Joins today's sky to the backtest's own condition vocabulary, and publishes the Pakistan /
    # KSE-100 slow-graha placements. Must run AFTER astro_engine (current sky) and is checked
    # against astro_backtest.json — a live condition the backtest never tested prints a warning
    # rather than silently becoming an unmeasured claim on the astro page.
    "astro_context.py",
    "astro_claims.py",   # files the astro readings as dated, market-relative, scoreable claims
    "fetch_macro_history.py",  # oil/gold/PKR/S&P/EM/10y/dollar daily history (incremental)
    "sector_macro.py",   # which macro drivers actually move each sector — measured, weekly cadence
    "sector_dossier.py", # deterministic evidence pack the weekly sector debate argues from
    "tv_crosscheck.py", "data_health.py", "compute_fairvalue.py", "build_signals.py",
    # Desk Room deterministic layer (free): compile dossiers, rank the coverage queue,
    # resolve/score any due persona+broker calls. Agents read these; they never fetch.
    "fetch_research.py", "build_explainer.py",  # explainability layer (plain-English "at a glance")
    "room_dossier.py", "room_queue.py", "room_gate.py", "room_score.py",
    "room_verify.py",   # deterministic QA: flags glitch-derived / inconsistent numbers before publish
    "design_lint.py",   # deterministic UI QA: flags rounded corners / padding-contract / raw-hex drift
    # The marketing site's public astro slice. Must run AFTER astro_engine (it reads the current
    # sky) and after build_natal_ephemeris (it slices the Moon column out of that table). Writes
    # only into site/, never state/, so it cannot affect the desk's own data layer.
    "build_astro_lite.py",
    # Diffs universe.json against the last-seen ticker set and auto-appends a templated
    # CHANGELOG.md entry when the universe grew (symbols only — nothing to leak). Must run
    # AFTER update_universe.py and BEFORE build_changelog.py so the new entry gets picked up
    # the same cycle it's written.
    "changelog_tickers.py",
    # Public release notes for the terminal's version badge. Extracts ONLY the `public` blocks
    # from CHANGELOG.md and refuses to build if one contains an internal term — so a bad note
    # fails the step rather than shipping. Cheap, no network.
    "build_changelog.py",
    "build_dashboard.py", "preflight.py",
]
# steps allowed to exit non-zero without aborting the run
ADVISORY = {"tv_crosscheck.py"}


def main():
    failed = []
    for s in STEPS:
        print(f"\n=== {s} ===")
        r = subprocess.run([sys.executable, str(SCRIPTS / s)])
        if r.returncode != 0 and s not in ADVISORY:
            failed.append(s)
            print(f"  ! {s} exited {r.returncode}")
    print("\n" + ("ALL OK" if not failed else f"FAILED: {', '.join(failed)}"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
