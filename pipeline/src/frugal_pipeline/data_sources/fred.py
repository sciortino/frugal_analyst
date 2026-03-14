"""Federal Reserve Economic Data (FRED) API client."""

from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


class FREDClient:
    """Client for the FRED API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        if not self.api_key:
            logger.warning("FRED_API_KEY not set; FRED calls will fail")
        self._client = httpx.Client(timeout=30.0)

    def get_series(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[tuple[str, float]]:
        """Fetch a FRED data series.

        Args:
            series_id: FRED series identifier (e.g. 'UNRATE').
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.

        Returns:
            List of (date_string, value) tuples.
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365 * 6)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date,
            "sort_order": "asc",
        }

        try:
            response = self._client.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            observations = data.get("observations", [])
            results = []
            for obs in observations:
                value_str = obs.get("value", ".")
                if value_str == ".":
                    continue
                try:
                    results.append((obs["date"], float(value_str)))
                except (ValueError, KeyError):
                    continue
            return results
        except httpx.HTTPStatusError as exc:
            logger.error("FRED HTTP error %s for %s", exc.response.status_code, series_id)
            return []
        except httpx.RequestError as exc:
            logger.error("FRED request error for %s: %s", series_id, exc)
            return []

    def get_unemployment_rate(self) -> list[tuple[str, float]]:
        """Get national unemployment rate (UNRATE)."""
        return self.get_series("UNRATE")

    def get_avg_hourly_earnings(self) -> list[tuple[str, float]]:
        """Get average hourly earnings of all employees (CES0500000003)."""
        return self.get_series("CES0500000003")

    def get_labor_share(self) -> list[tuple[str, float]]:
        """Get labor share of output, nonfarm business (PRS85006173)."""
        return self.get_series("PRS85006173")

    def get_cpi(self) -> list[tuple[str, float]]:
        """Get Consumer Price Index for all urban consumers (CPIAUCSL)."""
        return self.get_series("CPIAUCSL")

    def get_gdp(self) -> list[tuple[str, float]]:
        """Get Gross Domestic Product (GDP)."""
        return self.get_series("GDP")

    def get_sector_employment(self, sector_code: str) -> list[tuple[str, float]]:
        """Get employment data for a specific sector.

        Args:
            sector_code: FRED series ID for sector employment
                (e.g. 'CES5000000001' for financial activities).
        """
        return self.get_series(sector_code)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
