# Frugal Analyst

Automated daily financial analysis blog at frugalanalyst.com.

## Architecture

- `site/` — Astro static site deployed to GitHub Pages
- `pipeline/` — Python (uv) pipeline that fetches financial data, generates analysis via Claude API, outputs Markdown posts + chart PNGs
- `data/` — Company universe and analysis tracking
- `.github/workflows/` — Daily pipeline cron + deploy on merge

## Key Commands

- `cd site && npm run dev` — Local site preview
- `cd site && npm run build` — Build static site
- `cd pipeline && uv run python -m frugal_pipeline.main` — Run full pipeline
- `cd pipeline && uv run pytest` — Run pipeline tests

## Conventions

- Posts go in `site/src/content/blog/` as Markdown with YAML frontmatter
- Charts go in `site/public/charts/{YYYY-MM-DD}/` as PNGs
- Pipeline uses httpx for HTTP, matplotlib for charts, anthropic SDK for content generation
- All data models use Pydantic
- Claude model: claude-sonnet-4-20250514
