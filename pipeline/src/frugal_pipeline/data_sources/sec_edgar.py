"""SEC EDGAR XBRL API client."""

from __future__ import annotations

import os
import logging
import re
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"

# Concept lists ordered by preference (ASC 606 first for revenue)
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
]

NET_INCOME_CONCEPTS = [
    "NetIncomeLoss",
    "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
]

OPERATING_INCOME_CONCEPTS = [
    "OperatingIncomeLoss",
]

EBITDA_CONCEPTS = [
    "EarningsBeforeInterestTaxesDepreciationAndAmortization",
]

SGA_CONCEPTS = [
    "SellingGeneralAndAdministrativeExpense",
    "GeneralAndAdministrativeExpense",
]


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

    # ------------------------------------------------------------------
    # Smart concept resolution
    # ------------------------------------------------------------------

    def _resolve_concept(
        self,
        gaap_facts: dict[str, Any],
        concept_names: list[str],
        label: str = "metric",
    ) -> list[tuple[int, float]]:
        """Pick the best concept from candidates using scoring.

        For each candidate concept that exists in gaap_facts:
        1. Extract annual values via _extract_annual()
        2. Score by recency, coverage, and plausibility
        3. Return data from the highest-scoring concept

        Args:
            gaap_facts: The us-gaap facts dict from EDGAR.
            concept_names: Ordered list of XBRL concept names to try.
            label: Human-readable label for logging.

        Returns:
            List of (year, value) tuples from the best concept.
        """
        current_year = date.today().year
        best_score = -1.0
        best_data: list[tuple[int, float]] = []
        best_concept: str = ""

        for concept in concept_names:
            if concept not in gaap_facts:
                continue
            units = gaap_facts[concept].get("units", {})
            usd_data = units.get("USD", [])
            if not usd_data:
                continue

            annual_data = self._extract_annual(usd_data)
            if not annual_data:
                continue

            score = self._score_concept(annual_data, current_year)
            logger.debug(
                "Concept %s for %s: %d years, score=%.2f",
                concept, label, len(annual_data), score,
            )

            if score > best_score:
                best_score = score
                best_data = annual_data
                best_concept = concept

        if best_concept:
            logger.debug("Selected concept '%s' for %s (score=%.2f)", best_concept, label, best_score)

        return best_data

    def _score_concept(
        self,
        data: list[tuple[int, float]],
        current_year: int,
    ) -> float:
        """Score a concept's data by recency, coverage, and plausibility.

        Scoring weights:
        - Recency (50%): Has data within last 3 years
        - Coverage (30%): Number of years of data
        - Plausibility (20%): No single value 10x larger than neighbors
        """
        if not data:
            return 0.0

        years = [y for y, _ in data]
        values = [v for _, v in data]

        # Recency: bonus for recent data (last 3 years)
        most_recent = max(years)
        recency_score = 0.0
        if most_recent >= current_year - 1:
            recency_score = 1.0
        elif most_recent >= current_year - 2:
            recency_score = 0.7
        elif most_recent >= current_year - 3:
            recency_score = 0.4

        # Coverage: normalized by a reasonable max (15 years)
        coverage_score = min(len(data) / 15.0, 1.0)

        # Plausibility: check for wild outliers
        plausibility_score = 1.0
        if len(values) >= 3:
            for i in range(1, len(values) - 1):
                prev_val, cur_val, next_val = abs(values[i - 1]), abs(values[i]), abs(values[i + 1])
                neighbors_avg = (prev_val + next_val) / 2.0
                if neighbors_avg > 0 and cur_val > neighbors_avg * 10:
                    plausibility_score *= 0.5
                if cur_val > 0 and neighbors_avg > cur_val * 10:
                    plausibility_score *= 0.5

        return (recency_score * 0.5) + (coverage_score * 0.3) + (plausibility_score * 0.2)

    def _resolve_concept_with_stitching(
        self,
        gaap_facts: dict[str, Any],
        concept_names: list[str],
        label: str = "metric",
    ) -> list[tuple[int, float]]:
        """Resolve the best concept, then stitch older data from fallback concepts.

        After picking the best concept via scoring, if it only covers recent
        years, look at lower-priority concepts for older years and merge.
        """
        current_year = date.today().year

        # Collect all concept data
        concept_data: list[tuple[str, list[tuple[int, float]], float]] = []
        for concept in concept_names:
            if concept not in gaap_facts:
                continue
            units = gaap_facts[concept].get("units", {})
            usd_data = units.get("USD", [])
            if not usd_data:
                continue
            annual_data = self._extract_annual(usd_data)
            if not annual_data:
                continue
            score = self._score_concept(annual_data, current_year)
            concept_data.append((concept, annual_data, score))

        if not concept_data:
            return []

        # Sort by score descending
        concept_data.sort(key=lambda x: x[2], reverse=True)
        best_concept, best_data, best_score = concept_data[0]
        logger.debug("Selected concept '%s' for %s (score=%.2f)", best_concept, label, best_score)

        # Build result dict from best concept
        result: dict[int, float] = dict(best_data)
        min_year_in_best = min(result.keys())

        # Stitch older years from other concepts
        for concept, data, score in concept_data[1:]:
            stitched_years = []
            for year, val in data:
                if year < min_year_in_best and year not in result:
                    result[year] = val
                    stitched_years.append(year)
            if stitched_years:
                logger.info(
                    "Stitched %s years %s from concept '%s' into '%s'",
                    label, stitched_years, concept, best_concept,
                )

        return sorted(result.items())

    # ------------------------------------------------------------------
    # Public data methods (all accept optional _facts to avoid re-fetching)
    # ------------------------------------------------------------------

    def get_employee_count(
        self, cik: str, *, _facts: dict[str, Any] | None = None,
    ) -> list[tuple[int, int]]:
        """Extract employee counts from EDGAR XBRL facts.

        Looks for dei:EntityNumberOfEmployees in 10-K filings.
        Returns list of (year, count) tuples sorted by year ascending.
        """
        facts = _facts if _facts is not None else self.get_company_facts(cik)
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

    def get_revenue(
        self, cik: str, *, _facts: dict[str, Any] | None = None,
    ) -> list[tuple[int, float]]:
        """Extract annual revenue from EDGAR XBRL facts.

        Uses smart concept resolution with cross-year stitching.
        Returns list of (year, revenue) tuples sorted by year ascending.
        """
        facts = _facts if _facts is not None else self.get_company_facts(cik)
        if not facts:
            return []
        gaap_facts = facts.get("facts", {}).get("us-gaap", {})
        return self._resolve_concept_with_stitching(gaap_facts, REVENUE_CONCEPTS, label="revenue")

    def get_net_income(
        self, cik: str, *, _facts: dict[str, Any] | None = None,
    ) -> list[tuple[int, float]]:
        """Extract annual net income from EDGAR XBRL facts.

        Uses smart concept resolution with cross-year stitching.
        Returns list of (year, net_income) tuples sorted by year ascending.
        """
        facts = _facts if _facts is not None else self.get_company_facts(cik)
        if not facts:
            return []
        gaap_facts = facts.get("facts", {}).get("us-gaap", {})
        return self._resolve_concept_with_stitching(gaap_facts, NET_INCOME_CONCEPTS, label="net_income")

    def get_operating_income(
        self, cik: str, *, _facts: dict[str, Any] | None = None,
    ) -> list[tuple[int, float]]:
        """Extract annual operating income from EDGAR XBRL facts.

        Returns list of (year, operating_income) tuples sorted by year ascending.
        """
        facts = _facts if _facts is not None else self.get_company_facts(cik)
        if not facts:
            return []
        gaap_facts = facts.get("facts", {}).get("us-gaap", {})
        return self._resolve_concept(gaap_facts, OPERATING_INCOME_CONCEPTS, label="operating_income")

    def get_ebitda(
        self, cik: str, *, _facts: dict[str, Any] | None = None,
    ) -> list[tuple[int, float]]:
        """Extract annual EBITDA from EDGAR XBRL facts.

        EBITDA is not always reported directly in XBRL. If the concept is not
        found, returns an empty list (callers should handle gracefully).
        Returns list of (year, ebitda) tuples sorted by year ascending.
        """
        facts = _facts if _facts is not None else self.get_company_facts(cik)
        if not facts:
            return []
        gaap_facts = facts.get("facts", {}).get("us-gaap", {})
        return self._resolve_concept(gaap_facts, EBITDA_CONCEPTS, label="ebitda")

    def _get_sga(
        self, cik: str, *, _facts: dict[str, Any] | None = None,
    ) -> list[tuple[int, float]]:
        """Extract annual SGA expenses from EDGAR XBRL facts.

        Used as a proxy for labor costs in labor-lens analysis.
        Returns list of (year, sga) tuples sorted by year ascending.
        """
        facts = _facts if _facts is not None else self.get_company_facts(cik)
        if not facts:
            return []
        gaap_facts = facts.get("facts", {}).get("us-gaap", {})
        return self._resolve_concept(gaap_facts, SGA_CONCEPTS, label="sga")

    def get_financial_statements(self, cik: str) -> list[dict]:
        """Fetch all financial metrics and merge into annual statements.

        Calls get_company_facts() ONCE and passes the result to all metric
        extractors. Merges into a list of dicts sorted oldest-first.

        Each dict has keys: year, revenue, operating_income, net_income,
        ebitda, sga. Missing values default to 0.
        """
        facts = self.get_company_facts(cik)
        if not facts:
            return []

        revenue_data = self.get_revenue(cik, _facts=facts)
        operating_data = self.get_operating_income(cik, _facts=facts)
        net_income_data = self.get_net_income(cik, _facts=facts)
        ebitda_data = self.get_ebitda(cik, _facts=facts)
        sga_data = self._get_sga(cik, _facts=facts)

        # Collect all years
        all_years: set[int] = set()
        for series in [revenue_data, operating_data, net_income_data, ebitda_data, sga_data]:
            for year, _ in series:
                all_years.add(year)

        if not all_years:
            return []

        # Build lookup dicts
        rev_lookup = dict(revenue_data)
        op_lookup = dict(operating_data)
        ni_lookup = dict(net_income_data)
        ebitda_lookup = dict(ebitda_data)
        sga_lookup = dict(sga_data)

        results = []
        for year in sorted(all_years):
            results.append({
                "year": year,
                "revenue": rev_lookup.get(year, 0),
                "operating_income": op_lookup.get(year, 0),
                "net_income": ni_lookup.get(year, 0),
                "ebitda": ebitda_lookup.get(year, 0),
                "sga": sga_lookup.get(year, 0),
            })

        return results

    def _extract_annual(self, observations: list[dict]) -> list[tuple[int, float]]:
        """Extract annual 10-K values from XBRL observations.

        Strategy:
        1. Strongly prefer observations with a `frame` field matching CY{year}
           (full-year, non-quarterly). These are the canonical, deduplicated
           values from SEC's XBRL aggregation.
        2. For years with no CY{year} frame entry, fall back to the `end` date
           to determine the reporting year, taking only the most-recently-filed
           observation (latest `filed` date) to avoid duplicates from restatements.
        3. When multiple values exist for the same year, keep the largest
           (handles total vs. segment reporting).
        """
        # Phase 1: Collect framed (canonical) observations
        framed: dict[int, float] = {}
        for obs in observations:
            form = obs.get("form", "")
            if form != "10-K":
                continue
            fp = obs.get("fp", "")
            if fp not in ("FY", ""):
                continue

            frame = obs.get("frame", "")
            if not frame:
                continue

            # Match only full-year frames: CY2022, not CY2022Q3
            m = re.match(r"^CY(\d{4})$", frame)
            if not m:
                continue

            try:
                year = int(m.group(1))
                val = float(obs.get("val", 0))
            except (ValueError, TypeError):
                continue

            # Keep the largest value per year
            if year not in framed or val > framed[year]:
                framed[year] = val

        # Phase 2: For years not covered by framed data, use end-date fallback
        # Group unframed observations by end-date year, keep most recently filed
        unframed: dict[int, tuple[float, str]] = {}  # year -> (val, filed_date)
        for obs in observations:
            form = obs.get("form", "")
            if form != "10-K":
                continue
            fp = obs.get("fp", "")
            if fp not in ("FY", ""):
                continue
            frame = obs.get("frame", "")
            if frame:
                continue  # Already handled above

            end_date = obs.get("end", "")
            if not end_date or len(end_date) < 4:
                continue

            try:
                end_year = int(end_date[:4])
                val = float(obs.get("val", 0))
                filed = obs.get("filed", "")
            except (ValueError, TypeError):
                continue

            if end_year in framed:
                continue  # Already have canonical data for this year

            # Keep the most recently filed, or largest if same filed date
            if end_year not in unframed:
                unframed[end_year] = (val, filed)
            else:
                existing_val, existing_filed = unframed[end_year]
                if filed > existing_filed or (filed == existing_filed and val > existing_val):
                    unframed[end_year] = (val, filed)

        # Merge
        results: dict[int, float] = dict(framed)
        for year, (val, _) in unframed.items():
            if year not in results:
                results[year] = val

        if results:
            logger.debug(
                "Extracted %d annual values: years %d-%d (framed=%d, fallback=%d)",
                len(results), min(results.keys()), max(results.keys()),
                len(framed), len(results) - len(framed),
            )

        return sorted(results.items())

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
