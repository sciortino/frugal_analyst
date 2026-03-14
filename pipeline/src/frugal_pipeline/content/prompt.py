"""Prompt construction for Claude API content generation."""

from __future__ import annotations

from pathlib import Path

from frugal_pipeline.models import FinancialMetrics, LaborMetrics, MacroContext


def build_system_prompt() -> str:
    """Build the system prompt defining The Frugal Analyst voice and format."""
    return """You are The Frugal Analyst, writing a data-driven analysis of a public company through a labor economics lens.

## Voice & Tone
- Data-first, analytical, measured editorial commentary
- Informed but accessible -- explain financial concepts when they first appear
- Skeptical of corporate narratives; let the numbers tell the story
- Occasional dry wit, never sarcastic or dismissive toward workers
- No stock recommendations, no "buy/sell" language

## Structure (follow this framework)
1. **Lead with the most striking data point** -- the single number that tells the biggest story
2. **Financial Performance** -- revenue trajectory, margins, profitability trends
3. **The Labor Dimension** -- headcount vs. revenue growth, profit per employee, estimated labor cost dynamics
4. **Macro Context** -- how does this company sit within broader employment and wage trends?
5. **Implications** -- what does this mean for workers, investors, and the broader economy?

## Formatting Requirements
- Post length: 1,200-1,800 words
- Include a "Key Metrics" bulleted summary near the top (after the opening paragraph)
- Cite specific numbers with sources (e.g., "per FMP data" or "SEC filings")
- Reference the included charts by filename (the pipeline will fix paths)
- Include a "Methodology & Data Sources" section at the end listing:
  - Financial Modeling Prep (FMP) for financial statements and employee data
  - SEC EDGAR for XBRL-reported company facts
  - Federal Reserve Economic Data (FRED) for macroeconomic indicators
  - Bureau of Labor Statistics (BLS) for sector employment data
- No clickbait titles or sensational language
- Output format: Markdown body text only (no YAML frontmatter -- the pipeline adds that)
- Do NOT wrap the output in markdown code fences
- Use ## for major sections and ### for subsections"""


