// Single source of truth for brand-swappable values.
// Rename the product, change the domain, or edit the plan ladder in ONE place.
//
// NAMING (owner, 2026-07-19): the product is "Henneth" everywhere public — this marketing
// site, the brand, the domain. It is "Henneth Desk" only INSIDE the app/dashboard.
export const site = {
  name: 'Henneth',
  // The in-app product name, used when referring to the terminal itself.
  appName: 'Henneth Desk',
  /* Short tagline used in the browser tab and OG cards. Kept under ~50 characters because
     Base.astro renders "<name> — <tagline>" and search results truncate a title past ~60.

     WIDENED 2026-07-22: the desk now covers 23 US and global index / sector-ETF symbols
     alongside PSX. The accurate description is a global-markets publication that covers PSX in
     depth, not a PSX-only one — and "PSX" stays first because it is both the depth and the
     search term that brings people here. */
  tagline: 'PSX research, global markets, made clear.',
  /* One-line description used for meta + JSON-LD, and the homepage's meta description (index.astro
     passes no `description`, so editing this line edits the homepage's search snippet).
     Kept near 160 characters, which is what Google actually renders — the original 210-character
     version was cut mid-sentence, so the closing "Research, not advice" never appeared at all.

     ON THE ASTROLOGY WORDING: the lens is described as tested and scored, never as predictive.
     state/astro_backtest.json records 2,589 hypotheses and zero survivors after correction, and
     astro_map.json's own discipline says astro "NEVER generates or gates a trade setup". A meta
     description implying it forecasts returns would contradict the desk's published null result
     and CLAUDE.md Rule 5. Astro is no longer named here only because 160 characters will not hold
     it — /financial-astrology owns that query and carries the null result in its own meta. */
  description:
    'Scheduled research on the Pakistan Stock Exchange — company health, fair value, backtested strategies — plus global index context. Research, not advice.',
  // Marketing-site canonical URL — the marketing site owns the root domain.
  url: 'https://henneth.app',
  // The terminal users enter after picking a plan. Moved off the root so marketing can own it.
  appUrl: 'https://desk.henneth.app',
  contactEmail: 'hello@henneth.app',
  social: {
    x: 'https://x.com/MWasayI',
  },
  analytics: {
    // Google Analytics 4 measurement ID. Loaded in production builds only, so
    // local dev traffic never lands in the property.
    ga4: 'G-5PLLEK6RYC',
  },
  // Supabase (waitlist / plan-interest capture). Publishable key is client-safe.
  supabase: {
    url: 'https://qteoncckohuoatbjjykb.supabase.co',
    anonKey: 'sb_publishable_aQu8P4yrAY7l8Y0AcLth5g_Z3VceUnw',
    waitlistTable: 'waitlist',
  },

  // ---------------------------------------------------------------------------
  // THE PLAN LADDER — mirrors `PLANS` / `PLAN_ORDER` in dashboard/app.js.
  // Keep these in sync; app.js is the source of truth for features/entitlement.
  //
  // NO PRICES ON PURPOSE. There is no payment gateway yet (Stripe is unavailable
  // in Pakistan; a local gateway comes later) and `BILLING_LIVE = false` in the
  // app. Plan is also DB-frozen against client writes, so choosing a plan here
  // cannot grant it. Picking a plan records the intent and drops the user into
  // the free desk — we say so plainly rather than faking a checkout.
  // ---------------------------------------------------------------------------
  // EARLY ACCESS SWITCH.
  // While true, /plans shows the free early-access page: no prices, no trial, no
  // checkout — everything open, feedback requested. Flip to false to restore the
  // priced Investor/Pro/Broker page (the tier data below is kept intact for it).
  // Keep this true until the track record has resolved calls, a payment gateway
  // exists, and the legal pages are reviewed.
  earlyAccess: true,

  // Trial length for the PAID page only. The desk must honour this before that
  // page goes live: plan is DB-frozen, so a trial grant needs a service-role path.
  trialDays: 14,
  billing: {
    currency: 'Rs',
    // Annual = 10x monthly, i.e. two months free. Kept as a round multiple so the
    // saving is obvious without a calculator.
    monthsFreeOnAnnual: 2,
  },
  plans: [
    {
      id: 'investor',
      appPlan: 'investor',
      name: 'Investor',
      tag: '',
      priceMonthly: 3000,
      priceAnnual: 30000,
      trial: true,
      blurb:
        'For the investor who wants to read a company for themselves — the guided path, real filings, real prices.',
      cta: 'Start 14-day trial',
      href: null,
      soon: false,
      featured: false,
      features: [
        'Plain-English company reads',
        'The guided investor journey',
        'Practice portfolio (virtual Rs 500k)',
        'Dividends, earnings & calendars',
        'PSX calculators & tools',
      ],
    },
    {
      id: 'pro',
      appPlan: 'pro',
      name: 'Pro',
      tag: 'Most popular',
      priceMonthly: 8000,
      priceAnnual: 80000,
      trial: true,
      blurb:
        'The full desk. Tested strategies, model fair value, the research library, and every lens the desk runs.',
      cta: 'Start 14-day trial',
      href: null,
      soon: false,
      featured: true,
      features: [
        'Everything in Investor',
        'Model fair value, four ways',
        'Run any of the tested strategies',
        'Screener, scanner & scenarios',
        'Ask the desk, alignment & portfolio X-ray',
        'The Desk Room debates in full',
      ],
    },
    {
      id: 'broker',
      appPlan: null,
      name: 'Broker',
      tag: 'Coming soon',
      priceMonthly: null,
      priceAnnual: null,
      trial: false,
      // DELIBERATELY SAYS NOTHING (owner, 2026-07-20).
      // Every prior line here was a promise — public scoring, a leaderboard, team seats — for a
      // tier with no build date and no committed scope. Naming features before they exist sets an
      // expectation the desk would then owe, and quietly dates the page the moment the plan
      // changes shape. The tier stays visible so institutional readers know it is coming; what it
      // contains is a conversation, not a published list.
      // If features are added back, they must be things that already work in the app.
      blurb: 'For desks and institutions. Details on request.',
      cta: 'Coming soon',
      href: null,
      soon: true,
      featured: false,
      features: [],
    },
  ],
} as const;

export type Site = typeof site;
