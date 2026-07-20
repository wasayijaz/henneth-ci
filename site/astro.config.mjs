// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import mdx from '@astrojs/mdx';
import { site } from './src/site.config.ts';

// Static output — served on Vercel with zero server runtime.
// The waitlist form posts client-side to Supabase (RLS insert-only), so no
// serverless adapter is needed for phase 1.
export default defineConfig({
  site: site.url,
  integrations: [
    mdx(),
    // The legal pages carry <meta robots="noindex"> while they are unreviewed
    // drafts, so they must not be submitted in the sitemap — Search Console
    // reports that pairing as "Submitted URL marked noindex". Drop the filter
    // once a lawyer has signed them off and the noindex comes off.
    sitemap({ filter: (page) => !page.includes('/legal/') }),
  ],
  build: { inlineStylesheets: 'auto' },
  devToolbar: { enabled: false },
});
