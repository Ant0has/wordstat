from collections import Counter
import os

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"
prefixes = Counter()
total = 0
with_prefix = 0

with open(os.path.join(BASE_DIR, "all_routes_db.tsv"), "r", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        city_data = parts[1]
        p2 = city_data.split("Россия,")
        if len(p2) >= 2:
            ct = p2[1].split(",")[0].strip()
            total += 1
            for pref in ["посёлок", "поселок", "село", "деревня", "станица", "рабочий", "хутор", "аул", "город "]:
                if ct.lower().startswith(pref):
                    prefixes[pref] += 1
                    with_prefix += 1
                    break

print(f"Total routes with city_to: {total}")
print(f"With settlement prefix: {with_prefix}")
print(f"Without prefix (clean city names): {total - with_prefix}")
for pref, cnt in prefixes.most_common():
    print(f"  {pref:30s} {cnt:>6}")
