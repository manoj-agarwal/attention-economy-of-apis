#!/usr/bin/env python3
"""Count the token cost of each collected tool catalog.

Usage: python 02_count_tokens.py [input_dir]   (default: data/raw)

Serializes every tool to compact JSON (identical recipe for all servers) and
counts tokens with tiktoken o200k_base. If the tokenizer vocabulary is
unavailable, falls back to a crude character-based estimate and labels every
affected row in the count_method column. Only tiktoken rows are quotable.
Writes data/results.csv and prints summary statistics.
"""
import csv
import json
import statistics
import sys
from pathlib import Path

RESULTS_PATH = Path("data/results.csv")

FIELDS = [
    "name", "source_url", "fetched_at", "n_tools", "catalog_tokens",
    "median_tool_tokens", "largest_tool_tokens", "pct_params_described",
    "any_enum_constraint", "longest_description_chars", "count_method",
]


def build_counter():
    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        return (lambda s: len(enc.encode(s))), "tiktoken:o200k_base"
    except Exception as exc:  # vocabulary download blocked, offline, etc.
        print(f"WARNING: tiktoken unavailable ({type(exc).__name__}). "
              "Falling back to chars/3.5 ESTIMATE — not quotable.")
        return (lambda s: max(1, round(len(s) / 3.5))), "estimate:chars/3.5"


def compact(obj):
    """One serialization recipe for every server: compact, sorted, unicode kept."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def schema_stats(tools):
    """Share of top-level parameters carrying a description; any enum; longest desc."""
    total = described = 0
    any_enum = False
    longest_desc = 0
    for tool in tools:
        desc = tool.get("description") or ""
        longest_desc = max(longest_desc, len(desc))
        schema = tool.get("inputSchema") or tool.get("input_schema") or {}
        props = schema.get("properties") or {}
        for _, spec in props.items():
            if not isinstance(spec, dict):
                continue
            total += 1
            if spec.get("description"):
                described += 1
            if "enum" in spec:
                any_enum = True
    pct = round(100 * described / total, 1) if total else ""
    return pct, any_enum, longest_desc


def main():
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw")
    count, method = build_counter()
    rows = []
    for path in sorted(input_dir.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"SKIP {path.name}: not valid JSON")
            continue
        tools = doc.get("tools")
        if not isinstance(tools, list) or not tools:
            print(f"SKIP {path.name}: no tools array")
            continue
        per_tool = [count(compact(t)) for t in tools]
        pct_desc, any_enum, longest = schema_stats(tools)
        rows.append({
            "name": doc.get("name", path.stem),
            "source_url": doc.get("source_url", ""),
            "fetched_at": doc.get("fetched_at", ""),
            "n_tools": len(tools),
            "catalog_tokens": count(compact(tools)),
            "median_tool_tokens": round(statistics.median(per_tool)),
            "largest_tool_tokens": max(per_tool),
            "pct_params_described": pct_desc,
            "any_enum_constraint": any_enum,
            "longest_description_chars": longest,
            "count_method": method,
        })

    if not rows:
        print(f"No usable catalogs found in {input_dir}/")
        return

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    costs = sorted(r["catalog_tokens"] for r in rows)
    tool_counts = [r["n_tools"] for r in rows]
    pct90 = costs[max(0, round(0.9 * len(costs)) - 1)]
    print(f"\nServers measured : {len(rows)}   (method: {method})")
    print(f"Median tool count : {statistics.median(tool_counts)}")
    print(f"Median catalog cost: {statistics.median(costs)} tokens")
    print(f"90th percentile    : {pct90} tokens")
    print(f"Results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
