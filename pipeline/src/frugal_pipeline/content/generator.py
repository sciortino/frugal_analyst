"""Content generation via Claude API and post assembly."""

from __future__ import annotations

import os
import re
import logging
from datetime import date
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)


def generate_post(
    system_prompt: str,
    data_prompt: str,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """Generate blog post body via the Anthropic API.

    Args:
        system_prompt: The Frugal Analyst persona and formatting rules.
        data_prompt: Structured data package with all metrics.
        model: Claude model to use.

    Returns:
        Raw markdown body text.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=api_key)

    logger.info("Calling Claude API (model=%s)...", model)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {"role": "user", "content": data_prompt},
        ],
    )

    body = message.content[0].text
    logger.info(
        "Generated %d characters, %d tokens used",
        len(body),
        message.usage.input_tokens + message.usage.output_tokens,
    )
    return body


def assemble_post(
    title: str,
    post_date: date,
    ticker: str,
    company: str,
    sector: str,
    tags: list[str],
    description: str,
    body: str,
    chart_date_dir: str,
) -> str:
    """Assemble a complete blog post with YAML frontmatter.

    Args:
        title: Post title.
        post_date: Publication date.
        ticker: Stock ticker symbol.
        company: Full company name.
        sector: Company sector.
        tags: List of post tags.
        description: Short description for SEO/previews.
        body: Markdown body from Claude.
        chart_date_dir: Date-based chart directory name (e.g., '2026-03-14').

    Returns:
        Complete Markdown file content with frontmatter.
    """
    date_str = post_date.isoformat()
    tags_yaml = "\n".join(f'  - "{tag}"' for tag in tags)

    frontmatter = f"""---
title: "{title}"
description: "{description}"
pubDate: "{date_str}"
ticker: "{ticker}"
company: "{company}"
sector: "{sector}"
tags:
{tags_yaml}
---
"""

    # Fix chart image paths to be site-relative
    fixed_body = _fix_chart_paths(body, chart_date_dir)

    return frontmatter + "\n" + fixed_body


def _fix_chart_paths(body: str, chart_date_dir: str) -> str:
    """Fix chart image references to use site-relative paths.

    Converts raw filenames or local paths to /charts/{date}/filename.png format.
    """
    # Pattern: any image reference with a chart filename
    def replace_path(match: re.Match) -> str:
        alt = match.group(1)
        filename = Path(match.group(2)).name
        return f"![{alt}](/charts/{chart_date_dir}/{filename})"

    # Match markdown image syntax
    body = re.sub(r"!\[([^\]]*)\]\(([^)]+\.png)\)", replace_path, body)

    return body
