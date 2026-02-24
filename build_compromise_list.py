#!/usr/bin/env python3
"""
Build compromise route list for city2city.ru
=============================================

Decision logic:
  1. RETURN_FULL  (whitelist + sitemap):
       - freq > 10  OR  city2city in TOP-10
       - OR route belongs to an "actionable" segment (non-LOW_PRIORITY):
         SEO_GOLD_NEW, SEO_INVEST_NEW, SEO_HARD_NEW,
         SEO_AUTOPILOT_NEW, POTENTIAL_DIRECT_NEW
  2. RETURN_NOINDEX  (whitelist only, no sitemap):
       - freq 1-10  AND  city2city in TOP-30 (positions 11-30)
       - (routes already captured by rule 1 are excluded)
  3. SKIP  (leave on 404):
       - everything else
"""

import csv
import os

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"
INPUT_FILE = os.path.join(BASE_DIR, "scoring_109k.csv")

OUTPUT_FULL = os.path.join(BASE_DIR, "compromise_return_full.txt")
OUTPUT_NOINDEX = os.path.join(BASE_DIR, "compromise_return_noindex.txt")
OUTPUT_SKIP = os.path.join(BASE_DIR, "compromise_skip.txt")

ACTIONABLE_SEGMENTS = {
    "SEO_GOLD_NEW",
    "SEO_INVEST_NEW",
    "SEO_HARD_NEW",
    "SEO_AUTOPILOT_NEW",
    "POTENTIAL_DIRECT_NEW",
}


def parse_position(raw: str):
    """Parse city2city_position; return None if empty or unparseable."""
    raw = raw.strip()
    if raw in ("", "None", "nan"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def classify_route(freq, position, segment):
    """
    Return one of: RETURN_FULL, RETURN_NOINDEX, SKIP
    """
    # Rule 1a: actionable segment -> always RETURN_FULL
    if segment in ACTIONABLE_SEGMENTS:
        return "RETURN_FULL"

    # Rule 1b: freq > 10 -> RETURN_FULL
    if freq > 10:
        return "RETURN_FULL"

    # Rule 1c: city2city in TOP-10 -> RETURN_FULL
    if position is not None and position <= 10:
        return "RETURN_FULL"

    # Rule 2: freq 1-10 AND city2city in TOP-30 (positions 11-30) -> RETURN_NOINDEX
    if 1 <= freq <= 10 and position is not None and position <= 30:
        return "RETURN_NOINDEX"

    # Rule 3: everything else -> SKIP
    return "SKIP"


def main():
    return_full = []
    return_noindex = []
    skip = []

    # Detailed counters for summary
    full_by_actionable = 0
    full_by_freq = 0
    full_by_top10 = 0
    full_by_multiple = 0  # matched more than one FULL criterion
    noindex_count = 0
    skip_count = 0

    with open(INPUT_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            slug = row["slug"].strip()
            freq = int(row["freq"])
            position = parse_position(row["city2city_position"])
            segment = row["segment"].strip()

            decision = classify_route(freq, position, segment)

            if decision == "RETURN_FULL":
                return_full.append(slug)

                # Count reason breakdown
                reasons = 0
                if segment in ACTIONABLE_SEGMENTS:
                    reasons += 1
                    full_by_actionable += 1
                if freq > 10:
                    reasons += 1
                    full_by_freq += 1
                if position is not None and position <= 10:
                    reasons += 1
                    full_by_top10 += 1
                if reasons > 1:
                    full_by_multiple += 1

            elif decision == "RETURN_NOINDEX":
                return_noindex.append(slug)
                noindex_count += 1

            else:
                skip.append(slug)
                skip_count += 1

    # Write output files
    for filepath, slugs in [
        (OUTPUT_FULL, return_full),
        (OUTPUT_NOINDEX, return_noindex),
        (OUTPUT_SKIP, skip),
    ]:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(slugs))
            if slugs:
                f.write("\n")

    total = len(return_full) + len(return_noindex) + len(skip)

    # Summary
    print("=" * 60)
    print("COMPROMISE ROUTE LIST - SUMMARY")
    print("=" * 60)
    print(f"Total routes analysed:          {total:>6}")
    print()
    print(f"RETURN_FULL  (whitelist+sitemap): {len(return_full):>5}")
    print(f"  +-- by actionable segment:      {full_by_actionable:>5}")
    print(f"  +-- by freq > 10:               {full_by_freq:>5}")
    print(f"  +-- by city2city TOP-10:        {full_by_top10:>5}")
    print(f"  +-- (matched multiple criteria):{full_by_multiple:>5}")
    print()
    print(f"RETURN_NOINDEX (whitelist only):  {len(return_noindex):>5}")
    print(f"  +-- freq 1-10 & TOP-30 pos:     {noindex_count:>5}")
    print()
    print(f"SKIP (stay on 404):              {len(skip):>5}")
    print()
    print("-" * 60)
    print("Output files:")
    print(f"  {OUTPUT_FULL}")
    print(f"    -> {len(return_full)} slugs")
    print(f"  {OUTPUT_NOINDEX}")
    print(f"    -> {len(return_noindex)} slugs")
    print(f"  {OUTPUT_SKIP}")
    print(f"    -> {len(skip)} slugs")
    print("=" * 60)


if __name__ == "__main__":
    main()
