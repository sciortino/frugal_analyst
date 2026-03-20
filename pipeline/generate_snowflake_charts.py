"""Generate Snowflake analysis charts for the 2026-03-19 blog post."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# Match pipeline style exactly
COLORS = {
    "primary": "#2D6A9F",
    "secondary": "#D4763C",
    "tertiary": "#4A9B6E",
    "quaternary": "#8B5E9B",
    "quinary": "#C45B5B",
    "senary": "#7A8B99",
}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "axes.facecolor": "white",
    "axes.grid": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "figure.facecolor": "white",
    "figure.figsize": (8, 5),
    "figure.dpi": 150,
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#CCCCCC",
})

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "site" / "public" / "charts" / "2026-03-19"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def chart_opex_breakdown():
    """Chart 1: Snowflake OpEx breakdown as % of revenue, FY2024-FY2026."""
    fiscal_years = ["FY2024\n($2.81B)", "FY2025\n($3.62B)", "FY2026\n($4.68B)"]

    # OpEx as % of revenue
    rd = [40.0, 39.0, 42.0]
    sm = [39.0, 37.0, 35.4]
    ga = [8.0, 7.0, 6.0]

    x = np.arange(len(fiscal_years))
    width = 0.55

    fig, ax = plt.subplots()

    # Stacked bars
    bars_rd = ax.bar(x, rd, width, label="R&D", color=COLORS["primary"], alpha=0.85,
                     edgecolor="white", linewidth=0.5)
    bars_sm = ax.bar(x, sm, width, bottom=rd, label="Sales & Marketing",
                     color=COLORS["secondary"], alpha=0.85, edgecolor="white", linewidth=0.5)
    bottom_ga = [r + s for r, s in zip(rd, sm)]
    bars_ga = ax.bar(x, ga, width, bottom=bottom_ga, label="G&A",
                     color=COLORS["tertiary"], alpha=0.85, edgecolor="white", linewidth=0.5)

    # Add value labels inside each segment
    for i in range(len(fiscal_years)):
        # R&D label
        ax.text(x[i], rd[i] / 2, f"{rd[i]:.0f}%", ha="center", va="center",
                fontsize=10, fontweight="bold", color="white")
        # S&M label
        ax.text(x[i], rd[i] + sm[i] / 2, f"{sm[i]:.1f}%", ha="center", va="center",
                fontsize=10, fontweight="bold", color="white")
        # G&A label
        ax.text(x[i], bottom_ga[i] + ga[i] / 2, f"{ga[i]:.0f}%", ha="center", va="center",
                fontsize=9, fontweight="bold", color="white")

    # Total labels on top
    totals = [r + s + g for r, s, g in zip(rd, sm, ga)]
    for i, total in enumerate(totals):
        ax.text(x[i], total + 1.0, f"{total:.1f}%", ha="center", va="bottom",
                fontsize=10, fontweight="bold", color="#333333")

    ax.set_title("Snowflake (SNOW): Operating Expense Breakdown")
    ax.set_ylabel("% of Revenue")
    ax.set_xticks(x)
    ax.set_xticklabels(fiscal_years, fontsize=10)
    ax.set_ylim(0, 105)
    ax.legend(loc="upper right", fontsize=9)

    filepath = OUTPUT_DIR / "snow_opex_breakdown.png"
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {filepath}")


def chart_docs_influence():
    """Chart 2: Documentation influence on enterprise purchase decisions."""
    labels = [
        "Docs essential to\nclosing deals",
        "Review docs before\npurchasing",
        "Docs influence\npurchase decision",
    ]
    values = [51, 80, 88]

    fig, ax = plt.subplots()

    bars = ax.barh(labels, values, height=0.5, color=COLORS["quaternary"], alpha=0.85,
                   edgecolor="white", linewidth=0.5)

    # Add value labels at end of bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{val}%", ha="left", va="center", fontsize=11, fontweight="bold",
                color="#333333")

    ax.set_title("Documentation in Enterprise Purchase Decisions (2026)")
    ax.set_xlabel("% of Enterprise Buyers")
    ax.set_xlim(0, 100)
    ax.invert_yaxis()  # Highest value on top

    # Remove y-axis grid for horizontal bar chart (keep x-axis grid)
    ax.yaxis.grid(False)

    filepath = OUTPUT_DIR / "snow_docs_influence.png"
    fig.savefig(filepath, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {filepath}")


if __name__ == "__main__":
    chart_opex_breakdown()
    chart_docs_influence()
    print("Done.")
