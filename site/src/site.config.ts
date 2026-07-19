// Single source of truth for brand-swappable values.
// Rename the product, change the domain, or edit the plan ladder in ONE place.
//
// NAMING (owner, 2026-07-19): the product is "Henneth" everywhere public — this marketing
// site, the brand, the domain. It is "Henneth Desk" only INSIDE the app/dashboard.
export const site = {
  name: 'Henneth',
  // The in-app product name, used when referring to the terminal itself.
  appName: 'Henneth Desk',
  // Short tagline used in the browser tab and OG cards.
  tagline: 'PSX research, made clear.',
  // One-line description used for meta + JSON-LD.
  description:
    'Henneth turns the Pakistan Stock Exchange into plain-English answers — is this company healthy, is the price reasonable, what changed this week. A transparent, rules-based research engine. Research, not advice.',
  // Marketing-site canonical URL — the marketing site owns the root domain.
  url: 'https://henneth.app',
  // The terminal users enter after picking a plan. Moved off the root so marketing can own it.
  appUrl: 'https://desk.henneth.app',
  contactEmail: 'hello@henneth.app',
  social: {
    x: 'https://x.com/MWasayI',
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
  plansNote: 'Pricing is announced at launch. Billing isn’t live yet, so everyone starts on the free desk — pick the plan you want and we’ll hold your place.',
  plans: [
    {
      id: 'free',
      name: 'Free',
      tag: '',
      blurb: 'Cast your chart, read the daily desk note, and follow the public track record.',
      cta: 'Enter the desk',
      soon: false,
      featured: false,
      features: [
        'The daily desk note',
        'Universe board & heatmap',
        'Your personal chart',
        'The public track record',
        'News, macro & calendars',
      ],
    },
    {
      id: 'investor',
      name: 'Investor',
      tag: 'start here',
      blurb:
        'Become an investor who reads for themselves. The guided journey from “why invest” to your first practice position — on real PSX filings and real prices.',
      cta: 'Choose Investor',
      soon: false,
      featured: true,
      features: [
        'The guided investor journey',
        'Practice portfolio (virtual PKR 500k)',
        'PSX calculators & tools',
        'Dividends & earnings in full',
        'Your chart, in full',
      ],
    },
    {
      id: 'pro',
      name: 'Pro',
      tag: 'TA & FA',
      blurb:
        'The full desk. Tested strategies, model fair value, the research library, and every lens the desk runs.',
      cta: 'Choose Pro',
      soon: false,
      featured: false,
      features: [
        'Everything in Investor',
        'Model fair value, in full',
        'Run any of the tested strategies',
        'Screener, scanner & scenarios',
        'Ask the desk, alignment & portfolio X-ray',
      ],
    },
    {
      id: 'broker',
      name: 'Broker',
      tag: 'coming soon',
      blurb:
        'Everything in Pro, plus your own desk’s calls scored in public on the same bar as everyone else.',
      cta: 'Coming soon',
      soon: true,
      featured: false,
      features: [
        'Everything in Pro',
        'Your calls scored in public',
        'Your own desk on the leaderboard',
      ],
    },
  ],
} as const;

export type Site = typeof site;
