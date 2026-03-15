"""Main orchestrator for the Frugal Analyst pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from frugal_pipeline.company_selector import select_company
from frugal_pipeline.data_sources.fmp import FMPClient
from frugal_pipeline.data_sources.sec_edgar import SECEdgarClient
from frugal_pipeline.data_sources.fred import FREDClient
from frugal_pipeline.data_sources.bls import BLSClient
from frugal_pipeline.analysis.financials import compute_financial_metrics
from frugal_pipeline.analysis.labor_lens import compute_labor_metrics
from frugal_pipeline.analysis.macro_context import get_macro_context
from frugal_pipeline.charts.generator import generate_all_charts
from frugal_pipeline.content.prompt import build_system_prompt, build_data_prompt
from frugal_pipeline.content.generator import generate_post, assemble_post
from frugal_pipeline.output.writer import write_post, update_analyzed_log, ensure_chart_dir

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Frugal Analyst: automated financial analysis pipeline"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Override company selection with a specific ticker",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without writing output files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output site directory (default: ../../site)",
    )
    parser.add_argument(
        "--weekend",
        action="store_true",
        help="Generate weekend op-ed style post instead of standard analysis",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the pipeline."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run() -> None:
    """Execute the full analysis pipeline."""
    args = parse_args()
    setup_logging(args.verbose)

    # Resolve paths
    pipeline_dir = Path(__file__).resolve().parent.parent.parent  # pipeline/
    project_root = pipeline_dir.parent  # frugal_analyst/
    data_dir = project_root / "data"
    site_dir = Path(args.output_dir) if args.output_dir else project_root / "site"
    blog_dir = site_dir / "src" / "content" / "blog"
    charts_base_dir = site_dir / "public" / "charts"

    # Load environment variables from project root
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info("Loaded .env from %s", env_path)
    else:
        logger.warning("No .env file found at %s", env_path)

    today = date.today()
    logger.info("Starting Frugal Analyst pipeline for %s", today.isoformat())

    # Initialize API clients
    fmp = FMPClient()
    edgar = SECEdgarClient()
    fred = FREDClient()
    bls = BLSClient()

    try:
        # Step 1: Select company
        logger.info("Step 1: Selecting company...")
        selection = select_company(data_dir, fmp, override_ticker=args.ticker)
        logger.info(
            "Selected: %s (%s) - %s",
            selection.company_name,
            selection.ticker,
            selection.selection_reason,
        )

        # Step 2: Fetch corporate data
        logger.info("Step 2: Fetching corporate data...")
        income_statements = fmp.get_income_statements(selection.ticker)
        key_metrics = fmp.get_key_metrics(selection.ticker)
        employee_counts_fmp = fmp.get_employee_count(selection.ticker)
        company_profile = fmp.get_company_profile(selection.ticker)

        logger.info(
            "FMP data: %d income statements, %d key metrics, %d employee records",
            len(income_statements),
            len(key_metrics),
            len(employee_counts_fmp),
        )

        # Supplement with SEC EDGAR if CIK available
        employee_counts_edgar: list[tuple[int, int]] = []
        if selection.cik:
            logger.info("Fetching SEC EDGAR data for CIK %s...", selection.cik)
            employee_counts_edgar = edgar.get_employee_count(selection.cik)
            logger.info("EDGAR: %d employee count records", len(employee_counts_edgar))

        # Merge employee data: prefer FMP, fill gaps from EDGAR
        employee_counts = _merge_employee_data(employee_counts_fmp, employee_counts_edgar)

        # Step 3: Fetch macro context
        logger.info("Step 3: Fetching macroeconomic context...")
        sector = selection.sector
        if company_profile and not sector:
            sector = company_profile.get("sector", "Unknown")
        macro_context = get_macro_context(sector, fred, bls)
        logger.info("Macro context: unemployment=%.1f%%, sector=%s",
                     macro_context.unemployment_rate or 0,
                     macro_context.sector_name)

        # Step 4: Run analysis
        logger.info("Step 4: Computing financial metrics...")
        financial_metrics = compute_financial_metrics(
            income_statements, key_metrics, employee_counts, selection.ticker
        )
        logger.info("Financial metrics: %d years of data", len(financial_metrics.years))

        if len(financial_metrics.years) < 2:
            logger.error(
                "Insufficient financial data for %s (%s): only %d years. "
                "Need at least 2 years for meaningful analysis. "
                "Check that data source API keys are configured.",
                selection.company_name,
                selection.ticker,
                len(financial_metrics.years),
            )
            raise SystemExit(1)

        logger.info("Step 5: Computing labor metrics...")
        labor_metrics = compute_labor_metrics(
            financial_metrics, employee_counts, income_statements
        )
        logger.info("Labor patterns detected: %d", len(labor_metrics.notable_patterns))
        for pattern in labor_metrics.notable_patterns:
            logger.info("  - %s", pattern)

        # Step 5: Generate charts
        logger.info("Step 6: Generating charts...")
        chart_dir = ensure_chart_dir(today, charts_base_dir)
        chart_paths = generate_all_charts(
            financial_metrics,
            labor_metrics,
            macro_context,
            selection.company_name,
            selection.ticker,
            chart_dir,
        )
        logger.info("Generated %d charts", len(chart_paths))

        # Step 6: Generate content via Claude
        logger.info("Step 7: Generating content via Claude API...")
        system_prompt = build_system_prompt(weekend=args.weekend)
        if args.weekend:
            logger.info("Weekend mode: generating op-ed style analysis")
        data_prompt = build_data_prompt(
            company_name=selection.company_name,
            ticker=selection.ticker,
            sector=selection.sector,
            selection_reason=selection.selection_reason,
            financial_metrics=financial_metrics,
            labor_metrics=labor_metrics,
            macro_context=macro_context,
            chart_paths=chart_paths,
        )

        body = generate_post(system_prompt, data_prompt)

        # Extract title from first line of body (Claude should start with # Title)
        title, body_text = _extract_title(body, selection.company_name, selection.ticker)

        # Build tags
        base_tags = [
            selection.sector.lower(),
            selection.ticker.lower(),
            "labor-economics",
        ]
        if args.weekend:
            tags = base_tags + ["op-ed", "weekend-edition"]
        else:
            tags = base_tags + ["financial-analysis"]

        # Build description
        if args.weekend:
            description = (
                f"Weekend op-ed using {selection.company_name} ({selection.ticker}) "
                f"to explore a bigger question about labor, capital, and the economy."
            )
        else:
            description = (
                f"Data-driven analysis of {selection.company_name} ({selection.ticker}) "
                f"through a labor economics lens."
            )

        # Assemble complete post
        content = assemble_post(
            title=title,
            post_date=today,
            ticker=selection.ticker,
            company=selection.company_name,
            sector=selection.sector,
            tags=tags,
            description=description,
            body=body_text,
            chart_date_dir=today.isoformat(),
        )

        # Step 7: Write output
        if args.dry_run:
            logger.info("DRY RUN: would write post and update log")
            logger.info("Title: %s", title)
            logger.info("Content length: %d characters", len(content))
            print("\n--- GENERATED POST PREVIEW ---\n")
            print(content[:2000])
            if len(content) > 2000:
                print(f"\n... [{len(content) - 2000} more characters] ...")
        else:
            logger.info("Step 8: Writing output files...")
            suffix = "op-ed" if args.weekend else "analysis"
            filename = f"{today.isoformat()}-{selection.ticker.lower()}-{suffix}.md"
            write_post(content, filename, blog_dir)
            update_analyzed_log(
                selection.ticker, selection.company_name, today, data_dir
            )
            logger.info("Pipeline complete. Post written: %s", filename)

    finally:
        # Clean up clients
        fmp.close()
        edgar.close()
        fred.close()
        bls.close()


def _merge_employee_data(
    fmp_data: list[dict],
    edgar_data: list[tuple[int, int]],
) -> list[dict]:
    """Merge employee count data from FMP and EDGAR sources.

    FMP data takes precedence; EDGAR fills gaps.
    Returns FMP-format dicts.
    """
    result_by_year: dict[int, dict] = {}

    # FMP data first
    for entry in fmp_data:
        try:
            period = entry.get("periodOfReport", entry.get("acceptanceTime", ""))
            year = int(period[:4]) if period else 0
            if year > 0:
                result_by_year[year] = entry
        except (ValueError, TypeError, IndexError):
            continue

    # Fill from EDGAR
    for year, count in edgar_data:
        if year not in result_by_year:
            result_by_year[year] = {
                "periodOfReport": f"{year}-12-31",
                "employeeCount": count,
                "source": "SEC EDGAR",
            }

    # Return sorted by year (newest first, matching FMP convention)
    return [
        result_by_year[y]
        for y in sorted(result_by_year.keys(), reverse=True)
    ]


def _extract_title(
    body: str,
    company_name: str,
    ticker: str,
) -> tuple[str, str]:
    """Extract title from generated content.

    If the body starts with a markdown heading, use it as the title
    and return the remaining body. Otherwise generate a default title.
    """
    lines = body.strip().split("\n")
    if lines and lines[0].startswith("# "):
        title = lines[0].lstrip("# ").strip()
        remaining = "\n".join(lines[1:]).strip()
        return title, remaining

    # Default title
    title = f"{company_name} ({ticker}): A Labor Economics Perspective"
    return title, body


if __name__ == "__main__":
    run()
