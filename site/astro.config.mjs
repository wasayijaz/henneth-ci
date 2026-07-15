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
  integrations: [mdx(), sitemap()],
  build: { inlineStylesheets: 'auto' },
  devToolbar: { enabled: false },
});
