"""Output file writing utilities."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


def write_post(content: str, filename: str, blog_dir: str | Path) -> Path:
    """Write a Markdown blog post to the site content directory.

    Args:
        content: Complete Markdown content with frontmatter.
        filename: Post filename (e.g., '2026-03-14-aapl-analysis.md').
        blog_dir: Path to site/src/content/blog/ directory.

    Returns:
        Path to the written file.
    """
    blog_path = Path(blog_dir)
    blog_path.mkdir(parents=True, exist_ok=True)

    filepath = blog_path / filename
    filepath.write_text(content, encoding="utf-8")
    logger.info("Wrote blog post: %s", filepath)
    return filepath


def update_analyzed_log(
    ticker: str,
    company: str,
    analysis_date: date,
    data_dir: str | Path,
) -> None:
    """Update the analyzed_log.json with a new analysis entry.

    Args:
        ticker: Stock ticker analyzed.
        company: Full company name.
        analysis_date: Date of the analysis.
        data_dir: Path to the data/ directory containing analyzed_log.json.
    """
    log_path = Path(data_dir) / "analyzed_log.json"

    # Load existing log
    if log_path.exists():
        try:
            log_data = json.loads(log_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not read analyzed_log.json, starting fresh")
            log_data = {}
    else:
        log_data = {}

    # Add or update entry
    if ticker not in log_data:
        log_data[ticker] = []

    log_data[ticker].append({
        "date": analysis_date.isoformat(),
        "company": company,
    })

    # Write back
    log_path.write_text(
        json.dumps(log_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Updated analyzed_log.json for %s", ticker)


def ensure_chart_dir(chart_date: date, charts_base_dir: str | Path) -> Path:
    """Create and return the chart output directory for a given date.

    Creates: {charts_base_dir}/{YYYY-MM-DD}/

    Args:
        chart_date: Date for the chart directory name.
        charts_base_dir: Base path for chart storage (e.g., site/public/charts/).

    Returns:
        Path to the created directory.
    """
    chart_dir = Path(charts_base_dir) / chart_date.isoformat()
    chart_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Chart directory ready: %s", chart_dir)
    return chart_dir
