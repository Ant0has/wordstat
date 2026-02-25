import csv
from collections import Counter

INPUT = r"C:\Users\furse\Downloads\wordstatapi\final_scoring.csv"
DIRECT_SEGMENTS = {"SEO_GOLD_DIRECT", "SEO_INVEST_DIRECT", "DIRECT_ONLY", "DIRECT_TEST", "DIRECT_LOW"}
COLS = ["page_url", "city_from", "city_to", "price", "total_freq", "segment", "city2city_position", "weakness_score", "demand_score"]

rows = []
with open(INPUT, encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    for r in reader:
        seg = r.get("segment", "").strip()
        if seg in DIRECT_SEGMENTS:
            rows.append(r)

# Sort by segment asc, then total_freq desc (numeric)
rows.sort(key=lambda r: (r["segment"], -int(r["total_freq"] or 0)))

# Print header
print(";".join(COLS))

# Print rows
for r in rows:
    print(";".join(r.get(c, "") for c in COLS))

# Counts per segment
print()
print("=== Counts per segment ===")
counts = Counter(r["segment"] for r in rows)
for seg in sorted(counts):
    print(f"  {seg}: {counts[seg]}")
print(f"  TOTAL: {len(rows)}")
