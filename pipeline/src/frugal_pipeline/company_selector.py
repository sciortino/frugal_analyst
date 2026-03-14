"""Company selection logic for daily analysis."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from frugal_pipeline.models import CompanySelection
from frugal_pipeline.data_sources.fmp import FMPClient

logger = logging.getLogger(__name__)

# Cooldown period: don't re-analyze a company within this many days
COOLDOWN_DAYS = 60


def select_company(
    data_dir: str | Path,
    fmp_client: FMPClient,
    override_ticker: str | None = None,
) -> CompanySelection:
    """Select a company for today's analysis.

    Selection priority:
    1. CLI override (--ticker)
    2. Upcoming earnings reporters in universe (not recently analyzed)
    3. Events queue (manual overrides in events_queue.json)
    4. Sector rotation fallback (oldest or never analyzed)

    Args:
        data_dir: Path to the data/ directory.
        fmp_client: FMP client for earnings calendar lookups.
        override_ticker: Ticker override from CLI.

    Returns:
        CompanySelection with chosen company details.
    """
    data_path = Path(data_dir)
    universe = _load_universe(data_path)
    analyzed_log = _load_analyzed_log(data_path)

    if not universe:
        raise RuntimeError(f"No companies in {data_path / 'company_universe.json'}")

    # Build lookup
    universe_by_ticker = {c["ticker"]: c for c in universe}

    # 1. CLI override
    if override_ticker:
        ticker = override_ticker.upper()
        if ticker in universe_by_ticker:
            co = universe_by_ticker[ticker]
            return CompanySelection(
                ticker=ticker,
                company_name=co["company"],
                sector=co["sector"],
                cik=co["cik"],
                selection_reason=f"Manual override via --ticker {ticker}",
            )
        else:
            # Allow tickers not in universe (user knows what they want)
            return CompanySelection(
                ticker=ticker,
                company_name=ticker,
                sector="Unknown",
                cik="",
                selection_reason=f"Manual override (not in universe): {ticker}",
            )

    # 2. Upcoming earnings reporters
    selection = _check_earnings_calendar(universe, analyzed_log, fmp_client)
    if selection:
        return selection

    # 3. Events queue
    selection = _check_events_queue(data_path, universe_by_ticker, analyzed_log)
    if selection:
        return selection

    # 4. Sector rotation fallback
    return _sector_rotation_fallback(universe, analyzed_log)


def _load_universe(data_path: Path) -> list[dict]:
    """Load company_universe.json."""
    filepath = data_path / "company_universe.json"
    try:
        return json.loads(filepath.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.error("Failed to load company universe: %s", exc)
        return []


def _load_analyzed_log(data_path: Path) -> dict:
    """Load analyzed_log.json."""
    filepath = data_path / "analyzed_log.json"
    try:
        return json.loads(filepath.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _is_recently_analyzed(ticker: str, analyzed_log: dict) -> bool:
    """Check if a ticker was analyzed within the cooldown period."""
    entries = analyzed_log.get(ticker, [])
    if not entries:
        return False

    cutoff = datetime.now() - timedelta(days=COOLDOWN_DAYS)
    for entry in entries:
        try:
            analysis_date = datetime.fromisoformat(entry["date"])
            if analysis_date > cutoff:
                return True
        except (KeyError, ValueError):
            continue
    return False


def _last_analyzed_date(ticker: str, analyzed_log: dict) -> datetime | None:
    """Get the most recent analysis date for a ticker."""
    entries = analyzed_log.get(ticker, [])
    if not entries:
        return None

    dates = []
    for entry in entries:
        try:
            dates.append(datetime.fromisoformat(entry["date"]))
        except (KeyError, ValueError):
            continue
    return max(dates) if dates else None


def _check_earnings_calendar(
    universe: list[dict],
    analyzed_log: dict,
    fmp_client: FMPClient,
) -> CompanySelection | None:
    """Check for upcoming earnings reporters in the universe."""
    today = datetime.now()
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")

    universe_tickers = {c["ticker"] for c in universe}
    ticker_lookup = {c["ticker"]: c for c in universe}

    try:
        calendar = fmp_client.get_earnings_calendar(from_date, to_date)
    except Exception as exc:
        logger.warning("Failed to fetch earnings calendar: %s", exc)
        return None

    # Find universe companies reporting soon
    candidates = []
    for entry in calendar:
        ticker = entry.get("symbol", "")
        if ticker in universe_tickers and not _is_recently_analyzed(ticker, analyzed_log):
            report_date = entry.get("date", "")
            candidates.append((ticker, report_date))

    if not candidates:
        return None

    # Pick the soonest reporter
    candidates.sort(key=lambda x: x[1])
    ticker, report_date = candidates[0]
    co = ticker_lookup[ticker]

    return CompanySelection(
        ticker=ticker,
        company_name=co["company"],
        sector=co["sector"],
        cik=co["cik"],
        selection_reason=f"Upcoming earnings report on {report_date}",
    )


def _check_events_queue(
    data_path: Path,
    universe_by_ticker: dict[str, dict],
    analyzed_log: dict,
) -> CompanySelection | None:
    """Check events_queue.json for manually queued analyses."""
    queue_path = data_path / "events_queue.json"
    if not queue_path.exists():
        return None

    try:
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(queue, list) or not queue:
        return None

    # Take the first item from queue
    entry = queue[0]
    ticker = entry.get("ticker", "").upper()

    if not ticker:
        return None

    reason = entry.get("reason", "Queued via events_queue.json")

    # Remove from queue
    remaining = queue[1:]
    queue_path.write_text(
        json.dumps(remaining, indent=2) + "\n", encoding="utf-8"
    )

    if ticker in universe_by_ticker:
        co = universe_by_ticker[ticker]
        return CompanySelection(
            ticker=ticker,
            company_name=co["company"],
            sector=co["sector"],
            cik=co["cik"],
            selection_reason=reason,
        )

    return CompanySelection(
        ticker=ticker,
        company_name=entry.get("company", ticker),
        sector=entry.get("sector", "Unknown"),
        cik=entry.get("cik", ""),
        selection_reason=reason,
    )


def _sector_rotation_fallback(
    universe: list[dict],
    analyzed_log: dict,
) -> CompanySelection:
    """Pick the company with the oldest or no analysis (sector rotation)."""
    # Score each company: never analyzed = highest priority,
    # then oldest analysis date
    scored = []
    for co in universe:
        ticker = co["ticker"]
        last_date = _last_analyzed_date(ticker, analyzed_log)
        if last_date is None:
            # Never analyzed -- top priority, use ticker for deterministic ordering
            score = datetime.min
        else:
            score = last_date
        scored.append((score, ticker, co))

    # Sort by score ascending (oldest/never first), then ticker for stability
    scored.sort(key=lambda x: (x[0], x[1]))

    _, ticker, co = scored[0]
    last = _last_analyzed_date(ticker, analyzed_log)
    if last is None:
        reason = "Never previously analyzed (sector rotation)"
    else:
        reason = f"Oldest analysis in rotation (last: {last.date().isoformat()})"

    return CompanySelection(
        ticker=ticker,
        company_name=co["company"],
        sector=co["sector"],
        cik=co["cik"],
        selection_reason=reason,
    )
