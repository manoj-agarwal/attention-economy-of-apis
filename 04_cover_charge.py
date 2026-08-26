#!/usr/bin/env python3
"""Tokenizer-true cover charge for the two demo surfaces.

Usage: python 04_cover_charge.py
Outputs: stdout only. Writes nothing.

The serialization recipe and the token counter are imported from
02_count_tokens.py rather than reimplemented, so this figure cannot drift from
the recipe used for every catalog in data/results.csv. Only tiktoken counts are
quotable; if the tokenizer is unavailable this script says so loudly and exits
non-zero rather than letting an estimate pass as a headline number.
"""
import csv
import importlib.util
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNTER_SRC = HERE / "02_count_tokens.py"
RESULTS = HERE / "data" / "results.csv"
RAW = HERE / "data" / "raw"
SURFACE_DIR = HERE / "demo"

# The sensitivity adjustment models only these schema-internal keys.
ENVELOPE_KEYS = {"$schema": "http://json-schema.org/draft-07/schema#",
                 "additionalProperties": False}
# Tool-level keys real catalogs carry that the adjustment does NOT model.
UNMODELLED_KEYS = ["annotations", "outputSchema", "title", "execution", "_meta"]


def load_counter_module():
    """Import 02_count_tokens.py by path; its name starts with a digit."""
    spec = importlib.util.spec_from_file_location("count_tokens", COUNTER_SRC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_surfaces():
    sys.path.insert(0, str(SURFACE_DIR))
    import surface_a
    import surface_b
    return surface_a, surface_b


def share_at_or_below(values, target):
    """Percent of the corpus at or below target, on an already-sorted list."""
    return 100.0 * sum(1 for v in values if v <= target) / len(values)


def corpus_columns():
    with RESULTS.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows, {
        "catalog_tokens": sorted(int(r["catalog_tokens"]) for r in rows),
        "n_tools": sorted(int(r["n_tools"]) for r in rows),
        "median_tool_tokens": sorted(int(r["median_tool_tokens"]) for r in rows),
    }


def envelope_prevalence():
    """How often do real catalogs carry the keys we model, and the ones we don't?"""
    import json
    tools_seen = 0
    schema_keys = Counter()
    tool_keys = Counter()
    for path in sorted(RAW.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        tools = doc.get("tools")
        if not isinstance(tools, list) or not tools:
            continue
        for tool in tools:
            tools_seen += 1
            for key in tool:
                tool_keys[key] += 1
            schema = tool.get("inputSchema") or tool.get("input_schema") or {}
            if isinstance(schema, dict):
                for key in schema:
                    schema_keys[key] += 1
    return tools_seen, schema_keys, tool_keys


def with_envelope(tools):
    """Surface tools re-shaped as a registry catalog would carry them."""
    out = []
    for tool in tools:
        schema = dict(tool["input_schema"])
        schema.update(ENVELOPE_KEYS)
        out.append({"name": tool["name"], "description": tool["description"],
                    "inputSchema": schema})
    return out


def main():
    counter = load_counter_module()
    count, method = counter.build_counter()
    surface_a, surface_b = load_surfaces()

    print("=" * 72)
    print("COVER CHARGE — tokenizer-true count for the demo surfaces")
    print("=" * 72)
    print(f"  counter    : {method}   (imported from {COUNTER_SRC.name})")
    print(f"  recipe     : {counter.compact.__doc__.splitlines()[0]}")
    quotable = method.startswith("tiktoken")
    if not quotable:
        print()
        print("  !! NOT QUOTABLE: the tokenizer was unavailable and these are")
        print("  !! character estimates. Estimate-derived figures must not feed a")
        print("  !! headline statistic. Fix the tokenizer and re-run.")

    surfaces = [("Surface A (endpoint wrapper)", surface_a.TOOLS),
                ("Surface B (task tools)", surface_b.TOOLS)]
    measured = {}
    print()
    print("  MEASURED")
    print(f"  {'surface':<30} {'tools':>6} {'cover charge':>13} {'median tok/tool':>16}")
    for label, tools in surfaces:
        per_tool = [count(counter.compact(t)) for t in tools]
        total = count(counter.compact(tools))
        measured[label] = (len(tools), total, round(statistics.median(per_tool)))
        print(f"  {label:<30} {len(tools):>6} {total:>13,} {round(statistics.median(per_tool)):>16}")
    a_total = measured[surfaces[0][0]][1]
    b_total = measured[surfaces[1][0]][1]
    print(f"  ratio A/B  : {a_total / b_total:.2f}x")

    rows, cols = corpus_columns()
    methods = Counter(r["count_method"] for r in rows)
    costs = cols["catalog_tokens"]
    median_cost = statistics.median(costs)
    p90 = costs[max(0, round(0.9 * len(costs)) - 1)]   # same formula as 02_count_tokens.py

    print()
    print("=" * 72)
    print("AGAINST THE FIELD (data/results.csv)")
    print("=" * 72)
    print(f"  corpus     : {len(rows)} catalogs, count_method {dict(methods)}")
    print(f"  median cover charge : {median_cost:,.0f} tokens")
    print(f"  90th percentile     : {p90:,} tokens")
    print(f"  median tool count   : {statistics.median(cols['n_tools']):,.0f}")
    print(f"  median tok/tool     : {statistics.median(cols['median_tool_tokens']):,.0f}")
    print()
    for label, _ in surfaces:
        _, total, _ = measured[label]
        print(f"  {label:<30} {total:>6,} tokens | percentile {share_at_or_below(costs, total):>5.0f}%"
              f" | {total / median_cost:.2f}x the field median")

    print()
    print("=" * 72)
    print("COMPOSITION — the part most likely to be challenged")
    print("=" * 72)
    print("  A catalog can sit near the median in total while being atypical in")
    print("  both of its factors. Side by side:")
    print()
    print(f"  {'surface':<30} {'tools':>6} {'pct-ile':>8}   {'tok/tool':>9} {'pct-ile':>8}")
    for label, _ in surfaces:
        n_tools, _, med_tool = measured[label]
        print(f"  {label:<30} {n_tools:>6} {share_at_or_below(cols['n_tools'], n_tools):>7.0f}%"
              f"   {med_tool:>9} {share_at_or_below(cols['median_tool_tokens'], med_tool):>7.0f}%")

    print()
    print("=" * 72)
    print("SENSITIVITY ANALYSIS — NOT the measured figure")
    print("=" * 72)
    tools_seen, schema_keys, tool_keys = envelope_prevalence()
    print(f"  The measured numbers above are the headline. The corpus rows are real")
    print(f"  MCP catalogs; the surfaces are Anthropic-format lists built locally, so")
    print(f"  they carry less envelope. Modelled adjustment adds these schema keys:")
    for key in ENVELOPE_KEYS:
        seen = schema_keys.get(key, 0)
        print(f"    {key:<22} present on {seen:>5,} of {tools_seen:,} corpus tools "
              f"({100.0 * seen / tools_seen:.0f}%)")
    print("  NOT modelled (so the adjustment is a floor, not a ceiling):")
    for key in UNMODELLED_KEYS:
        seen = tool_keys.get(key, 0)
        print(f"    {key:<22} present on {seen:>5,} of {tools_seen:,} corpus tools "
              f"({100.0 * seen / tools_seen:.0f}%)")
    print()
    for label, tools in surfaces:
        _, total, _ = measured[label]
        adjusted = count(counter.compact(with_envelope(tools)))
        print(f"  {label:<30} measured {total:>6,} -> adjusted {adjusted:>6,} "
              f"({100.0 * (adjusted - total) / total:+.0f}%), "
              f"percentile {share_at_or_below(costs, adjusted):.0f}%, "
              f"{adjusted / median_cost:.2f}x median")

    if not quotable:
        sys.exit(1)


if __name__ == "__main__":
    main()
