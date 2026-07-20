/* =============================================================================================
   THE CALCULATORS — shared maths for the public tools at /tools/*.

   These formulas are PORTED FROM `dashboard/app.js` (the TOOLS section) and must stay identical
   to it. A visitor who runs the public compound calculator and then the same one inside the desk
   has to get the same number, or the desk looks broken in the one place a stranger can check it
   for free. If a formula changes on one side, change it on the other in the same commit.

   Everything here is a PURE function of the visitor's own inputs. Nothing forecasts, nothing
   advises (CLAUDE.md Rule 5), and no rate is invented — any real-world anchor (CPI, policy rate,
   gold) is passed IN from the data layer at build time by the page, never typed from memory
   (Rule 2).
   ============================================================================================= */

export type Tile = { k: string; v: string; sub?: string; cls?: '' | 'up' | 'dn' };
export type Result = { tiles: Tile[]; note?: string; noteWarn?: boolean; bars?: BarSeries };
export type BarSeries = { yearly: number[]; lump: number; monthly: number };

// ---------------------------------------------------------------------------- formatting
const nf = new Intl.NumberFormat('en-PK');
export const fmt = (n: number) => nf.format(Math.round(n));
export const rs = (n: number) => 'Rs ' + fmt(n);
const pct = (n: number, d = 1) => n.toFixed(d) + '%';

// ---------------------------------------------------------------------------- core maths
/** Future value of a lump sum plus monthly contributions, compounded monthly. */
export function fvSeries(lump: number, monthly: number, years: number, annualRate: number) {
  const mr = Math.pow(1 + annualRate, 1 / 12) - 1;
  const n = Math.round(years * 12);
  let v = lump;
  const yearly: number[] = [];
  for (let i = 1; i <= n; i++) {
    v = v * (1 + mr) + monthly;
    if (i % 12 === 0) yearly.push(v);
  }
  return { end: v, contributed: lump + monthly * n, yearly };
}

// ---------------------------------------------------------------------------- calculators
export type CalcFn = (v: Record<string, number>, anchors: Anchors) => Result;
export type Anchors = {
  cpi?: number | null;
  policy?: number | null;
  tbill?: number | null;
  goldPkrPerGram?: number | null;
  goldUsdOz?: number | null;
  usdpkr?: number | null;
  goldDate?: string | null;
};

const compound: CalcFn = (v) => {
  const { lump, years, rate: r, infl: i } = v;
  const rate = r / 100, infl = i / 100;
  const out = fvSeries(lump, 0, years, rate);
  const real = out.end / Math.pow(1 + infl, years);
  const beats = rate > infl;
  return {
    tiles: [
      { k: 'Ending value', v: rs(out.end), sub: `after ${years} years`, cls: 'up' },
      { k: 'You put in', v: rs(out.contributed), sub: 'one lump sum' },
      { k: 'Growth', v: rs(out.end - out.contributed), sub: `at ${pct(rate * 100)}/yr`, cls: out.end >= out.contributed ? 'up' : 'dn' },
      { k: "In today's rupees", v: rs(real), sub: `after ${pct(infl * 100)} inflation`, cls: real >= lump ? 'up' : 'dn' },
    ],
    bars: { yearly: out.yearly, lump, monthly: 0 },
    noteWarn: !beats,
    note: beats
      ? `At ${pct(rate * 100)} against ${pct(infl * 100)} inflation, this money grows in <b>real</b> terms — the "today's rupees" tile is the honest one, and it is what your savings would actually buy.`
      : `<b>This loses purchasing power.</b> ${pct(rate * 100)} against ${pct(infl * 100)} inflation means the ending amount buys <b>less</b> than what you put in. Beating inflation is the first job, not the last.`,
  };
};

const sip: CalcFn = (v) => {
  const { monthly, lump, years, rate: r, infl: i } = v;
  const rate = r / 100, infl = i / 100;
  const out = fvSeries(lump, monthly, years, rate);
  const real = out.end / Math.pow(1 + infl, years);
  return {
    tiles: [
      { k: 'Ending value', v: rs(out.end), sub: `${years} yrs × Rs ${fmt(monthly)}/mo`, cls: 'up' },
      { k: 'You put in', v: rs(out.contributed), sub: `${Math.round(years * 12)} contributions` },
      { k: 'Growth', v: rs(out.end - out.contributed), sub: `at ${pct(rate * 100)}/yr`, cls: 'up' },
      { k: "In today's rupees", v: rs(real), sub: `after ${pct(infl * 100)} inflation` },
    ],
    bars: { yearly: out.yearly, lump, monthly },
    note: `Saving a fixed amount every month buys more shares when prices are low and fewer when high — which is the whole argument for regularity over timing. Note how much of the ending value is <b>your own contributions</b> in the early years: compounding only becomes the bigger half late, which is why starting early beats starting big.`,
  };
};

