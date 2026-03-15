# The Frugal Analyst

Automated daily financial analysis blog at [frugalanalyst.com](https://frugalanalyst.com). Each day, the pipeline selects a public company, pulls financial data from SEC filings and government sources, generates a data-driven analysis through a labor economics lens using Claude, and opens a PR for review.

Weekend editions are op-ed style — using a company's data as a launching point for broader arguments about the economy, labor, and corporate America.

## Architecture

```
frugal_analyst/
├── site/                  # Astro static site → GitHub Pages
│   ├── src/
│   │   ├── content/blog/  # Markdown posts with YAML frontmatter
│   │   ├── pages/         # Home, archive, tools, about, 404
│   │   ├── layouts/       # Base + post layouts
│   │   ├── components/    # Header, footer, SEO, audio player, disclaimer
│   │   └── styles/        # Single global.css with CSS custom properties
│   └── public/
│       ├── charts/        # Generated chart PNGs (by date)
│       └── audio/         # Podcast MP3s (manually recorded)
├── pipeline/              # Python (uv) data pipeline
│   └── src/frugal_pipeline/
│       ├── data_sources/  # SEC EDGAR, FRED, BLS clients
│       ├── analysis/      # Financial metrics, labor lens, validation
│       ├── charts/        # Matplotlib chart generation
│       ├── content/       # Claude prompts + content generation
│       └── output/        # File writing + log updates
├── data/
│   ├── company_universe.json   # Companies the pipeline can select
│   └── analyzed_log.json       # Tracks what's been covered (60-day cooldown)
└── .github/workflows/
    ├── daily-pipeline.yml      # Runs every day at 5-6 AM ET
    └── deploy.yml              # Deploys site on merge to main
```

## Data Sources

All analysis is grounded in public, authoritative data:

- **[SEC EDGAR](https://www.sec.gov/edgar)** — Corporate financial statements via XBRL (revenue, income, SGA, employee counts)
- **[FRED](https://fred.stlouisfed.org)** — Federal Reserve economic data (unemployment, wages, sector employment)
- **[BLS](https://www.bls.gov)** — Bureau of Labor Statistics (employment, hourly earnings, labor market data)
- **[Anthropic Claude](https://www.anthropic.com)** — AI content generation from structured data

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- API keys (see [Secrets](#github-secrets) below)

### Local Development

```bash
# Preview the site
cd site && npm run dev          # http://localhost:4321

# Build the site
cd site && npm run build

# Run the pipeline (needs .env with API keys)
cd pipeline && uv run python -m frugal_pipeline.main

# Run for a specific company
cd pipeline && uv run python -m frugal_pipeline.main --ticker MSFT

# Dry run (preview without writing files)
cd pipeline && uv run python -m frugal_pipeline.main --ticker MSFT --dry-run

# Weekend op-ed mode
cd pipeline && uv run python -m frugal_pipeline.main --weekend
```

## Daily Workflow

1. **Pipeline runs** at 5-6 AM ET via GitHub Actions (every day, including weekends)
2. **Company selected** via sector rotation (or events queue / CLI override)
3. **Data fetched** from SEC EDGAR, FRED, and BLS
4. **Analysis generated** by Claude with the weekday or weekend prompt
5. **PR opened** with the post, charts, and updated analysis log
6. **Review & publish** — review the PR, tighten prose if needed, merge to deploy

Weekend runs (Saturday/Sunday) automatically use the op-ed prompt, which produces an essayistic piece using the company's data to make a broader argument.

## Publishing a Post

Use the `/publish-post` slash command in Claude Code to walk through the full review and publish process, or do it manually:

1. Review the open PR on GitHub
2. Check for data accuracy (no hallucinated numbers, correct year references)
3. Tighten prose (~20% — Claude tends to overwrite)
4. Optionally record audio and add to the post (see [Podcast](#podcast) below)
5. Merge the PR — deploy triggers automatically

## Podcast

Posts can include audio narration that appears as an embedded player on the post page and in a podcast RSS feed.

### Recording a New Episode

1. Read the post aloud and record (Voice Memos, GarageBand, or any recorder)
2. Export as MP3
3. Save to `site/public/audio/YYYY-MM-DD-slug.mp3`
4. Add to the post frontmatter:
   ```yaml
   audio: "/audio/YYYY-MM-DD-slug.mp3"
   ```
5. Commit and push (or add to the PR before merging)

### Podcast Feed

The feed is at `frugalanalyst.com/podcast.xml`. Submit this URL to:
- [Apple Podcasts Connect](https://podcastsconnect.apple.com)
- [Spotify for Podcasters](https://podcasters.spotify.com)

Only posts with the `audio` frontmatter field appear in the podcast feed.

## Post Frontmatter

```yaml
---
title: "Post Title"
date: 2026-03-15
ticker: "AAPL"
company: "Apple Inc."
sector: "Technology"
tags: ["technology", "aapl", "labor-economics"]
description: "One-sentence description for SEO and post cards."
keyMetrics:                    # optional (weekday posts include these)
  - label: "Revenue/Employee"
    value: "$2.43M"
audio: "/audio/2026-03-15-aapl-op-ed.mp3"   # optional
---
```

## Feeds

| Feed | URL | Purpose |
|------|-----|---------|
| Blog RSS | `/rss.xml` | All posts |
| Podcast | `/podcast.xml` | Posts with audio (iTunes-compatible) |

## GitHub Secrets

Add in **Settings > Secrets and variables > Actions**:

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | Claude API for content generation |
| `FRED_API_KEY` | Federal Reserve Economic Data |
| `BLS_API_KEY` | Bureau of Labor Statistics |
| `SEC_EDGAR_EMAIL` | Email for SEC EDGAR User-Agent header |
| `PUBLIC_GA_MEASUREMENT_ID` | Google Analytics 4 (optional) |

## Site Pages

| Page | Path | Description |
|------|------|-------------|
| Home | `/` | Latest 10 posts |
| Archive | `/blog/` | All posts by month |
| Tools | `/tools/` | Tools we use (with affiliate disclosure) |
| About | `/about/` | Methodology, data sources, mission |
| 404 | `/404` | Custom not-found page |

## License

Content is published as a free public resource. All analysis is for informational purposes only and does not constitute financial advice.
