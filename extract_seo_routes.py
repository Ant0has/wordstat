#!/usr/bin/env python3
"""
Extract SEO route data from final_scoring.csv
Segments: SEO_GOLD, SEO_GOLD_DIRECT, SEO_INVEST, SEO_INVEST_DIRECT,
          SEO_DEFEND, SEO_HARD, SEO_AUTOPILOT, SEO_MONITOR
"""

import csv
from collections import defaultdict

INPUT = r"C:\Users\furse\Downloads\wordstatapi\final_scoring.csv"

SEO_SEGMENTS = {
    "SEO_GOLD", "SEO_GOLD_DIRECT",
    "SEO_INVEST", "SEO_INVEST_DIRECT",
    "SEO_DEFEND", "SEO_HARD",
    "SEO_AUTOPILOT", "SEO_MONITOR",
}

COLUMNS = [
    "page_url", "city_from", "city_to", "price",
    "total_freq", "segment", "city2city_position",
    "weakness_score", "demand_score", "top10_domains",
]

SEPARATOR = "=" * 120

def read_data():
    rows = []
    with open(INPUT, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if row["segment"] in SEO_SEGMENTS:
                rows.append(row)
    return rows

def sort_key(row):
    seg_order = [
        "SEO_GOLD", "SEO_GOLD_DIRECT",
        "SEO_INVEST", "SEO_INVEST_DIRECT",
        "SEO_DEFEND", "SEO_HARD",
        "SEO_AUTOPILOT", "SEO_MONITOR",
    ]
    seg_idx = seg_order.index(row["segment"]) if row["segment"] in seg_order else 99
    try:
        freq = float(row["total_freq"])
    except (ValueError, TypeError):
        freq = 0.0
    return (seg_idx, -freq)

def print_header():
    print(";".join(COLUMNS))

def print_row(row):
    print(";".join(str(row.get(c, "")) for c in COLUMNS))

def main():
    rows = read_data()
    rows.sort(key=sort_key)

    # ---- FULL LISTING (all SEO routes) ----
    print(SEPARATOR)
    print("ALL SEO ROUTES (sorted by segment, then total_freq descending)")
    print(SEPARATOR)
    print_header()
    for r in rows:
        print_row(r)

    # ---- COUNTS PER SEGMENT ----
    counts = defaultdict(int)
    for r in rows:
        counts[r["segment"]] += 1

    print()
    print(SEPARATOR)
    print("COUNTS PER SEGMENT")
    print(SEPARATOR)
    seg_order = [
        "SEO_GOLD", "SEO_GOLD_DIRECT",
        "SEO_INVEST", "SEO_INVEST_DIRECT",
        "SEO_DEFEND", "SEO_HARD",
        "SEO_AUTOPILOT", "SEO_MONITOR",
    ]
    total = 0
    for seg in seg_order:
        c = counts.get(seg, 0)
        total += c
        print(f"  {seg:<25s} {c:>6d}")
    print(f"  {'TOTAL':<25s} {total:>6d}")

    # ---- SEO_GOLD & SEO_GOLD_DIRECT: full details ----
    gold = [r for r in rows if r["segment"] in ("SEO_GOLD", "SEO_GOLD_DIRECT")]
    print()
    print(SEPARATOR)
    print(f"SEO_GOLD + SEO_GOLD_DIRECT — ALL ROUTES ({len(gold)} total)")
    print(SEPARATOR)
    print_header()
    for r in gold:
        print_row(r)

    # ---- SEO_INVEST & SEO_INVEST_DIRECT: top-20 by demand_score ----
    invest = [r for r in rows if r["segment"] in ("SEO_INVEST", "SEO_INVEST_DIRECT")]
    invest.sort(key=lambda r: -float(r.get("demand_score") or 0))
    top20 = invest[:20]
    print()
    print(SEPARATOR)
    print(f"SEO_INVEST + SEO_INVEST_DIRECT — TOP 20 by demand_score (out of {len(invest)})")
    print(SEPARATOR)
    print_header()
    for r in top20:
        print_row(r)

    print()
    print("Done.")

if __name__ == "__main__":
    main()