const inflation: CalcFn = (v, a) => {
  const { amount, years, rate: r } = v;
  const infl = r / 100;
  const future = amount * Math.pow(1 + infl, years);
  const worth = amount / Math.pow(1 + infl, years);
  const lost = 100 - (worth / amount) * 100;
  return {
    tiles: [
      { k: `Rs ${fmt(amount)} today`, v: rs(worth), sub: `will buy this much in ${years} yrs`, cls: 'dn' },
      { k: "To match it you'd need", v: rs(future), sub: `in ${years} years` },
      { k: 'Purchasing power lost', v: pct(lost), sub: `at ${pct(infl * 100)}/yr`, cls: 'dn' },
    ],
    noteWarn: true,
    note:
      `This is the case for investing in one number. Cash left idle at ${pct(infl * 100)} inflation loses about <b>${lost.toFixed(0)}%</b> of its purchasing power over ${years} years — a certainty, not a risk.` +
      (a.cpi != null
        ? ` Pakistan's latest reported CPI is <b>${a.cpi}%</b>` +
          (a.tbill != null ? `, and 6-month T-bills yield about <b>${a.tbill}%</b> — the near-riskless bar any investment should be judged against` : '') +
          '.'
        : ''),
  };
};

const goal: CalcFn = (v) => {
  const { target, years, rate: r, infl: i, have } = v;
  const rate = r / 100, infl = i / 100;
  const targetReal = target * Math.pow(1 + infl, years);
  const mr = Math.pow(1 + rate, 1 / 12) - 1;
  const n = Math.round(years * 12);
  const grownHave = have * Math.pow(1 + mr, n);
  const need = Math.max(0, targetReal - grownHave);
  const monthly = mr === 0 ? need / n : (need * mr) / (Math.pow(1 + mr, n) - 1);
  return {
    tiles: [
      { k: "Goal in today's money", v: rs(target), sub: `${years} years away` },
      { k: "What it'll actually cost", v: rs(targetReal), sub: `at ${pct(infl * 100)} inflation`, cls: 'dn' },
      { k: 'Your savings will grow to', v: rs(grownHave), sub: `from ${rs(have)} today`, cls: 'up' },
      { k: 'Save per month', v: rs(monthly), sub: `for ${n} months at ${pct(rate * 100)}`, cls: 'up' },
    ],
    note: `The tile most goal calculators hide is the second one: a goal priced in <b>today's</b> rupees costs materially more by the time you reach it. Plan against ${rs(targetReal)}, not ${rs(target)}. If the monthly figure looks impossible, the honest levers are a longer horizon or a smaller goal — not a higher assumed return.`,
  };
};

const mortgage: CalcFn = (v, a) => {
  const { price, down, years, rate: r } = v;
  const rate = r / 100;
  const principal = Math.max(0, price - down);
  const mr = rate / 12;
  const n = Math.round(years * 12);
  const pay = mr === 0 ? principal / n : (principal * mr) / (1 - Math.pow(1 + mr, -n));
  const total = pay * n;
  const interest = total - principal;
  return {
    tiles: [
      { k: 'Monthly instalment', v: rs(pay), sub: `${years} yrs at ${pct(rate * 100, 2)}` },
      { k: 'You borrow', v: rs(principal), sub: `${rs(down)} down on ${rs(price)}` },
      { k: 'Total interest', v: rs(interest), sub: `over ${n} payments`, cls: 'dn' },
      { k: 'Total repaid', v: rs(total), sub: interest > principal ? 'more than double the loan' : 'principal + interest', cls: 'dn' },
    ],
    noteWarn: true,
    note:
      `Over ${years} years you repay <b>${rs(total)}</b> on a <b>${rs(principal)}</b> loan — interest alone is <b>${rs(interest)}</b>, ${((interest / principal) * 100).toFixed(0)}% of what you borrowed. ` +
      `Pakistani home finance is usually priced at <b>KIBOR + a bank spread</b> and re-prices as rates move, so a fixed illustration understates the risk of a rising-rate year.` +
      (a.policy != null
        ? ` The SBP policy rate is currently <b>${a.policy}%</b>` + (a.tbill != null ? ` and 6M T-bills yield <b>${a.tbill}%</b>` : '') + ` — home finance typically sits above these, not at them.`
        : '') +
      ` Enter the rate your bank actually quotes.`,
  };
};

