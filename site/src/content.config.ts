import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

/* The canonical cluster list — the single source of truth for the blog taxonomy.
   Imported by the blog index (filter chips) and the post template (icon map), so the three can
   never drift apart.

   Clusters are how the blog ranks: a pillar page plus spokes, linked to each other, reads to
   Google as depth on one topic rather than scattered posts. See docs/BLOG_PLAN.md. */
export const CLUSTERS = [
  'Market structure',
  'Method',
  'Valuation',
  'Sectors',
  'Macro',
  'Astro',
] as const;

export type Cluster = (typeof CLUSTERS)[number];

const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    // An ENUM, deliberately, not a free string. As `z.string()` a typo like "Market Structure"
    // was accepted silently: the post rendered with the fallback icon and was unreachable from
    // every filter chip, so it existed but nobody could navigate to it. Now a bad value fails the
    // build, which is the only moment anyone is looking.
    cluster: z.enum(CLUSTERS).optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
