// Single source of truth for brand-swappable values.
// Rename the product, change the domain, or edit pricing in ONE place.
export const site = {
  name: 'Henneth AI',
  // Short tagline used in the browser tab and OG cards.
  tagline: 'PSX research, made clear.',
  // One-line description used for meta + JSON-LD.
  description:
    'Henneth AI turns the Pakistan Stock Exchange into plain-English answers — is this company healthy, is the price reasonable, what changed this week. A transparent, rules-based research engine. Research, not advice.',
  // Marketing-site canonical URL. NOT changed in the 2026-07-19 rebrand: henneth.app serves the
  // TERMINAL, so pointing the marketing canonical at it would make both claim the same URL. Set
  // this once the marketing site has its own home (a subdomain, or henneth.app with the app moved
  // to app.henneth.app) — a canonical pointing somewhere that doesn't host this site is worse
  // than a stale one.
  url: 'https://psx-desk.vercel.app',
  // The product app users launch into (the existing terminal).
  appUrl: 'https://henneth.app',
  contactEmail: 'hello@example.com',
  social: {
    x: 'https://x.com/MWasayI',
  },
  // Supabase (waitlist capture). Publishable key is client-safe.
  supabase: {
    url: 'https://qteoncckohuoatbjjykb.supabase.co',
    anonKey: 'sb_publishable_aQu8P4yrAY7l8Y0AcLth5g_Z3VceUnw',
    waitlistTable: 'waitlist',
  },
  // Pricing is displayed only — checkout stays OFF until the legal + track-record
  // gates in docs/LAUNCH-PLAYBOOK.md are cleared.
  pricing: {
    currency: 'PKR',
    tiers: [
      {
        id: 'free',
        name: 'Free',
        priceMonthly: 0,
        blurb: 'The research, open to everyone. Always free.',
        cta: 'Start free',
        featured: false,
      },
      {
        id: 'desk',
        name: 'Desk',
        priceMonthly: 1500,
        priceYearly: 12000,
        blurb: 'For the active investor who wants the full picture.',
        cta: 'Join the waitlist',
        featured: true,
      },
      {
        id: 'pro',
        name: 'Desk Pro',
        priceMonthly: 4000,
        priceYearly: 32000,
        blurb: 'Every strategy, every debate, full depth.',
        cta: 'Join the waitlist',
        featured: false,
      },
    ],
  },
} as const;

export type Site = typeof site;
