"""SEC EDGAR XBRL API client."""

from __future__ import annotations

import os
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"


class SECEdgarClient:
    """Client for the SEC EDGAR XBRL company facts API."""

    def __init__(self, email: str | None = None):
        self.email = email or os.environ.get("SEC_EDGAR_EMAIL", "")
        if not self.email:
            logger.warning("SEC_EDGAR_EMAIL not set; EDGAR calls may be rejected")
        self._client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": f"FrugalAnalyst/1.0 ({self.email})",
                "Accept": "application/json",
            },
        )

    def _pad_cik(self, cik: str) -> str:
        """Pad CIK to 10 digits."""
        return cik.lstrip("0").zfill(10)

    def get_company_facts(self, cik: str) -> dict[str, Any]:
        """Fetch all XBRL facts for a company.

        Returns the full companyfacts JSON, keyed by taxonomy (us-gaap, dei, etc.).
        """
        padded = self._pad_cik(cik)
        url = f"{BASE_URL}/CIK{padded}.json"

        try:
            response = self._client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("EDGAR HTTP error %s for CIK %s", exc.response.status_code, cik)
            return {}
        except httpx.RequestError as exc:
            logger.error("EDGAR request error for CIK %s: %s", cik, exc)
            return {}

    def get_employee_count(self, cik: str) -> list[tuple[int, int]]:
        """Extract employee counts from EDGAR XBRL facts.

        Looks for dei:EntityNumberOfEmployees in 10-K filings.
        Returns list of (year, count) tuples sorted by year ascending.
        """
        facts = self.get_company_facts(cik)
        if not facts:
            return []

        dei_facts = facts.get("facts", {}).get("dei", {})
        employee_data = dei_facts.get("EntityNumberOfEmployees", {})
        units = employee_data.get("units", {})

        # Employee counts are typically unitless or under "pure"
        observations = []
        for unit_key in ["pure", "number", "Number"]:
            if unit_key in units:
                observations = units[unit_key]
                break

        if not observations:
            # Try first available unit
            if units:
                observations = next(iter(units.values()))

        results: dict[int, int] = {}
        for obs in observations:
            form = obs.get("form", "")
            if form != "10-K":
                continue
            try:
                year = int(obs.get("fy", 0))
                val = int(obs.get("val", 0))
                if year > 0 and val > 0:
                    results[year] = val
            except (ValueError, TypeError):
                continue

        return sorted(results.items())

    def get_revenue(self, cik: str) -> list[tuple[int, float]]:
        """Extract annual revenue from EDGAR XBRL facts.

        Tries multiple revenue concept names used across filers.
        Returns list of (year, revenue) tuples sorted by year ascending.
        """
        facts = self.get_company_facts(cik)
        if not facts:
            return []

        gaap_facts = facts.get("facts", {}).get("us-gaap", {})

        # Try common revenue concept names
        revenue_concepts = [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
        ]

        for concept in revenue_concepts:
            if concept in gaap_facts:
                units = gaap_facts[concept].get("units", {})
                usd_data = units.get("USD", [])
                if usd_data:
                    return self._extract_annual(usd_data)

        return []

    def _extract_annual(self, observations: list[dict]) -> list[tuple[int, float]]:
        """Extract annual 10-K values from XBRL observations."""
        results: dict[int, float] = {}
        for obs in observations:
            form = obs.get("form", "")
            if form != "10-K":
                continue
            # Prefer full-year periods (fp = FY)
            fp = obs.get("fp", "")
            if fp not in ("FY", ""):
                continue
            try:
                year = int(obs.get("fy", 0))
                val = float(obs.get("val", 0))
                if year > 0:
                    results[year] = val
            except (ValueError, TypeError):
                continue

        return sorted(results.items())

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
