"""
Analyze routes from MySQL DB that are NOT in our current 4204 routes.
Parse city_from/city_to from city_data field.
Estimate Wordstat API budget.
"""
import csv
from collections import Counter

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"


def parse_cities(city_data):
    """Parse city_from and city_to from city_data string.
    Format: 'Город1, регион, Россия,Город2, регион, Россия'
    """
    if not city_data or city_data == "-":
        return "", ""
    # Split on 'Россия,' to separate two cities
    parts = city_data.split("Россия,")
    city_from = ""
    city_to = ""
    if len(parts) >= 1:
        city_from = parts[0].split(",")[0].strip()
    if len(parts) >= 2:
        raw = parts[1].strip()
        # Remove leading descriptors like "посёлок городского типа", "село", etc.
        city_to = raw.split(",")[0].strip()
    return city_from, city_to


def main():
    # Load our 4204 known routes
    known_urls = set()
    with open(f"{BASE_DIR}\\routes_city2city.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = row["page_url"].strip().replace("https://city2city.ru/", "")
            known_urls.add(slug)

    print(f"Known routes: {len(known_urls)}")

    # Load all routes from DB export
    all_routes = []
    with open(f"{BASE_DIR}\\all_routes_db.tsv", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 5:
                url = parts[0]
                city_data = parts[1]
                dist_str = parts[2]
                price_str = parts[3]
                idx_str = parts[4]

                dist = 0
                if dist_str not in ("NULL", "", "\\N"):
                    try:
                        dist = int(dist_str)
                    except:
                        pass

                price = 0
                if price_str not in ("NULL", "", "\\N"):
                    try:
                        price = int(price_str)
                    except:
                        pass

                indexable = 0
                if idx_str not in ("NULL", "", "\\N"):
                    try:
                        indexable = int(idx_str)
                    except:
                        pass

                all_routes.append({
                    "url": url,
                    "city_data": city_data,
                    "distance_km": dist,
                    "price": price,
                    "is_indexable": indexable,
                })

    print(f"Total routes in DB: {len(all_routes)}")

    # Find routes NOT in our 4204
    new_routes = []
    for r in all_routes:
        if r["url"] not in known_urls:
            cf, ct = parse_cities(r["city_data"])
            r["city_from"] = cf
            r["city_to"] = ct
            new_routes.append(r)

    # Also check how many of our 4204 are in the DB
    db_urls = set(r["url"] for r in all_routes)
    our_in_db = sum(1 for u in known_urls if u in db_urls)
    our_not_in_db = sum(1 for u in known_urls if u not in db_urls)

    # Stats
    total_new = len(new_routes)
    with_both_cities = sum(1 for r in new_routes if r["city_from"] and r["city_to"])
    with_price = sum(1 for r in new_routes if r["price"] > 0)
    indexable_new = sum(1 for r in new_routes if r["is_indexable"])

    # Unique city pairs
    city_pairs = set()
    for r in new_routes:
        if r["city_from"] and r["city_to"]:
            city_pairs.add((r["city_from"], r["city_to"]))

    unique_from = set(r["city_from"] for r in new_routes if r["city_from"])
    unique_to = set(r["city_to"] for r in new_routes if r["city_to"])

    # Write report
    with open(f"{BASE_DIR}\\new_routes_report.txt", "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("ANALYSIS: Routes in DB but NOT in current 4204\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total in DB:                {len(all_routes):>10,}\n")
        f.write(f"Our known (4204):           {len(known_urls):>10,}\n")
        f.write(f"  - of those in DB:         {our_in_db:>10,}\n")
        f.write(f"  - not found in DB:        {our_not_in_db:>10,}\n")
        f.write(f"NEW routes (not in 4204):   {total_new:>10,}\n")

        f.write(f"\n--- NEW ROUTES BREAKDOWN ---\n")
        f.write(f"With both cities parsed:    {with_both_cities:>10,}\n")
        f.write(f"With price > 0:             {with_price:>10,}\n")
        f.write(f"Indexable (is_indexable=1):  {indexable_new:>10,}\n")
        f.write(f"Unique city_from:           {len(unique_from):>10,}\n")
        f.write(f"Unique city_to:             {len(unique_to):>10,}\n")
        f.write(f"Unique city pairs:          {len(city_pairs):>10,}\n")

        # Distance distribution for new routes
        f.write(f"\n--- DISTANCE DISTRIBUTION (new routes with distance) ---\n")
        dist_ranges = {
            "no_distance": 0,
            "<50km": 0,
            "50-200km": 0,
            "200-500km": 0,
            "500-1000km": 0,
            ">1000km": 0,
        }
        for r in new_routes:
            d = r["distance_km"]
            if d == 0:
                dist_ranges["no_distance"] += 1
            elif d < 50:
                dist_ranges["<50km"] += 1
            elif d < 200:
                dist_ranges["50-200km"] += 1
            elif d < 500:
                dist_ranges["200-500km"] += 1
            elif d < 1000:
                dist_ranges["500-1000km"] += 1
            else:
                dist_ranges[">1000km"] += 1
        for k, v in dist_ranges.items():
            f.write(f"  {k:<20s} {v:>10,}\n")

        # Top cities
        f.write(f"\n--- TOP-20 CITIES BY ROUTE COUNT (city_from) ---\n")
        cf_counts = Counter(r["city_from"] for r in new_routes if r["city_from"])
        for city, cnt in cf_counts.most_common(20):
            f.write(f"  {city:<35s} {cnt:>6,} routes\n")

        # Sample routes
        f.write(f"\n--- SAMPLE NEW ROUTES (first 30) ---\n")
        for r in new_routes[:30]:
            f.write(f"  {r['url']:<55s} {r['city_from']:>20s} -> {r['city_to']:<20s} "
                    f"price={r['price']:>6} dist={r['distance_km']:>5}\n")

        # ============================================================
        # WORDSTAT BUDGET ESTIMATION
        # ============================================================
        f.write(f"\n{'='*80}\n")
        f.write(f"WORDSTAT API BUDGET ESTIMATION\n")
        f.write(f"{'='*80}\n\n")

        # Routes eligible for Wordstat (have both cities)
        eligible = with_both_cities
        f.write(f"Routes with both cities (eligible for Wordstat): {eligible:,}\n\n")

        f.write(f"--- Option 1: Yandex Cloud Search API (Wordstat) ---\n")
        f.write(f"  API: searchapi.api.cloud.yandex.net/v2/wordstat/topRequests\n")
        f.write(f"  Cost: FREE (Preview mode)\n")
        f.write(f"  Rate: ~4 rps (0.25s pause)\n")
        f.write(f"  Time: {eligible} / 4 / 60 = {eligible / 4 / 60:.0f} min = {eligible / 4 / 3600:.1f} hours\n")
        f.write(f"  Daily limit: unknown (Preview), estimated ~50K/day\n")
        f.write(f"  Estimated days: {eligible / 50000:.1f} days if 50K/day limit\n")
        f.write(f"  TOTAL COST: $0 (FREE)\n\n")

        f.write(f"--- Option 2: Classic Wordstat API (api.wordstat.yandex.net) ---\n")
        f.write(f"  Cost: FREE but limited to 5000 requests/day\n")
        f.write(f"  Time: {eligible} / 5000 = {eligible / 5000:.0f} days\n")
        f.write(f"  TOTAL COST: $0 (FREE)\n\n")

        f.write(f"--- Option 3: Yandex Cloud Web Search (SERP) ---\n")
        serp_cost_per_1000 = 0.25  # $ per 1000 deferred requests
        serp_total = eligible * serp_cost_per_1000 / 1000
        f.write(f"  Cost: ${serp_cost_per_1000} per 1000 deferred requests\n")
        f.write(f"  Requests: {eligible:,}\n")
        f.write(f"  TOTAL COST: ${serp_total:.2f} (~{serp_total * 100:.0f} RUB)\n\n")

        f.write(f"--- TOTAL BUDGET SUMMARY ---\n")
        f.write(f"  Phase 1 (Wordstat frequency):  FREE\n")
        f.write(f"  Phase 2 (SERP analysis):       ${serp_total:.2f} (~{serp_total * 100:.0f} RUB)\n")
        f.write(f"  TOTAL:                         ${serp_total:.2f} (~{serp_total * 100:.0f} RUB)\n\n")

        f.write(f"--- TIME ESTIMATION ---\n")
        f.write(f"  Wordstat at 4 rps:             {eligible / 4 / 3600:.1f} hours\n")
        f.write(f"  SERP deferred (batches of 200): {eligible / 200:.0f} batches x 90s wait = "
                f"{eligible / 200 * 90 / 3600:.1f} hours + send/collect time\n")
        f.write(f"  TOTAL estimated:               {eligible / 4 / 3600 + eligible / 200 * 90 / 3600:.1f} hours\n\n")

        f.write(f"--- OPTIMIZATION: SMART FILTERING ---\n")
        f.write(f"  Instead of checking ALL {eligible:,} routes,\n")
        f.write(f"  filter first by city importance:\n\n")

        # Smart estimate: how many routes from TOP cities
        top_20_cities = [city for city, _ in cf_counts.most_common(20)]
        top20_routes = sum(1 for r in new_routes if r["city_from"] in top_20_cities and r["city_to"])
        top50_cities = [city for city, _ in cf_counts.most_common(50)]
        top50_routes = sum(1 for r in new_routes if r["city_from"] in top50_cities and r["city_to"])

        f.write(f"  Top-20 cities: ~{top20_routes:,} routes\n")
        f.write(f"    Time: {top20_routes / 4 / 3600:.1f} hours, SERP: ${top20_routes * 0.00025:.2f}\n")
        f.write(f"  Top-50 cities: ~{top50_routes:,} routes\n")
        f.write(f"    Time: {top50_routes / 4 / 3600:.1f} hours, SERP: ${top50_routes * 0.00025:.2f}\n")
        f.write(f"  All {len(unique_from)} cities: {eligible:,} routes\n")
        f.write(f"    Time: {eligible / 4 / 3600:.1f} hours, SERP: ${eligible * 0.00025:.2f}\n")

    print(f"\nReport saved to {BASE_DIR}\\new_routes_report.txt")
    print(f"New routes: {total_new:,}")
    print(f"Eligible for Wordstat: {with_both_cities:,}")


if __name__ == "__main__":
    main()
