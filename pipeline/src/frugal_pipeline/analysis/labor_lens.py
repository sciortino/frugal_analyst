"""Labor-lens analysis computations."""

from __future__ import annotations

import logging

from frugal_pipeline.models import FinancialMetrics, LaborMetrics

logger = logging.getLogger(__name__)


def compute_labor_metrics(
    financial_metrics: FinancialMetrics,
    employee_counts: list[tuple[int, int]],
    financial_data: list[dict],
) -> LaborMetrics:
    """Compute labor-specific metrics from financial data.

    Args:
        financial_metrics: Pre-computed financial metrics.
        employee_counts: List of (year, count) tuples from SEC EDGAR.
        financial_data: List of dicts from SECEdgarClient.get_financial_statements(),
            sorted oldest-first, with keys: year, revenue, operating_income,
            net_income, ebitda, sga.

    Focuses on the relationship between corporate performance and workforce.
    """
    years = financial_metrics.years
    headcount = financial_metrics.employee_counts
    revenue = financial_metrics.revenue_trend
    notable_patterns: list[str] = []

    # Headcount growth vs revenue growth
    hc_vs_rev: list[dict] = []
    for i in range(1, len(years)):
        entry: dict = {"year": years[i]}
        if headcount[i] > 0 and headcount[i - 1] > 0:
            hc_growth = (headcount[i] - headcount[i - 1]) / headcount[i - 1] * 100
            entry["headcount_growth_pct"] = round(hc_growth, 2)
        else:
            entry["headcount_growth_pct"] = None

        if revenue[i] > 0 and revenue[i - 1] > 0:
            rev_growth = (revenue[i] - revenue[i - 1]) / revenue[i - 1] * 100
            entry["revenue_growth_pct"] = round(rev_growth, 2)
        else:
            entry["revenue_growth_pct"] = None

        hc_vs_rev.append(entry)

    # Estimated labor cost ratio using SGA as proxy
    # SGA (Selling, General & Administrative) contains most labor costs
    estimated_labor_ratio: list[float | None] = []
    for stmt in financial_data:
        try:
            sga = float(stmt.get("sga", 0))
            rev = float(stmt.get("revenue", 0))
            if rev > 0 and sga > 0:
                estimated_labor_ratio.append(round(sga / rev * 100, 2))
            else:
                estimated_labor_ratio.append(None)
        except (ValueError, TypeError):
            estimated_labor_ratio.append(None)

    # Profit-to-estimated-compensation ratio
    # Uses net income / SGA as rough proxy
    profit_to_comp: list[float | None] = []
    for stmt in financial_data:
        try:
            net_income = float(stmt.get("net_income", 0))
            sga = float(stmt.get("sga", 0))
            if sga > 0:
                profit_to_comp.append(round(net_income / sga, 2))
            else:
                profit_to_comp.append(None)
        except (ValueError, TypeError):
            profit_to_comp.append(None)

    # Revenue per employee indexed to base year (first year = 100)
    rpe = financial_metrics.revenue_per_employee
    rpe_indexed: list[float] = []
    base = rpe[0] if rpe and rpe[0] > 0 else 1.0
    for val in rpe:
        if val > 0:
            rpe_indexed.append(round(val / base * 100, 2))
        else:
            rpe_indexed.append(0.0)

    # Detect notable patterns
    _detect_patterns(
        years, headcount, revenue, rpe, hc_vs_rev, profit_to_comp, notable_patterns
    )

    return LaborMetrics(
        headcount_trend=headcount,
        headcount_growth_vs_revenue_growth=hc_vs_rev,
        estimated_labor_cost_ratio=estimated_labor_ratio,
        profit_to_compensation_ratio=profit_to_comp,
        revenue_per_employee_indexed=rpe_indexed,
        notable_patterns=notable_patterns,
        years=years,
    )


def _detect_patterns(
    years: list[int],
    headcount: list[int],
    revenue: list[float],
    rpe: list[float],
    hc_vs_rev: list[dict],
    profit_to_comp: list[float | None],
    patterns: list[str],
) -> None:
    """Detect notable labor-related patterns in the data."""
    # Pattern: headcount declining while revenue growing
    declining_hc_years = []
    for entry in hc_vs_rev:
        hc_g = entry.get("headcount_growth_pct")
        rev_g = entry.get("revenue_growth_pct")
        if hc_g is not None and rev_g is not None:
            if hc_g < -1.0 and rev_g > 1.0:
                declining_hc_years.append(entry["year"])

    if declining_hc_years:
        patterns.append(
            f"Headcount declining while revenue growing in {', '.join(map(str, declining_hc_years))}"
        )

    # Pattern: accelerating revenue per employee
    if len(rpe) >= 3:
        recent_rpe_growth = []
        for i in range(1, len(rpe)):
            if rpe[i - 1] > 0:
                recent_rpe_growth.append((rpe[i] - rpe[i - 1]) / rpe[i - 1] * 100)
        if len(recent_rpe_growth) >= 2 and all(g > 5 for g in recent_rpe_growth[-2:]):
            patterns.append("Revenue per employee growing at accelerating pace")

    # Pattern: profit-to-compensation ratio expanding
    valid_ptc = [v for v in profit_to_comp if v is not None]
    if len(valid_ptc) >= 3:
        if valid_ptc[-1] > valid_ptc[0] * 1.3:
            patterns.append(
                "Profit-to-compensation ratio expanded significantly over the period"
            )

    # Pattern: large headcount swings
    for entry in hc_vs_rev:
        hc_g = entry.get("headcount_growth_pct")
        if hc_g is not None and abs(hc_g) > 15:
            direction = "increase" if hc_g > 0 else "decrease"
            patterns.append(
                f"Notable headcount {direction} of {abs(hc_g):.1f}% in {entry['year']}"
            )
