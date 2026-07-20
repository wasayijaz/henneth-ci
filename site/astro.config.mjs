// @ts-check
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import mdx from '@astrojs/mdx';
import { site } from './src/site.config.ts';

// `lastmod` for blog posts, read straight from each file's frontmatter at build time.
//
// Only posts get one, and only from a real date they declare. The tempting shortcut — stamping
// every URL with the build time — is worse than emitting nothing: it tells Google the legal pages
// and the about page changed on every deploy, and once a site is caught doing that Google stops
// trusting the field at all. An honest lastmod on the pages that genuinely change is the whole
// value of the field, which is telling a crawler which of a few hundred posts to re-fetch.
function blogLastmods() {
  const dir = fileURLToPath(new URL('./src/content/blog/', import.meta.url));
  /** @type {Record<string, string>} */
  const out = {};
  /** @type {string[]} */
  let files = [];
  try {
    files = fs.readdirSync(dir, { recursive: true }).map(String);
  } catch {
    return out; // no posts yet — the collection directory does not have to exist
  }
  for (const rel of files) {
    if (!/\.mdx?$/.test(rel)) continue;
    const raw = fs.readFileSync(new URL(rel.replace(/\\/g, '/'), new URL('./src/content/blog/', import.meta.url)), 'utf8');
    const fm = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (!fm) continue;
    const body = fm[1];
    if (/^draft:\s*true\s*$/m.test(body)) continue;
    const picked = body.match(/^updatedDate:\s*(.+)$/m) ?? body.match(/^pubDate:\s*(.+)$/m);
    if (!picked) continue;
    const d = new Date(picked[1].trim().replace(/^['"]|['"]$/g, ''));
    if (Number.isNaN(d.valueOf())) continue;
    const slug = rel.replace(/\\/g, '/').replace(/\.mdx?$/, '');
    out[`${site.url}/blog/${slug}/`] = d.toISOString();
  }
  return out;
}

const lastmods = blogLastmods();

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
    sitemap({
      filter: (page) => !page.includes('/legal/'),
      serialize: (item) => {
        const lastmod = lastmods[item.url];
        return lastmod ? { ...item, lastmod } : item;
      },
    }),
  ],
  build: { inlineStylesheets: 'auto' },
  devToolbar: { enabled: false },
});
