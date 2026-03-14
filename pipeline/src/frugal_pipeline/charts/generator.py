"""Matplotlib chart generation for Frugal Analyst blog posts."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from frugal_pipeline.models import FinancialMetrics, LaborMetrics, MacroContext

logger = logging.getLogger(__name__)

# Muted 6-color palette
COLORS = {
    "primary": "#2D6A9F",
    "secondary": "#D4763C",
    "tertiary": "#4A9B6E",
    "quaternary": "#8B5E9B",
    "quinary": "#C45B5B",
    "senary": "#7A8B99",
}

COLOR_LIST = list(COLORS.values())


def _setup_style() -> None:
    """Configure matplotlib style for clean, professional charts."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "axes.facecolor": "white",
        "axes.grid": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
        "figure.facecolor": "white",
        "figure.figsize": (8, 5),
        "figure.dpi": 150,
        "legend.framealpha": 0.9,
        "legend.edgecolor": "#CCCCCC",
    })


def generate_all_charts(
    financial_metrics: FinancialMetrics,
    labor_metrics: LaborMetrics,
    macro_context: MacroContext,
    company_name: str,
    ticker: str,
    output_dir: str | Path,
) -> list[str]:
    """Generate all chart types and return list of saved file paths."""
    _setup_style()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    chart_paths: list[str] = []

    # 1. Revenue vs headcount
    path = revenue_vs_headcount(
        financial_metrics, company_name, ticker, output_path
    )
    if path:
        chart_paths.append(path)

    # 2. Profit vs compensation
    path = profit_vs_compensation(
        financial_metrics, labor_metrics, company_name, ticker, output_path
    )
    if path:
        chart_paths.append(path)

    # 3. Margin trends
    path = margin_trends(
        financial_metrics, company_name, ticker, output_path
    )
    if path:
        chart_paths.append(path)

    # 4. Labor share comparison
    path = labor_share_comparison(
        labor_metrics, macro_context, company_name, ticker, output_path
    )
    if path:
        chart_paths.append(path)

    logger.info("Generated %d charts in %s", len(chart_paths), output_path)
    return chart_paths


def revenue_vs_headcount(
    metrics: FinancialMetrics,
    company_name: str,
    ticker: str,
    output_dir: Path,
) -> str | None:
    """Dual-axis indexed line chart: revenue and headcount indexed to base year = 100."""
    years = metrics.years
    revenue = metrics.revenue_trend
    headcount = metrics.employee_counts

    if len(years) < 2 or not any(h > 0 for h in headcount):
        logger.warning("Insufficient data for revenue vs headcount chart")
        return None

    # Index to base year
    rev_base = revenue[0] if revenue[0] != 0 else 1
    hc_base = headcount[0] if headcount[0] != 0 else 1
    rev_indexed = [r / rev_base * 100 for r in revenue]
    hc_indexed = [h / hc_base * 100 if h > 0 else None for h in headcount]

    fig, ax = plt.subplots()
    ax.plot(years, rev_indexed, marker="o", color=COLORS["primary"],
            linewidth=2, label="Revenue", markersize=6)
    ax.plot(years, hc_indexed, marker="s", color=COLORS["secondary"],
            linewidth=2, label="Headcount", markersize=6)
    ax.axhline(y=100, color="#999999", linestyle=":", alpha=0.5)

    ax.set_title(f"{company_name} ({ticker}): Revenue vs. Headcount Growth")
    ax.set_xlabel("Year")
    ax.set_ylabel("Indexed (Base Year = 100)")
    ax.legend()
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    filename = f"{ticker.lower()}_revenue_vs_headcount.png"
    filepath = output_dir / filename
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)
    return str(filepath)


