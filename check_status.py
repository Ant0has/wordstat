import json, os

BASE = r"C:\Users\furse\Downloads\wordstatapi"

# Wordstat progress
ws = json.load(open(os.path.join(BASE, "ws_cloud_progress.json"), encoding="utf-8"))
ws_done = len(ws["collected"])

# WS results CSV lines
ws_csv = os.path.join(BASE, "ws_cloud_results.csv")
with open(ws_csv, "r", encoding="utf-8-sig") as f:
    ws_lines = sum(1 for _ in f) - 1

# SERP progress
serp_file = os.path.join(BASE, "serp_progress.json")
serp_done = 0
serp_ops = 0
if os.path.exists(serp_file):
    sp = json.load(open(serp_file, encoding="utf-8"))
    serp_done = len(sp.get("collected", []))
    serp_ops = len(sp.get("operations", {}))

# SERP results CSV
serp_csv = os.path.join(BASE, "serp_results.csv")
serp_csv_lines = 0
if os.path.exists(serp_csv):
    with open(serp_csv, "r", encoding="utf-8-sig") as f:
        serp_csv_lines = sum(1 for _ in f) - 1

# Count nonzero in WS results
nonzero = 0
with open(ws_csv, "r", encoding="utf-8-sig") as f:
    import csv
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        tc = int(row["total_count"]) if row["total_count"] else 0
        if tc > 0:
            nonzero += 1

print("=" * 50)
print("PIPELINE STATUS (4204 routes)")
print("=" * 50)
print(f"Wordstat Cloud:    {ws_done}/4204 ({100*ws_done/4204:.1f}%)")
print(f"WS results CSV:    {ws_lines} data rows")
print(f"WS nonzero (>0):   {nonzero}")
print()
print(f"SERP collected:    {serp_done}/4204")
print(f"SERP pending ops:  {serp_ops}")
print(f"SERP results CSV:  {serp_csv_lines} rows")
print()
if ws_done >= 4204:
    print(">> Wordstat COMPLETE!")
if serp_done > 0:
    print(f">> SERP in progress: {serp_done/4204*100:.1f}%")
elif serp_ops > 0:
    print(f">> SERP: {serp_ops} operations pending collection")
else:
    print(">> SERP not started yet")