const zakat: CalcFn = (v, a) => {
  const { shares, cash, owed } = v;
  const net = Math.max(0, shares + cash - owed);
  const nisabGold = a.goldPkrPerGram != null ? a.goldPkrPerGram * 87.48 : null;
  const above = nisabGold != null ? net >= nisabGold : null;
  const tiles: Tile[] = [
    { k: 'Zakatable total', v: rs(net), sub: 'shares + cash − debts due' },
    { k: 'Zakat at 2.5%', v: rs(net * 0.025), sub: above === false ? 'only if above nisab' : 'payable if held a lunar year', cls: 'up' },
    { k: 'Gold nisab (87.48g)', v: nisabGold != null ? rs(nisabGold) : '—', sub: a.goldUsdOz ? `gold $${a.goldUsdOz}/oz · USD/PKR ${a.usdpkr}` : 'gold price unavailable' },
  ];
  let note = '';
  if (nisabGold != null) {
    note = above
      ? `Your ${rs(net)} is <b>above</b> the gold nisab of ${rs(nisabGold)}, so zakat would be due if the wealth has been held for a lunar year. `
      : `Your ${rs(net)} is <b>below</b> the gold nisab of ${rs(nisabGold)}. Note that the <b>silver</b> nisab (612.36g) is considerably lower and is what many scholars apply — the desk does not hold a silver price, so check the current silver rate before concluding zakat is not due. `;
  }
  note += `<b>This is a calculator, not a fatwa.</b> Scholars differ on real questions here — whether shares held long-term are zakatable at full market value or only on the company's zakatable assets, and whether the gold or silver nisab applies. Confirm with your own scholar or zakat authority.`;
  return { tiles, note, noteWarn: above === false };
};

export const CALCS: Record<string, CalcFn> = { compound, sip, inflation, goal, mortgage, zakat };

// ---------------------------------------------------------------------------- DOM wiring
/**
 * Binds every `[data-calc]` block on the page: reads its `[data-field]` inputs, runs the named
 * calculator, and paints tiles + note. Recalculates on input, so there is no "Calculate" button
 * to forget to press — a calculator that shows a stale number after you change an input is the
 * most common defect in the ones already ranking.
 */
export function mountCalculators(anchors: Anchors) {
  document.querySelectorAll<HTMLElement>('[data-calc]').forEach((root) => {
    const fn = CALCS[root.dataset.calc || ''];
    if (!fn) return;
    const inputs = Array.from(root.querySelectorAll<HTMLInputElement>('[data-field]'));
    const out = root.querySelector<HTMLElement>('[data-out]');
    if (!out) return;

    const run = () => {
      const v: Record<string, number> = {};
      for (const el of inputs) v[el.dataset.field!] = Number(el.value) || 0;
      const r = fn(v, anchors);
      const tiles = r.tiles
        .map((t) => `<div class="sumtile"><span class="sk">${t.k}</span><b class="${t.cls || ''}">${t.v}</b>${t.sub ? `<i>${t.sub}</i>` : ''}</div>`)
        .join('');
      const bars = r.bars ? renderBars(r.bars) : '';
      out.innerHTML =
        `<div class="sumstrip s${r.tiles.length}">${tiles}</div>${bars}` +
        (r.note ? `<div class="tnote${r.noteWarn ? ' warn' : ''}">${r.note}</div>` : '');
    };

    inputs.forEach((el) => el.addEventListener('input', run));
    run();

    // One event per calculator, fired once per visit rather than on every keystroke — otherwise a
    // visitor dragging a number would generate dozens of identical events and the engagement
    // signal would be meaningless.
    let sent = false;
    inputs.forEach((el) =>
      el.addEventListener('change', () => {
        if (sent) return;
        sent = true;
        (window as any).hTrack?.('calculator_use', { calculator: root.dataset.calc });
      })
    );
  });
}

function renderBars(b: BarSeries) {
  if (!b.yearly.length) return '';
  const max = b.yearly[b.yearly.length - 1] || 1;
  const bars = b.yearly
    .map((v, i) => {
      const put = b.lump + b.monthly * 12 * (i + 1);
      const h = Math.max(2, (v / max) * 100);
      const ph = Math.max(1, Math.min(h, (put / max) * 100));
      return `<div class="tbar" title="Year ${i + 1}: ${rs(v)} (you put in ${rs(put)})"><span class="tb-grow" style="height:${h}%"></span><span class="tb-put" style="height:${ph}%"></span><i>${i + 1}</i></div>`;
    })
    .join('');
  return `<div class="tbars">${bars}</div><div class="tlegend"><span><span class="sw put"></span>what you put in</span><span><span class="sw grow"></span>total value</span></div>`;
}
