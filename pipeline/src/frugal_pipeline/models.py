"""Shared Pydantic models for the Frugal Analyst pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CompanySelection(BaseModel):
    """Result of the company selection process."""

    ticker: str
    company_name: str
    sector: str
    cik: str
    selection_reason: str


class FinancialMetrics(BaseModel):
    """Computed financial metrics over a multi-year window."""

    ticker: str
    years: list[int] = Field(default_factory=list)
    revenue_trend: list[float] = Field(default_factory=list)
    operating_margin_trend: list[float] = Field(default_factory=list)
    net_margin_trend: list[float] = Field(default_factory=list)
    revenue_per_employee: list[float] = Field(default_factory=list)
    profit_per_employee: list[float] = Field(default_factory=list)
    ebitda_per_employee: list[float] = Field(default_factory=list)
    employee_counts: list[int] = Field(default_factory=list)
    revenue_growth_yoy: list[float | None] = Field(default_factory=list)


class LaborMetrics(BaseModel):
    """Labor-lens analysis metrics."""

    headcount_trend: list[int] = Field(default_factory=list)
    headcount_growth_vs_revenue_growth: list[dict] = Field(default_factory=list)
    estimated_labor_cost_ratio: list[float | None] = Field(default_factory=list)
    profit_to_compensation_ratio: list[float | None] = Field(default_factory=list)
    revenue_per_employee_indexed: list[float] = Field(default_factory=list)
    notable_patterns: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)


class MacroContext(BaseModel):
    """Macroeconomic context data."""

    unemployment_rate: float | None = None
    sector_employment_growth: float | None = None
    avg_hourly_earnings_growth: float | None = None
    labor_share_national: float | None = None
    cpi_trend: list[dict] | None = None
    sector_name: str = ""
    real_wage_growth: float | None = None
