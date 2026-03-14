"""Financial Modeling Prep API client."""

from __future__ import annotations

import os
import time
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com/api/v3"


class FMPClient:
    """Client for the Financial Modeling Prep API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FMP_API_KEY", "")
        if not self.api_key:
            logger.warning("FMP_API_KEY not set; FMP calls will fail")
        self._client = httpx.Client(timeout=30.0)
        self._last_request_time: float = 0.0
        self._min_interval: float = 0.3  # Rate limit: ~3 req/sec

    def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Make a rate-limited GET request to FMP."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

        url = f"{BASE_URL}/{endpoint}"
        request_params = {"apikey": self.api_key}
        if params:
            request_params.update(params)

        try:
            response = self._client.get(url, params=request_params)
            self._last_request_time = time.time()
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "Error Message" in data:
                logger.error("FMP API error: %s", data["Error Message"])
                return []
            return data
        except httpx.HTTPStatusError as exc:
            logger.error("FMP HTTP error %s for %s", exc.response.status_code, endpoint)
            return []
        except httpx.RequestError as exc:
            logger.error("FMP request error for %s: %s", endpoint, exc)
            return []

    def get_income_statements(
        self, ticker: str, period: str = "annual", limit: int = 5
    ) -> list[dict]:
        """Fetch income statements."""
        return self._request(
            f"income-statement/{ticker}",
            {"period": period, "limit": str(limit)},
        ) or []

    def get_quarterly_income_statements(
        self, ticker: str, limit: int = 8
    ) -> list[dict]:
        """Fetch quarterly income statements."""
        return self.get_income_statements(ticker, period="quarter", limit=limit)

    def get_key_metrics(
        self, ticker: str, period: str = "annual", limit: int = 5
    ) -> list[dict]:
        """Fetch key financial metrics."""
        return self._request(
            f"key-metrics/{ticker}",
            {"period": period, "limit": str(limit)},
        ) or []

    def get_company_profile(self, ticker: str) -> dict:
        """Fetch company profile."""
        data = self._request(f"profile/{ticker}")
        if isinstance(data, list) and data:
            return data[0]
        return {}

    def get_earnings_calendar(
        self, from_date: str, to_date: str
    ) -> list[dict]:
        """Fetch earnings calendar for a date range.

        Dates should be in YYYY-MM-DD format.
        """
        return self._request(
            "earning_calendar",
            {"from": from_date, "to": to_date},
        ) or []

    def get_employee_count(self, ticker: str) -> list[dict]:
        """Fetch historical employee counts.

        Returns list of dicts with 'periodOfReport', 'employeeCount', etc.
        FMP v4 endpoint.
        """
        url = "https://financialmodelingprep.com/api/v4/historical/employee_count"
        params = {"symbol": ticker, "apikey": self.api_key}

        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return data
            return []
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.error("FMP employee count error for %s: %s", ticker, exc)
            return []

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
