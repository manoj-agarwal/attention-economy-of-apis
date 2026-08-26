#!/usr/bin/env python3
"""Draw the catalog-cost and tool-count histograms from data/results.csv.

Usage: python 03_make_charts.py
Outputs: charts/catalog_cost_hist.png, charts/tool_count_hist.png
"""
import csv
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path("data/results.csv")
CHARTS = Path("charts")


def load_column(field):
    with RESULTS.open(encoding="utf-8") as f:
        return [int(row[field]) for row in csv.DictReader(f) if row.get(field)]


def histogram(values, title, xlabel, outfile):
    med = statistics.median(values)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(values, bins=min(40, max(10, len(values) // 5)))
    ax.axvline(med, linestyle="--", linewidth=2)
    ax.annotate(f"median = {med:,.0f}", xy=(med, ax.get_ylim()[1] * 0.9),
                xytext=(8, 0), textcoords="offset points")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("number of servers")
    fig.tight_layout()
    CHARTS.mkdir(exist_ok=True)
    fig.savefig(CHARTS / outfile, dpi=200)
    plt.close(fig)
    print(f"wrote charts/{outfile}")


def main():
    costs = load_column("catalog_tokens")
    counts = load_column("n_tools")
    if not costs:
        print("No data in data/results.csv — run 02_count_tokens.py first.")
        return
    histogram(costs,
              "The cover charge: token cost of the tool catalog, per server",
              "tokens consumed before the first user message", 
              "catalog_cost_hist.png")
    histogram(counts,
              "Tools presented per server",
              "number of tools in the catalog",
              "tool_count_hist.png")


if __name__ == "__main__":
    main()
