# -*- coding: utf-8 -*-
"""
Analyze competitor domains from SERP data.
Reads serp_results.csv (semicolon-delimited, utf-8-sig),
counts domain frequency across all routes, categorizes them.
"""

import csv
from collections import Counter

CSV_PATH = r"C:\Users\furse\Downloads\wordstatapi\serp_results.csv"

# ── 1. Read data and count domain frequencies ──────────────────────────
domain_counter = Counter()
total_routes = 0
empty_routes = 0

with open(CSV_PATH, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        total_routes += 1
        raw = row.get("top10_domains", "").strip()
        if not raw:
            empty_routes += 1
            continue
        domains = [d.strip() for d in raw.split("|") if d.strip()]
        # Count each domain only once per route (even if it appears twice like yandex.ru)
        for d in set(domains):
            domain_counter[d] += 1

print(f"Total routes analysed: {total_routes}")
print(f"Routes with empty top10_domains: {empty_routes}")
print(f"Unique domains found: {len(domain_counter)}")
print()

# ── 2. Categorisation rules ────────────────────────────────────────────
FEDERAL_AGGREGATORS = {
    "kiwitaxi.ru", "www.kiwitaxi.ru",
    "gettransfer.com", "www.gettransfer.com",
    "intui.travel", "www.intui.travel",
    "blablacar.ru", "www.blablacar.ru",
    "rustransfer.org", "www.rustransfer.org",
    "taxi555.ru", "www.taxi555.ru",
    "transfers.unitaxi.ru", "unitaxi.ru",
    "1taxopark.ru", "www.1taxopark.ru",
    "taxigator.ru", "www.taxigator.ru",
    "catalogtaxi.ru", "www.catalogtaxi.ru",
    "catalogtaksi.ru", "www.catalogtaksi.ru",
    "city2city.ru", "www.city2city.ru",
    "obltaxi.ru", "www.obltaxi.ru",
    "transtaxiru.ru",
    "transfer-online.ru",
    "po-doroge.ru",
    "gorodtaxi.ru",
    "poetomu.ru",
    "dobiraemsya.ru",
}

YANDEX_SERVICES = {
    "yandex.ru", "www.yandex.ru",
    "taxi.yandex.ru",
    "uslugi.yandex.ru",
    "maps.yandex.ru",
    "2gis.ru", "www.2gis.ru",
    "zen.yandex.ru",
    "dzen.ru", "www.dzen.ru",
    "market.yandex.ru",
}

CLASSIFIEDS = {
    "www.avito.ru", "avito.ru",
    "youla.ru", "www.youla.ru",
    "profi.ru", "www.profi.ru",
}

FEDERAL_TAXI_CHAINS = {
    "taximaxim.ru", "www.taximaxim.ru",
    "taxi-maxim.ru",
    "rutaxi.ru", "www.rutaxi.ru",         # Везёт
    "city-mobil.ru", "www.city-mobil.ru",
    "citymobil.ru", "www.citymobil.ru",
    "moetaxi.ru", "www.moetaxi.ru",
}

DIRECTORIES_REVIEWS = {
    "zoon.ru", "www.zoon.ru",
    "yell.ru", "www.yell.ru",
    "flamp.ru", "www.flamp.ru",
    "irecommend.ru", "www.irecommend.ru",
    "otzovik.com", "www.otzovik.com",
    "pravda-sotrudnikov.ru",
    "spr.ru", "www.spr.ru",
    "orgpage.ru", "www.orgpage.ru",
    "2gis.ru", "www.2gis.ru",          # also directory
    "spravker.ru", "www.spravker.ru",
    "vl.ru", "www.vl.ru",
    "tulp.ru", "www.tulp.ru",
    "cataloxy.ru", "www.cataloxy.ru",
}

# Known non-taxi domains to avoid mis-categorizing as regional taxi
KNOWN_NON_TAXI = {
    "ru.wikipedia.org", "wikipedia.org",
    "www.google.com", "google.com",
    "vk.com", "www.vk.com",
    "ok.ru", "www.ok.ru",
    "t.me",
    "drive2.ru", "www.drive2.ru",
}

TAXI_KEYWORDS = ["taxi", "taksi", "такси", "transfer", "трансфер", "transf"]

def categorize(domain):
    dl = domain.lower()
    if dl in FEDERAL_AGGREGATORS:
        return "Federal aggregators"
    if dl in YANDEX_SERVICES:
        return "Yandex services"
    if dl in CLASSIFIEDS:
        return "Classifieds"
    if dl in FEDERAL_TAXI_CHAINS:
        return "Federal taxi chains"
    if dl in DIRECTORIES_REVIEWS:
        return "Directories / reviews"
    if dl in KNOWN_NON_TAXI:
        return "Other"
    # Regional taxi heuristic
    for kw in TAXI_KEYWORDS:
        if kw in dl:
            return "Regional taxi"
    return "Other"


# ── 3. Build sorted list with categories ───────────────────────────────
top_all = domain_counter.most_common()   # all, sorted
top100 = top_all[:100]

print("=" * 90)
print(f"{'#':>4}  {'Domain':<55} {'Count':>6}  Category")
print("=" * 90)

category_counts = Counter()     # category -> total mentions
category_domains = {}           # category -> list of (domain, count)

for i, (dom, cnt) in enumerate(top100, 1):
    cat = categorize(dom)
    category_counts[cat] += cnt
    category_domains.setdefault(cat, []).append((dom, cnt))
    print(f"{i:>4}. {dom:<55} {cnt:>6}  [{cat}]")

print("=" * 90)
print()

# ── 4. Summary by category (across ALL domains, not just top-100) ──────
print("CATEGORY SUMMARY (all domains)")
print("-" * 60)
full_cat_counts = Counter()
full_cat_domains = {}
for dom, cnt in top_all:
    cat = categorize(dom)
    full_cat_counts[cat] += cnt
    full_cat_domains.setdefault(cat, []).append((dom, cnt))

for cat, total in full_cat_counts.most_common():
    n_domains = len(full_cat_domains[cat])
    print(f"  {cat:<25} {total:>7} mentions across {n_domains:>4} unique domains")
print()

# ── 5. Top regional taxi domains ───────────────────────────────────────
regional = full_cat_domains.get("Regional taxi", [])
regional.sort(key=lambda x: -x[1])

print(f"TOP REGIONAL TAXI DOMAINS ({len(regional)} total unique)")
print("-" * 70)
for i, (dom, cnt) in enumerate(regional[:60], 1):
    print(f"  {i:>3}. {dom:<55} {cnt:>5}")
print()

# ── 6. Federal aggregator details ─────────────────────────────────────
fed = full_cat_domains.get("Federal aggregators", [])
fed.sort(key=lambda x: -x[1])
print("FEDERAL AGGREGATOR DOMAINS")
print("-" * 70)
for i, (dom, cnt) in enumerate(fed, 1):
    print(f"  {i:>3}. {dom:<55} {cnt:>5}")
print()

# ── 7. "Other" in top-100 for manual review ───────────────────────────
other_top = [x for x in top100 if categorize(x[0]) == "Other"]
print(f"'Other' domains in TOP-100 (review for re-categorisation)")
print("-" * 70)
for dom, cnt in other_top:
    print(f"  {dom:<55} {cnt:>5}")

