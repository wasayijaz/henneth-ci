import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// Blog collection — the SEO content engine (phase 2).
// Drop .mdx files into src/content/blog/ and they render automatically.
const blog = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    cluster: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
