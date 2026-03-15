"""Financial data validation and quality checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of financial data validation."""

    financial_data: list[dict]
    employee_counts: list[tuple[int, int]]
    warnings: list[str] = field(default_factory=list)
    is_valid: bool = True


def validate_financial_data(
    financial_data: list[dict],
    employee_counts: list[tuple[int, int]],
    ticker: str,
) -> ValidationResult:
    """Validate and clean financial data from SEC EDGAR.

    Checks:
    - Revenue > 0 for each year (removes years where revenue=0)
    - Margins between -200% and +200% (warns if violated)
    - Revenue doesn't drop >50% YoY (warns, doesn't remove)
    - At least 3 years of valid data after cleaning
    - Employee count warnings if all zeros/empty

    Args:
        financial_data: List of dicts from SECEdgarClient.get_financial_statements().
        employee_counts: List of (year, count) tuples.
        ticker: Ticker symbol for logging context.

    Returns:
        ValidationResult with cleaned data, warnings, and validity flag.
    """
    warnings: list[str] = []
    cleaned_data: list[dict] = []

    # --- Revenue > 0 filter ---
    zero_rev_years = []
    for stmt in financial_data:
        revenue = float(stmt.get("revenue", 0))
        if revenue <= 0:
            zero_rev_years.append(stmt.get("year"))
        else:
            cleaned_data.append(stmt)

    if zero_rev_years:
        warnings.append(
            f"{ticker}: Removed {len(zero_rev_years)} year(s) with zero/negative "
            f"revenue: {zero_rev_years}"
        )

    # --- Margin sanity checks ---
    for stmt in cleaned_data:
        year = stmt.get("year")
        revenue = float(stmt.get("revenue", 0))
        if revenue == 0:
            continue

        op_income = float(stmt.get("operating_income", 0))
        net_income = float(stmt.get("net_income", 0))

        op_margin = op_income / revenue * 100
        net_margin = net_income / revenue * 100

        if abs(op_margin) > 200:
            warnings.append(
                f"{ticker} {year}: Operating margin {op_margin:.1f}% is outside "
                f"[-200%, +200%] range -- possible data quality issue"
            )
        if abs(net_margin) > 200:
            warnings.append(
                f"{ticker} {year}: Net margin {net_margin:.1f}% is outside "
                f"[-200%, +200%] range -- possible data quality issue"
            )

    # --- Revenue drop >50% YoY check ---
    for i in range(1, len(cleaned_data)):
        prev_rev = float(cleaned_data[i - 1].get("revenue", 0))
        curr_rev = float(cleaned_data[i].get("revenue", 0))
        prev_year = cleaned_data[i - 1].get("year")
        curr_year = cleaned_data[i].get("year")

        if prev_rev > 0 and curr_rev > 0:
            pct_change = (curr_rev - prev_rev) / prev_rev * 100
            if pct_change < -50:
                warnings.append(
                    f"{ticker}: Revenue dropped {pct_change:.1f}% from {prev_year} "
                    f"to {curr_year} -- verify data accuracy"
                )

    # --- Employee count warnings ---
    if not employee_counts:
        warnings.append(
            f"{ticker}: No employee count data available from EDGAR"
        )
    elif all(count == 0 for _, count in employee_counts):
        warnings.append(
            f"{ticker}: All employee counts are zero"
        )

    # --- Minimum data threshold ---
    valid_years = len(cleaned_data)
    is_valid = valid_years >= 3
    if not is_valid:
        warnings.append(
            f"{ticker}: Only {valid_years} year(s) of valid data (need at least 3). "
            f"Insufficient for meaningful analysis."
        )

    return ValidationResult(
        financial_data=cleaned_data,
        employee_counts=employee_counts,
        warnings=warnings,
        is_valid=is_valid,
    )