def profit_vs_compensation(
    financial_metrics: FinancialMetrics,
    labor_metrics: LaborMetrics,
    company_name: str,
    ticker: str,
    output_dir: Path,
) -> str | None:
    """Grouped bar chart: profit per employee vs estimated compensation proxy."""
    years = financial_metrics.years
    profit_pe = financial_metrics.profit_per_employee

    if len(years) < 2 or not any(p != 0 for p in profit_pe):
        logger.warning("Insufficient data for profit vs compensation chart")
        return None

    # Estimate compensation per employee from SGA / headcount
    # (labor_metrics has estimated_labor_cost_ratio as SGA/revenue %)
    # We reconstruct SGA per employee from revenue_per_employee * ratio
    rpe = financial_metrics.revenue_per_employee
    ratios = labor_metrics.estimated_labor_cost_ratio
    comp_pe: list[float] = []
    for i in range(len(years)):
        if (i < len(ratios) and ratios[i] is not None
                and i < len(rpe) and rpe[i] > 0):
            comp_pe.append(rpe[i] * ratios[i] / 100)
        else:
            comp_pe.append(0)

    x = np.arange(len(years))
    width = 0.35

    fig, ax = plt.subplots()
    # Scale to thousands
    profit_k = [p / 1000 for p in profit_pe]
    comp_k = [c / 1000 for c in comp_pe]

    ax.bar(x - width / 2, profit_k, width, label="Net Income / Employee",
           color=COLORS["primary"], alpha=0.85)
    ax.bar(x + width / 2, comp_k, width, label="SGA / Employee (proxy)",
           color=COLORS["secondary"], alpha=0.85)

    ax.set_title(f"{company_name} ({ticker}): Profit vs. SGA per Employee")
    ax.set_xlabel("Year")
    ax.set_ylabel("$ Thousands")
    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years])
    ax.legend()

    filename = f"{ticker.lower()}_profit_vs_compensation.png"
    filepath = output_dir / filename
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)
    return str(filepath)


def margin_trends(
    metrics: FinancialMetrics,
    company_name: str,
    ticker: str,
    output_dir: Path,
) -> str | None:
    """Line chart of operating and net margins over time."""
    years = metrics.years
    op_margin = metrics.operating_margin_trend
    net_margin = metrics.net_margin_trend

    if len(years) < 2:
        logger.warning("Insufficient data for margin trends chart")
        return None

    fig, ax = plt.subplots()
    ax.plot(years, op_margin, marker="o", color=COLORS["primary"],
            linewidth=2, label="Operating Margin", markersize=6)
    ax.plot(years, net_margin, marker="s", color=COLORS["tertiary"],
            linewidth=2, label="Net Margin", markersize=6)
    ax.axhline(y=0, color="#999999", linestyle="-", alpha=0.3)

    ax.set_title(f"{company_name} ({ticker}): Margin Trends")
    ax.set_xlabel("Year")
    ax.set_ylabel("Margin (%)")
    ax.legend()
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    filename = f"{ticker.lower()}_margin_trends.png"
    filepath = output_dir / filename
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)
    return str(filepath)


def labor_share_comparison(
    labor_metrics: LaborMetrics,
    macro_context: MacroContext,
    company_name: str,
    ticker: str,
    output_dir: Path,
) -> str | None:
    """Line chart comparing company labor cost ratio to national labor share."""
    years = labor_metrics.years
    company_ratio = labor_metrics.estimated_labor_cost_ratio
    national_share = macro_context.labor_share_national

    valid_ratios = [r for r in company_ratio if r is not None]
    if len(years) < 2 or not valid_ratios:
        logger.warning("Insufficient data for labor share comparison chart")
        return None

    fig, ax = plt.subplots()

    # Company ratio
    plot_ratios = [r if r is not None else 0 for r in company_ratio]
    ax.plot(years, plot_ratios, marker="o", color=COLORS["primary"],
            linewidth=2, label=f"{ticker} SGA/Revenue Ratio", markersize=6)

    # National labor share as horizontal reference
    if national_share is not None:
        ax.axhline(y=national_share, color=COLORS["secondary"],
                   linestyle="--", linewidth=1.5,
                   label=f"National Labor Share ({national_share:.1f}%)")

    ax.set_title(f"{company_name} ({ticker}): Labor Cost Ratio vs. National")
    ax.set_xlabel("Year")
    ax.set_ylabel("Percentage (%)")
    ax.legend()
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    filename = f"{ticker.lower()}_labor_share.png"
    filepath = output_dir / filename
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)
    return str(filepath)
