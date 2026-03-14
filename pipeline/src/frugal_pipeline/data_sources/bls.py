"""Bureau of Labor Statistics (BLS) API v2 client."""

from __future__ import annotations

import os
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


class BLSClient:
    """Client for the BLS Public Data API v2.

    v2 provides 500 queries/day and up to 50 series per query.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("BLS_API_KEY", "")
        if not self.api_key:
            logger.warning("BLS_API_KEY not set; BLS calls will use v1 (limited)")
        self._client = httpx.Client(timeout=30.0)

    def get_series(
        self,
        series_ids: list[str],
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, list[dict]]:
        """Fetch one or more BLS time series.

        Args:
            series_ids: List of BLS series IDs (max 50).
            start_year: Start year (default: 5 years ago).
            end_year: End year (default: current year).

        Returns:
            Dict mapping series_id to list of observation dicts
            with keys: year, period, periodName, value.
        """
        now = datetime.now()
        if not start_year:
            start_year = now.year - 5
        if not end_year:
            end_year = now.year

        payload: dict = {
            "seriesid": series_ids[:50],
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if self.api_key:
            payload["registrationkey"] = self.api_key

        headers = {"Content-type": "application/json"}

        try:
            response = self._client.post(BASE_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "REQUEST_SUCCEEDED":
                logger.error("BLS API error: %s", data.get("message", "Unknown"))
                return {}

            results: dict[str, list[dict]] = {}
            for series in data.get("Results", {}).get("series", []):
                sid = series.get("seriesID", "")
                observations = []
                for item in series.get("data", []):
                    try:
                        observations.append({
                            "year": int(item["year"]),
                            "period": item["period"],
                            "period_name": item.get("periodName", ""),
                            "value": float(item["value"]),
                        })
                    except (ValueError, KeyError):
                        continue
                # BLS returns newest first; reverse to chronological
                observations.sort(key=lambda x: (x["year"], x["period"]))
                results[sid] = observations

            return results

        except httpx.HTTPStatusError as exc:
            logger.error("BLS HTTP error %s", exc.response.status_code)
            return {}
        except httpx.RequestError as exc:
            logger.error("BLS request error: %s", exc)
            return {}

    def get_industry_employment(self, industry_code: str) -> list[dict]:
        """Get employment data for a specific NAICS industry.

        Uses CES (Current Employment Statistics) series.
        Series format: CES{industry_code}01 for all employees.
        """
        series_id = f"CES{industry_code}01"
        result = self.get_series([series_id])
        return result.get(series_id, [])

    def get_quarterly_wages(
        self,
        industry_code: str,
        area_code: str = "US000",
    ) -> list[dict]:
        """Get quarterly wages for an industry from QCEW.

        Series format: ENU{area_code}{size_code}{ownership}{industry_code}
        Uses size=0 (all), ownership=5 (private).
        """
        series_id = f"ENU{area_code}05{industry_code}"
        result = self.get_series([series_id])
        return result.get(series_id, [])

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
