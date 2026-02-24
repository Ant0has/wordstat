import csv
import re
from collections import defaultdict

BASE_DIR = r'C:\Users\furse\Downloads\wordstatapi'

# Step 1: Read all rows
with open(BASE_DIR + r'\routes_city2city.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Collect all (city_from, city_to, url_slug) triples
triples = []
for row in rows:
    url = row['page_url'].strip().replace('https://city2city.ru/', '')
    city_from = row['city_from'].strip()
    city_to = row['city_to'].strip()
    triples.append((city_from, city_to, url))

# Build: city_from -> slug prefix
from_prefix = {}
for cf, ct, slug in triples:
    if cf and ct and cf not in from_prefix:
        same_from = [(c2, s) for c1, c2, s in triples if c1 == cf and c2]
        if len(same_from) >= 2:
            slugs = [s for _, s in same_from]
            prefix = slugs[0]
            for s in slugs[1:]:
                while not s.startswith(prefix):
                    prefix = prefix[:-1]
                    if '-' in prefix:
                        prefix = prefix[:prefix.rindex('-')+1]
                    else:
                        prefix = ''
                        break
            if prefix and prefix.endswith('-'):
                from_prefix[cf] = prefix
            elif prefix:
                from_prefix[cf] = prefix + '-'

# Build city_to slug -> city_name mapping
to_slug_map = {}
for cf, ct, slug in triples:
    if cf and ct and cf in from_prefix:
        prefix = from_prefix[cf]
        if slug.startswith(prefix):
            to_slug = slug[len(prefix):]
            to_slug_map[to_slug] = ct

# Also build for city_from
from_slug_map = {}
for cf, ct, slug in triples:
    if cf and ct:
        for prefix_cf, pref in from_prefix.items():
            if prefix_cf == cf and slug.startswith(pref):
                from_slug = pref.rstrip('-')
                from_slug_map[from_slug] = cf
                break

# Now fix the empty city_to rows
fixed = 0
not_fixed = []
for row in rows:
    if row['city_to'].strip():
        continue
    url = row['page_url'].strip().replace('https://city2city.ru/', '')
    cf = row['city_from'].strip()
    if cf in from_prefix:
        prefix = from_prefix[cf]
        if url.startswith(prefix):
            to_slug = url[len(prefix):]
            if to_slug in to_slug_map:
                row['city_to'] = to_slug_map[to_slug]
                fixed += 1
                continue
    # Fallback: try all known prefixes
    found = False
    for pref_city, pref in from_prefix.items():
        if url.startswith(pref):
            to_slug = url[len(pref):]
            if to_slug in to_slug_map:
                row['city_to'] = to_slug_map[to_slug]
                fixed += 1
                found = True
                break
    if not found:
        not_fixed.append((cf, url))

# Write report
with open(BASE_DIR + r'\_fix_report.txt', 'w', encoding='utf-8') as f:
    f.write(f'Fixed: {fixed}\n')
    f.write(f'Not fixed: {len(not_fixed)}\n')
    f.write(f'From prefix map size: {len(from_prefix)}\n')
    f.write(f'To slug map size: {len(to_slug_map)}\n')
    f.write(f'\nSample from_prefix:\n')
    for k, v in list(from_prefix.items())[:20]:
        f.write(f'  {k}: {v}\n')
    f.write(f'\nNot fixed:\n')
    for cf, url in not_fixed:
        f.write(f'  {cf} | {url}\n')

# Save fixed CSV
with open(BASE_DIR + r'\routes_city2city_fixed.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['city_from', 'city_to', 'page_url', 'distance_km', 'duration_hours', 'price'])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

print('Done')
