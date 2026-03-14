"""Financial analysis computations."""

from __future__ import annotations

import logging

from frugal_pipeline.models import FinancialMetrics

logger = logging.getLogger(__name__)


def compute_financial_metrics(
    income_statements: list[dict],
    key_metrics: list[dict],
    employee_counts: list[dict],
    ticker: str,
) -> FinancialMetrics:
    """Compute multi-year financial metrics from FMP data.

    All input lists are expected newest-first (FMP default ordering).
    Output trends are oldest-first (chronological).
    """
    # Reverse to chronological order
    statements = list(reversed(income_statements))
    metrics_data = list(reversed(key_metrics))

    # Build employee count lookup by year
    emp_by_year: dict[int, int] = {}
    for emp in employee_counts:
        try:
            period = emp.get("periodOfReport", emp.get("acceptanceTime", ""))
            year = int(period[:4]) if period else 0
            count = int(emp.get("employeeCount", 0))
            if year > 0 and count > 0:
                emp_by_year[year] = count
        except (ValueError, TypeError, IndexError):
            continue

    years: list[int] = []
    revenue_trend: list[float] = []
    operating_margin_trend: list[float] = []
    net_margin_trend: list[float] = []
    revenue_per_employee: list[float] = []
    profit_per_employee: list[float] = []
    ebitda_per_employee: list[float] = []
    emp_counts: list[int] = []
    revenue_growth_yoy: list[float | None] = []

    for stmt in statements:
        try:
            date_str = stmt.get("date", stmt.get("fillingDate", ""))
            year = int(date_str[:4]) if date_str else 0
            if year == 0:
                continue

            revenue = float(stmt.get("revenue", 0))
            operating_income = float(stmt.get("operatingIncome", 0))
            net_income = float(stmt.get("netIncome", 0))
            ebitda = float(stmt.get("ebitda", 0))

            years.append(year)
            revenue_trend.append(revenue)

            # Margins
            if revenue != 0:
                operating_margin_trend.append(
                    round(operating_income / revenue * 100, 2)
                )
                net_margin_trend.append(round(net_income / revenue * 100, 2))
            else:
                operating_margin_trend.append(0.0)
                net_margin_trend.append(0.0)

            # Per-employee metrics
            emp_count = emp_by_year.get(year, 0)
            emp_counts.append(emp_count)

            if emp_count > 0:
                revenue_per_employee.append(round(revenue / emp_count, 2))
                profit_per_employee.append(round(net_income / emp_count, 2))
                ebitda_per_employee.append(round(ebitda / emp_count, 2))
            else:
                revenue_per_employee.append(0.0)
                profit_per_employee.append(0.0)
                ebitda_per_employee.append(0.0)

            # YoY revenue growth
            if len(revenue_trend) >= 2 and revenue_trend[-2] != 0:
                growth = (revenue - revenue_trend[-2]) / revenue_trend[-2] * 100
                revenue_growth_yoy.append(round(growth, 2))
            else:
                revenue_growth_yoy.append(None)

        except (ValueError, TypeError) as exc:
            logger.warning("Error processing statement for year: %s", exc)
            continue

    return FinancialMetrics(
        ticker=ticker,
        years=years,
        revenue_trend=revenue_trend,
        operating_margin_trend=operating_margin_trend,
        net_margin_trend=net_margin_trend,
        revenue_per_employee=revenue_per_employee,
        profit_per_employee=profit_per_employee,
        ebitda_per_employee=ebitda_per_employee,
        employee_counts=emp_counts,
        revenue_growth_yoy=revenue_growth_yoy,
    )
