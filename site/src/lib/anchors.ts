import fs from 'node:fs';
import path from 'node:path';

/* =============================================================================================
   REAL PAKISTANI FIGURES FOR THE CALCULATORS, READ FROM state/ AT BUILD TIME.

   Same contract as the hero board in index.astro: the marketing site builds from the same repo as
   the desk, so a calculator can anchor its defaults to the SBP policy rate and the latest reported
   CPI instead of a number someone typed from memory (CLAUDE.md Rule 2).

   This matters more here than on the hero. A calculator that quietly defaults to "8% inflation"
   in a year Pakistan printed 11.1% produces answers that are wrong in the direction that flatters
   the product, and every visitor who accepts the default gets a misleading result.

   Every read degrades to null, never throws — a standalone site checkout has no state/ at all,
   and a missing figure must soften the page (the anchor chip disappears, the calculator still
   works on the visitor's own inputs) rather than fail the build.
   ============================================================================================= */

const STATE = path.resolve(process.cwd(), '..', 'state');

function readState<T>(file: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(path.join(STATE, file), 'utf-8')) as T;
  } catch {
    return fallback;
  }
}

export type Anchors = {
  cpi: number | null;
  policy: number | null;
  tbill: number | null;
  /** Date the macro layer was last refreshed, so the page can stamp what it is quoting. */
  updated: string | null;
};

export function getAnchors(): Anchors {
  const m = readState<any>('macro.json', {});
  const num = (x: unknown) => (typeof x === 'number' && Number.isFinite(x) ? x : null);
  return {
    cpi: num(m.cpi_yoy),
    policy: num(m.sbp_rate),
    tbill: num(m.domestic?.tbill_6m),
    updated: typeof m.updated === 'string' ? m.updated.slice(0, 10) : null,
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
