# Frugal Analyst — Site Guide

You are helping the owner of frugalanalyst.com understand how to write, edit, and maintain their automated financial analysis blog. Answer their question using the information below.

---

## Architecture Overview

- **`site/`** — Astro static site deployed to GitHub Pages at frugalanalyst.com
- **`pipeline/`** — Python (uv) pipeline that fetches financial data, generates analysis via Claude API, and outputs Markdown posts + chart PNGs
- **`.github/workflows/`** — GitHub Actions: daily pipeline cron + deploy on merge to main
- **`data/`** — Company universe and analysis tracking log

---

## Writing a Post Manually

1. Create a Markdown file in `site/src/content/blog/` with this naming convention: `YYYY-MM-DD-slug.md`
2. Include this YAML frontmatter at the top:

```yaml
---
title: "Your Post Title"
date: YYYY-MM-DD
ticker: "TICK"
company: "Company Name"
sector: "Sector"
tags: ["tag1", "tag2"]
description: "One-sentence description for the post card and SEO."
keyMetrics:
  - label: "Metric Name"
    value: "Metric Value"
  - label: "Another Metric"
    value: "Another Value"
audio: "/audio/YYYY-MM-DD-slug.mp3"  # optional — adds audio player + podcast feed
---
```

3. Write Markdown body content below the frontmatter
4. For charts/images, place PNGs in `site/public/charts/YYYY-MM-DD/` and reference them as `/charts/YYYY-MM-DD/filename.png`
5. Image captions: put italic text on the line after the image (`*Caption text*`)
6. Tables use standard Markdown table syntax — numeric columns auto-right-align via CSS
7. For audio: place MP3 in `site/public/audio/` and add `audio: "/audio/filename.mp3"` to frontmatter

---

## Editing an Existing Post

- Posts live in `site/src/content/blog/` as `.md` files
- Edit the frontmatter to update metadata (title, tags, description, keyMetrics)
- Edit the body content below the `---` frontmatter separator
- Charts are in `site/public/charts/YYYY-MM-DD/` — replace PNGs to update visuals

---

## Running the Pipeline Locally

```bash
# Full pipeline (auto-selects company)
cd pipeline && uv run python -m frugal_pipeline.main

# Override with a specific ticker
cd pipeline && uv run python -m frugal_pipeline.main --ticker AAPL

# Dry run (generates but doesn't write files)
cd pipeline && uv run python -m frugal_pipeline.main --ticker AAPL --dry-run
```

Required: create a `.env` file in the project root with API keys (see `.env.example`).

---

## Previewing the Site Locally

```bash
cd site && npm run dev
```

Opens at http://localhost:4321. Hot-reloads on file changes.

---

## Building the Site

```bash
cd site && npm run build
```

Output goes to `site/dist/`. Zero JavaScript, pure static HTML/CSS.

---

## Deploying Changes

**Automatic (daily posts):** The GitHub Actions pipeline runs weekdays at 5-6 AM ET, generates a post, and opens a PR tagging @sciortino for review. Merging the PR triggers deployment.

**Manual changes:** Push or merge to `main` with changes in `site/**` → deploy workflow triggers automatically.

---

## Managing the Company Universe

- `data/company_universe.json` — list of companies the pipeline can auto-select from
- `data/analyzed_log.json` — tracks which companies have been covered and when (prevents repeats within 60 days)
- To add a company: add an entry with `ticker`, `cik`, `company`, and `sector` to the JSON array
- To force a specific company: use `--ticker` flag when running the pipeline

---

## Customizing the Site

- **CSS**: `site/src/styles/global.css` — all styling in one file, CSS custom properties for colors
- **Header/Footer**: `site/src/components/Header.astro` and `Footer.astro`
- **Post layout**: `site/src/layouts/PostLayout.astro` — controls how articles render
- **Homepage**: `site/src/pages/index.astro` — shows latest 10 posts
- **About page**: `site/src/pages/about.astro`
- **Tools page**: `site/src/pages/tools.astro` — affiliate/tools-we-use page with FTC disclosure
- **SEO**: `site/src/components/SEO.astro` — Open Graph, Twitter Cards, JSON-LD

---

## Customizing the Pipeline

- **Claude prompt/voice**: `pipeline/src/frugal_pipeline/content/prompt.py`
- **Chart style/types**: `pipeline/src/frugal_pipeline/charts/generator.py`
- **Company selection logic**: `pipeline/src/frugal_pipeline/company_selector.py`
- **Data sources**: `pipeline/src/frugal_pipeline/data_sources/` (sec_edgar.py, fred.py, bls.py)
- **Analysis computations**: `pipeline/src/frugal_pipeline/analysis/`

---

## Google Analytics

GA4 is integrated via a build-time environment variable. The measurement ID is NOT in the source code.

- **Local dev**: set `PUBLIC_GA_MEASUREMENT_ID` in `site/.env` (gitignored)
- **Production**: set as a GitHub Actions secret (`PUBLIC_GA_MEASUREMENT_ID`)
- **Code**: injected in `site/src/layouts/BaseLayout.astro` — only loads if the env var is present
- **Dashboard**: analytics.google.com

---

## GitHub Secrets Required

Add these in **Settings > Secrets > Actions** on the repo:

| Secret | Purpose |
|--------|---------|
| `FRED_API_KEY` | Federal Reserve Economic Data |
| `BLS_API_KEY` | Bureau of Labor Statistics |
| `ANTHROPIC_API_KEY` | Claude API for content generation |
| `SEC_EDGAR_EMAIL` | Email for SEC EDGAR User-Agent header |
| `PUBLIC_GA_MEASUREMENT_ID` | Google Analytics 4 measurement ID |

---

## Troubleshooting

- **Build fails**: Run `cd site && npm run build` locally to see errors. Usually a frontmatter schema mismatch.
- **Missing charts**: Ensure chart PNGs exist at the path referenced in the post. Paths must start with `/charts/`.
- **Pipeline errors**: Check API keys in `.env` and ensure CIK numbers are set in `company_universe.json`.
- **Deploy not triggering**: Deploy only triggers on pushes to `main` that touch `site/**`. Check the Actions tab.
- **Content not showing**: Verify the post's `date` field is a valid date and the frontmatter matches the Zod schema in `site/src/content.config.ts`.

---

## Key Files Quick Reference

| What | Where |
|------|-------|
| Blog posts | `site/src/content/blog/*.md` |
| Chart images | `site/public/charts/YYYY-MM-DD/` |
| CSS styling | `site/src/styles/global.css` |
| Post template | `site/src/layouts/PostLayout.astro` |
| Tools page | `site/src/pages/tools.astro` |
| Content schema | `site/src/content.config.ts` |
| Claude prompt | `pipeline/src/frugal_pipeline/content/prompt.py` |
| Company list | `data/company_universe.json` |
| Analysis log | `data/analyzed_log.json` |
| Daily workflow | `.github/workflows/daily-pipeline.yml` |
| Deploy workflow | `.github/workflows/deploy.yml` |
