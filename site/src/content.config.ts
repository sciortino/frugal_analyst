import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const blog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    ticker: z.string(),
    company: z.string(),
    sector: z.string(),
    tags: z.array(z.string()),
    description: z.string(),
    keyMetrics: z.array(
      z.object({
        label: z.string(),
        value: z.string(),
      })
    ).optional().default([]),
    audio: z.string().optional(),
  }),
});

export const collections = { blog };