def build_data_prompt(
    company_name: str,
    ticker: str,
    sector: str,
    selection_reason: str,
    financial_metrics: FinancialMetrics,
    labor_metrics: LaborMetrics,
    macro_context: MacroContext,
    chart_paths: list[str],
) -> str:
    """Build the data prompt packaging all metrics for Claude.

    Formats raw data into a readable text block that Claude can
    use to write an informed analysis.
    """
    chart_filenames = [Path(p).name for p in chart_paths]

    # Format revenue in billions/millions
    def fmt_revenue(val: float) -> str:
        if abs(val) >= 1e9:
            return f"${val / 1e9:.2f}B"
        if abs(val) >= 1e6:
            return f"${val / 1e6:.1f}M"
        return f"${val:,.0f}"

    def fmt_per_emp(val: float) -> str:
        if abs(val) >= 1e6:
            return f"${val / 1e6:.2f}M"
        if abs(val) >= 1e3:
            return f"${val / 1e3:.0f}K"
        return f"${val:,.0f}"

    # Build financial summary table
    fin_rows = []
    for i, year in enumerate(financial_metrics.years):
        rev = fmt_revenue(financial_metrics.revenue_trend[i]) if i < len(financial_metrics.revenue_trend) else "N/A"
        op_m = f"{financial_metrics.operating_margin_trend[i]:.1f}%" if i < len(financial_metrics.operating_margin_trend) else "N/A"
        net_m = f"{financial_metrics.net_margin_trend[i]:.1f}%" if i < len(financial_metrics.net_margin_trend) else "N/A"
        emp = f"{financial_metrics.employee_counts[i]:,}" if i < len(financial_metrics.employee_counts) and financial_metrics.employee_counts[i] > 0 else "N/A"
        rpe = fmt_per_emp(financial_metrics.revenue_per_employee[i]) if i < len(financial_metrics.revenue_per_employee) and financial_metrics.revenue_per_employee[i] > 0 else "N/A"
        ppe = fmt_per_emp(financial_metrics.profit_per_employee[i]) if i < len(financial_metrics.profit_per_employee) and financial_metrics.profit_per_employee[i] > 0 else "N/A"
        rev_g = f"{financial_metrics.revenue_growth_yoy[i]:.1f}%" if i < len(financial_metrics.revenue_growth_yoy) and financial_metrics.revenue_growth_yoy[i] is not None else "N/A"
        fin_rows.append(f"  {year}: Revenue={rev}, OpMargin={op_m}, NetMargin={net_m}, Employees={emp}, Rev/Emp={rpe}, Profit/Emp={ppe}, RevGrowth={rev_g}")

    fin_table = "\n".join(fin_rows)

    # Build labor metrics summary
    labor_lines = []
    for entry in labor_metrics.headcount_growth_vs_revenue_growth:
        hc_g = entry.get("headcount_growth_pct")
        rev_g = entry.get("revenue_growth_pct")
        hc_str = f"{hc_g:+.1f}%" if hc_g is not None else "N/A"
        rev_str = f"{rev_g:+.1f}%" if rev_g is not None else "N/A"
        labor_lines.append(f"  {entry['year']}: Headcount Growth={hc_str}, Revenue Growth={rev_str}")

    labor_growth_table = "\n".join(labor_lines) if labor_lines else "  No year-over-year data available"

    # Revenue per employee indexed
    rpe_indexed_str = ", ".join(
        f"{y}: {v:.0f}" for y, v in zip(labor_metrics.years, labor_metrics.revenue_per_employee_indexed)
    )

    # Notable patterns
    patterns_str = "\n".join(f"  - {p}" for p in labor_metrics.notable_patterns) if labor_metrics.notable_patterns else "  None detected"

    # Macro context
    macro_lines = []
    if macro_context.unemployment_rate is not None:
        macro_lines.append(f"National Unemployment Rate: {macro_context.unemployment_rate:.1f}%")
    if macro_context.sector_employment_growth is not None:
        macro_lines.append(f"{macro_context.sector_name} Sector Employment Growth (YoY): {macro_context.sector_employment_growth:+.1f}%")
    if macro_context.avg_hourly_earnings_growth is not None:
        macro_lines.append(f"Average Hourly Earnings Growth (YoY): {macro_context.avg_hourly_earnings_growth:+.1f}%")
    if macro_context.real_wage_growth is not None:
        macro_lines.append(f"Real Wage Growth (YoY): {macro_context.real_wage_growth:+.1f}%")
    if macro_context.labor_share_national is not None:
        macro_lines.append(f"National Labor Share of Output: {macro_context.labor_share_national:.1f}%")
    macro_str = "\n".join(f"  {l}" for l in macro_lines) if macro_lines else "  No macro data available"

    # Charts
    charts_str = "\n".join(f"  - {f}" for f in chart_filenames) if chart_filenames else "  No charts generated"

    return f"""## Company Analysis Data Package

**Company**: {company_name} ({ticker})
**Sector**: {sector}
**Selection Reason**: {selection_reason}

### Financial Performance (Annual)
{fin_table}

### Headcount vs. Revenue Growth (Year-over-Year)
{labor_growth_table}

### Revenue per Employee Index (Base Year = 100)
  {rpe_indexed_str}

### Estimated Labor Cost Indicators
  SGA/Revenue Ratios: {', '.join(f'{y}: {r:.1f}%' if r is not None else f'{y}: N/A' for y, r in zip(labor_metrics.years, labor_metrics.estimated_labor_cost_ratio))}
  Profit-to-SGA Ratios: {', '.join(f'{y}: {r:.2f}x' if r is not None else f'{y}: N/A' for y, r in zip(labor_metrics.years, labor_metrics.profit_to_compensation_ratio))}

### Notable Labor Patterns Detected
{patterns_str}

### Macroeconomic Context
{macro_str}

### Available Charts (reference these in the analysis)
{charts_str}

Write the analysis now, following the system prompt guidelines."""
