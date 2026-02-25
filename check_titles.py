import os
from collections import Counter

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"

prefixes = Counter()
total = 0
taxi_count = 0
parseable = 0
not_parseable = []

with open(os.path.join(BASE_DIR, "new_routes_titles.tsv"), "r", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) < 2:
            continue
        url, title = parts[0], parts[1]
        total += 1

        prefix = title.split()[0] if title.split() else ""
        prefixes[prefix] += 1

        if title.startswith("Такси "):
            taxi_count += 1
            # Parse: "Такси CityFrom CityTo" — but cities can have spaces!
            # We know city_from from our data, or we can use the title as the Wordstat query
            # For Wordstat, we just need "такси {city_from} {city_to}" = lowercase(title)
            parseable += 1
        else:
            if len(not_parseable) < 20:
                not_parseable.append((url, title))

print(f"Total: {total}")
print(f"Starting with 'Такси ': {taxi_count} ({taxi_count/total*100:.1f}%)")
print(f"\nTitle prefixes:")
for pref, cnt in prefixes.most_common(10):
    print(f"  {pref:20s} {cnt:>6}")
print(f"\nNon-taxi titles (first 20):")
for url, title in not_parseable:
    print(f"  {url:50s} | {title}")
