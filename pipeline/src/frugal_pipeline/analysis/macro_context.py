"""Macroeconomic context matching and computation."""

from __future__ import annotations

import logging

from frugal_pipeline.models import MacroContext
from frugal_pipeline.data_sources.fred import FREDClient
from frugal_pipeline.data_sources.bls import BLSClient

logger = logging.getLogger(__name__)

# Maps company sectors to relevant FRED employment series and BLS industry codes
SECTOR_MAPPING: dict[str, dict[str, str]] = {
    "Technology": {
        "fred_employment": "CES5051200001",  # Information sector (proxy)
        "bls_industry": "5051200",
        "display_name": "Information/Technology",
    },
    "Healthcare": {
        "fred_employment": "CES6562000001",  # Health care and social assistance
        "bls_industry": "6562000",
        "display_name": "Health Care",
    },
    "Finance": {
        "fred_employment": "CES5552000001",  # Finance and insurance
        "bls_industry": "5552000",
        "display_name": "Finance and Insurance",
    },
    "Consumer": {
        "fred_employment": "CES4200000001",  # Retail trade
        "bls_industry": "4200000",
        "display_name": "Retail/Consumer",
    },
    "Industrial": {
        "fred_employment": "CES3000000001",  # Manufacturing
        "bls_industry": "3000000",
        "display_name": "Manufacturing/Industrial",
    },
    "Energy": {
        "fred_employment": "CES1021000001",  # Mining and logging (includes oil/gas)
        "bls_industry": "1021000",
        "display_name": "Mining and Energy",
    },
    "Telecom": {
        "fred_employment": "CES5051700001",  # Telecommunications
        "bls_industry": "5051700",
        "display_name": "Telecommunications",
    },
}


def get_macro_context(
    sector: str,
    fred_client: FREDClient,
    bls_client: BLSClient,
) -> MacroContext:
    """Fetch and compute macroeconomic context for a given sector.

    Gathers national economic indicators and sector-specific employment data.
    Handles missing data gracefully -- any field may be None.
    """
    sector_info = SECTOR_MAPPING.get(sector, {})
    sector_display = sector_info.get("display_name", sector)

    # National unemployment rate (most recent value)
    unemployment_rate = _latest_value(fred_client.get_unemployment_rate())

    # Average hourly earnings growth (YoY)
    earnings_data = fred_client.get_avg_hourly_earnings()
    earnings_growth = _compute_yoy_growth(earnings_data)

    # National labor share
    labor_share_data = fred_client.get_labor_share()
    labor_share = _latest_value(labor_share_data)

    # CPI trend (last 12 months)
    cpi_data = fred_client.get_cpi()
    cpi_trend = [{"date": d, "value": v} for d, v in cpi_data[-12:]] if cpi_data else None

    # CPI-based inflation for real wage calc
    cpi_growth = _compute_yoy_growth(cpi_data)

    # Real wage growth = nominal earnings growth - CPI inflation
    real_wage_growth = None
    if earnings_growth is not None and cpi_growth is not None:
        real_wage_growth = round(earnings_growth - cpi_growth, 2)

    # Sector employment growth (from FRED)
    sector_emp_growth = None
    fred_series = sector_info.get("fred_employment")
    if fred_series:
        sector_emp_data = fred_client.get_sector_employment(fred_series)
        sector_emp_growth = _compute_yoy_growth(sector_emp_data)

    return MacroContext(
        unemployment_rate=unemployment_rate,
        sector_employment_growth=sector_emp_growth,
        avg_hourly_earnings_growth=earnings_growth,
        labor_share_national=labor_share,
        cpi_trend=cpi_trend,
        sector_name=sector_display,
        real_wage_growth=real_wage_growth,
    )


def _latest_value(data: list[tuple[str, float]]) -> float | None:
    """Return the most recent value from a FRED series."""
    if not data:
        return None
    return data[-1][1]


def _compute_yoy_growth(data: list[tuple[str, float]]) -> float | None:
    """Compute year-over-year growth rate from monthly FRED data.

    Compares the latest observation to the one 12 months prior.
    """
    if len(data) < 13:
        return None
    try:
        current = data[-1][1]
        year_ago = data[-13][1]
        if year_ago == 0:
            return None
        return round((current - year_ago) / year_ago * 100, 2)
    except (IndexError, TypeError):
        return None
