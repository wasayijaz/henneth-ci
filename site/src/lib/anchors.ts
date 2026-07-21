import ctx from '../data/public/context.json';

/* =============================================================================================
   REAL PAKISTANI FIGURES FOR THE CALCULATORS.

   A calculator anchors its defaults to the SBP policy rate and the latest reported CPI rather
   than a number someone typed from memory (CLAUDE.md Rule 2). One that quietly defaults to
   "8% inflation" in a year Pakistan printed 11.1% produces answers wrong in the direction that
   flatters the product, and every visitor who accepts the default gets a misleading result.

   READS THE COMMITTED PUBLIC EXTRACT, NOT `../state/`  (changed 2026-07-21)
   This used to `fs.readFileSync` its way up into `../state/macro.json`, which is why Vercel's
   "Include source files outside the Root Directory" had to be switched on for the marketing
   project — putting the entire 93 MB data layer inside the marketing build, one careless route
   away from being served. `scripts/build_public_slice.py` now writes a narrow, allow-listed
   `context.json` into `site/`, so the Astro build reads nothing above its own root and that
   setting can stay off.

   Regenerate with `python scripts/build_public_slice.py` whenever the macro layer moves; the file
   is committed so the build is hermetic and reproducible.

   Still degrades to null rather than throwing: a missing figure must soften the page (the anchor
   chip disappears, the calculator still works on the visitor's own inputs), never fail the build.
   ============================================================================================= */

export type Anchors = {
  cpi: number | null;
  policy: number | null;
  tbill: number | null;
  /** Date the macro layer was last refreshed, so the page can stamp what it is quoting. */
  updated: string | null;
};

export function getAnchors(): Anchors {
  // The extract has already flattened `domestic.tbill_6m` and trimmed `updated` to a date, so the
  // shape here is deliberately simpler than macro.json's.
  const m: any = (ctx as any)?.macro ?? {};
  const num = (x: unknown) => (typeof x === 'number' && Number.isFinite(x) ? x : null);
  return {
    cpi: num(m.cpi_yoy),
    policy: num(m.sbp_rate),
    tbill: num(m.tbill_6m),
    updated: typeof m.updated === 'string' ? m.updated : null,
  };
}

/**
 * A default the visitor can override, anchored to a real figure when the data layer has one.
 * Rounded to one decimal because an input pre-filled with 11.4375 reads as false precision on a
 * planning assumption — the underlying figure stays exact wherever it is actually quoted.
 */
export function anchoredDefault(value: number | null, fallback: number) {
  return value == null ? fallback : Math.round(value * 10) / 10;
}
