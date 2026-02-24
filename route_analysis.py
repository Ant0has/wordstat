"""
Сводный анализ маршрутов: Wordstat частотность + Direct (чек >=10K) + базовые данные.
Сегментация: ДИРЕКТ / SEO / ИГНОР
"""

import csv
import io
import os
import sys
from collections import defaultdict

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"

WORDSTAT_CSV = os.path.join(BASE_DIR, "wordstat_results.csv")
ROUTES_CSV = os.path.join(BASE_DIR, "routes_city2city.csv")
DIRECT_CSV = os.path.join(BASE_DIR, "direct_routes_10k.csv")

OUTPUT_COMBINED = os.path.join(BASE_DIR, "analysis_combined.csv")
OUTPUT_REPORT = os.path.join(BASE_DIR, "analysis_report.txt")


def load_wordstat(path):
    route_data = defaultdict(lambda: {
        "templates": {}, "total_freq": 0, "max_phrase": "", "max_count": 0,
        "city_from": "", "city_to": "",
    })
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            url = row["page_url"].strip()
            template = row["template"].strip()
            total_count = int(row["total_count"]) if row["total_count"] else 0
            d = route_data[url]
            d["city_from"] = row["city_from"]
            d["city_to"] = row["city_to"]
            d["templates"][template] = total_count
            d["total_freq"] += total_count
            if total_count > d["max_count"]:
                d["max_count"] = total_count
                d["max_phrase"] = row["phrase"]
    return dict(route_data)


def load_routes(path):
    routes = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row["page_url"].strip()
            routes[url] = {
                "city_from": row["city_from"], "city_to": row["city_to"],
                "distance_km": int(row["distance_km"]) if row["distance_km"] else 0,
                "duration_hours": float(row["duration_hours"]) if row["duration_hours"] else 0,
                "price": int(row["price"]) if row["price"] else 0,
            }
    return routes


def load_direct(path):
    direct = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        for cols in reader:
            if len(cols) < 9:
                continue
            url = cols[4].strip()
            direct[url] = {
                "city_from": cols[0], "city_to": cols[1],
                "price": int(cols[2]) if cols[2] else 0,
                "distance_km": int(cols[3]) if cols[3] else 0,
                "city_type_from": cols[5], "city_type_to": cols[6],
                "freq_forecast": cols[7], "strategy": cols[8],
            }
    return direct


def segment_route(total_freq, price):
    """
    Сегментация:
    - DIRECT: чек >= 10,000 И частотность > 0 (подходят для рекламы)
    - SEO: частотность > 0, но чек < 10,000 (работаем через SEO)
    - IGNORE: нулевая частотность (не трогаем)
    """
    if total_freq == 0:
        return "IGNORE"
    if price >= 10000:
        return "DIRECT"
    return "SEO"


def sub_segment(total_freq, price, in_direct, strategy):
    if total_freq == 0:
        if price >= 10000:
            return "IGNORE_HIGH_CHECK"
        return "IGNORE_ZERO"
    if price >= 10000:
        if total_freq >= 100:
            return "DIRECT_PRIORITY"
        elif total_freq >= 10:
            return "DIRECT_STANDARD"
        else:
            return "DIRECT_TEST"
    if total_freq >= 500:
        return "SEO_GOLD"
    elif total_freq >= 100:
        return "SEO_INVEST"
    elif total_freq >= 10:
        return "SEO_STANDARD"
    else:
        return "SEO_LOW"


def main():
    out = io.StringIO()
    p = lambda *a, **kw: print(*a, **kw, file=out)

    p("=" * 70)
    p("ROUTE ANALYSIS: Wordstat + Direct + Base Data")
    p("=" * 70)

    wordstat = load_wordstat(WORDSTAT_CSV)
    routes = load_routes(ROUTES_CSV)
    direct = load_direct(DIRECT_CSV)

    p(f"\n1. DATA LOADED")
    p(f"   Wordstat: {len(wordstat)} unique URLs with frequency data")
    p(f"   All routes: {len(routes)} URLs")
    p(f"   Direct (check>=10K): {len(direct)} URLs")

    wordstat_urls = set(wordstat.keys())
    direct_urls = set(direct.keys())

    p(f"\n2. JOIN STATS")
    p(f"   Wordstat & Direct intersection: {len(wordstat_urls & direct_urls)}")
    p(f"   Wordstat only: {len(wordstat_urls - direct_urls)}")
    p(f"   Direct only (no Wordstat yet): {len(direct_urls - wordstat_urls)}")

    # Segmentation
    combined = []
    segments = defaultdict(int)
    sub_segments = defaultdict(int)
    segment_freq = defaultdict(int)

    for url in wordstat_urls:
        ws = wordstat[url]
        rt = routes.get(url, {})
        dr = direct.get(url, {})

        price = rt.get("price", 0) or (dr.get("price", 0) if dr else 0)
        in_direct = url in direct_urls
        strategy = dr.get("strategy", "") if dr else ""

        seg = segment_route(ws["total_freq"], price)
        sub_seg = sub_segment(ws["total_freq"], price, in_direct, strategy)

        segments[seg] += 1
        sub_segments[sub_seg] += 1
        segment_freq[seg] += ws["total_freq"]

        freq_taksi = ws["templates"].get("такси {city_from} {city_to}", 0)
        freq_transfer = ws["templates"].get("трансфер {city_from} {city_to}", 0)
        freq_mezhgorod = ws["templates"].get("межгород {city_from} {city_to}", 0)
        freq_cena = ws["templates"].get("такси {city_from} {city_to} цена", 0)

        combined.append({
            "page_url": url,
            "city_from": ws["city_from"], "city_to": ws["city_to"],
            "price": price, "distance_km": rt.get("distance_km", 0),
            "total_freq": ws["total_freq"],
            "freq_taksi": freq_taksi, "freq_transfer": freq_transfer,
            "freq_mezhgorod": freq_mezhgorod, "freq_cena": freq_cena,
            "max_phrase": ws["max_phrase"], "max_count": ws["max_count"],
            "in_direct": "YES" if in_direct else "NO",
            "direct_strategy": strategy, "segment": seg, "sub_segment": sub_seg,
        })

    combined.sort(key=lambda x: -x["total_freq"])
    total_analyzed = len(combined)
    total_freq_all = sum(segment_freq.values()) or 1

    p(f"\n{'=' * 70}")
    p(f"3. SEGMENTATION RESULTS")
    p(f"{'=' * 70}")
    p(f"\nTotal routes with Wordstat data: {total_analyzed}")
    p(f"(out of {len(routes)} total routes, {total_analyzed/len(routes)*100:.1f}% analyzed)")

    p(f"\n{'Segment':<12} {'Routes':>8} {'%':>7} {'Total Freq':>12} {'% Freq':>8}")
    p("-" * 50)
    for seg in ["DIRECT", "SEO", "IGNORE"]:
        cnt = segments[seg]
        pct = cnt / total_analyzed * 100 if total_analyzed > 0 else 0
        freq = segment_freq[seg]
        fpct = freq / total_freq_all * 100
        p(f"{seg:<12} {cnt:>8} {pct:>6.1f}% {freq:>12,} {fpct:>7.1f}%")
    p(f"{'TOTAL':<12} {total_analyzed:>8} {'100%':>7} {total_freq_all:>12,} {'100%':>8}")

    p(f"\n--- Sub-segments ---")
    p(f"\n{'Sub-segment':<22} {'Routes':>8} {'%':>7}")
    p("-" * 40)
    for ss in sorted(sub_segments.keys()):
        cnt = sub_segments[ss]
        pct = cnt / total_analyzed * 100
        p(f"{ss:<22} {cnt:>8} {pct:>6.1f}%")

    # TOP-20 DIRECT
    direct_routes = [r for r in combined if r["segment"] == "DIRECT"]
    p(f"\n{'=' * 70}")
    p(f"TOP-20 DIRECT ROUTES (check>=10K + frequency>0)")
    p(f"{'=' * 70}")
    p(f"\n{'#':>3} {'Route':<45} {'Freq':>8} {'Price':>10} {'Strategy':<25}")
    p("-" * 95)
    for i, r in enumerate(direct_routes[:20], 1):
        rn = f"{r['city_from']} -> {r['city_to']}"
        if len(rn) > 43:
            rn = rn[:40] + "..."
        p(f"{i:>3} {rn:<45} {r['total_freq']:>8,} {r['price']:>9,}R {r['direct_strategy']:<25}")

    # TOP-20 SEO
    seo_routes = [r for r in combined if r["segment"] == "SEO"]
    p(f"\n{'=' * 70}")
    p(f"TOP-20 SEO ROUTES (frequency>0, check<10K)")
    p(f"{'=' * 70}")
    p(f"\n{'#':>3} {'Route':<45} {'Freq':>8} {'Price':>10} {'Sub-seg':<18}")
    p("-" * 88)
    for i, r in enumerate(seo_routes[:20], 1):
        rn = f"{r['city_from']} -> {r['city_to']}"
        if len(rn) > 43:
            rn = rn[:40] + "..."
        p(f"{i:>3} {rn:<45} {r['total_freq']:>8,} {r['price']:>9,}R {r['sub_segment']:<18}")

    # IGNORE stats
    ignore_routes = [r for r in combined if r["segment"] == "IGNORE"]
    ignore_high = [r for r in ignore_routes if r["price"] >= 10000]
    p(f"\n{'=' * 70}")
    p(f"IGNORE SEGMENT: ZERO FREQUENCY")
    p(f"{'=' * 70}")
    p(f"Total zero-frequency routes: {len(ignore_routes)}")
    p(f"Of those with check>=10K: {len(ignore_high)}")
    if ignore_high:
        p(f"\nHigh-check routes with zero demand (top 10):")
        for i, r in enumerate(sorted(ignore_high, key=lambda x: -x["price"])[:10], 1):
            p(f"  {i}. {r['city_from']} -> {r['city_to']} -- {r['price']:,}R")

    # Direct without Wordstat
    direct_no_ws = direct_urls - wordstat_urls
    p(f"\n{'=' * 70}")
    p(f"DIRECT ROUTES WITHOUT WORDSTAT DATA")
    p(f"{'=' * 70}")
    p(f"Total: {len(direct_no_ws)} Direct routes not yet checked via Wordstat")
    p(f"Need to collect frequency data for these before making final decisions.")

    # Overall funnel
    p(f"\n{'=' * 70}")
    p(f"OVERALL FUNNEL")
    p(f"{'=' * 70}")
    p(f"All city2city routes:           {len(routes):>6}")
    p(f"Routes with Wordstat data:      {total_analyzed:>6} ({total_analyzed/len(routes)*100:.1f}%)")
    p(f"  -> DIRECT (check>=10K+demand): {segments['DIRECT']:>5}")
    p(f"  -> SEO (demand, check<10K):    {segments['SEO']:>5}")
    p(f"  -> IGNORE (zero demand):       {segments['IGNORE']:>5}")
    p(f"Routes without Wordstat:        {len(routes)-total_analyzed:>6} ({(1-total_analyzed/len(routes))*100:.1f}%)")
    p(f"  -> of those in Direct:         {len(direct_no_ws):>5}")

    # Budget estimates for Direct
    p(f"\n{'=' * 70}")
    p(f"DIRECT BUDGET ESTIMATES")
    p(f"{'=' * 70}")
    if direct_routes:
        avg_price = sum(r["price"] for r in direct_routes) / len(direct_routes)
        total_freq_d = sum(r["total_freq"] for r in direct_routes)
        prio = [r for r in direct_routes if r["sub_segment"] == "DIRECT_PRIORITY"]
        std = [r for r in direct_routes if r["sub_segment"] == "DIRECT_STANDARD"]
        tst = [r for r in direct_routes if r["sub_segment"] == "DIRECT_TEST"]

        p(f"Avg check for Direct routes: {avg_price:,.0f}R")
        p(f"Total frequency (Direct):    {total_freq_d:,}")
        p(f"\nBreakdown:")
        p(f"  DIRECT_PRIORITY (freq>=100): {len(prio):>5} routes, freq {sum(r['total_freq'] for r in prio):>10,}")
        p(f"  DIRECT_STANDARD (freq>=10):  {len(std):>5} routes, freq {sum(r['total_freq'] for r in std):>10,}")
        p(f"  DIRECT_TEST (freq<10):       {len(tst):>5} routes, freq {sum(r['total_freq'] for r in tst):>10,}")

        # Revenue potential
        p(f"\nRevenue potential (freq * price):")
        for label, lst in [("PRIORITY", prio), ("STANDARD", std), ("TEST", tst)]:
            if lst:
                rev = sum(r["total_freq"] * r["price"] for r in lst)
                p(f"  {label}: {rev:>15,} (freq*price units)")
    else:
        p("No Direct routes in current data.")

    # SEO breakdown
    p(f"\n{'=' * 70}")
    p(f"SEO BREAKDOWN")
    p(f"{'=' * 70}")
    if seo_routes:
        seo_gold = [r for r in seo_routes if r["sub_segment"] == "SEO_GOLD"]
        seo_inv = [r for r in seo_routes if r["sub_segment"] == "SEO_INVEST"]
        seo_std = [r for r in seo_routes if r["sub_segment"] == "SEO_STANDARD"]
        seo_low = [r for r in seo_routes if r["sub_segment"] == "SEO_LOW"]

        p(f"  SEO_GOLD (freq>=500):    {len(seo_gold):>5} routes, freq {sum(r['total_freq'] for r in seo_gold):>10,}")
        p(f"  SEO_INVEST (freq>=100):  {len(seo_inv):>5} routes, freq {sum(r['total_freq'] for r in seo_inv):>10,}")
        p(f"  SEO_STANDARD (freq>=10): {len(seo_std):>5} routes, freq {sum(r['total_freq'] for r in seo_std):>10,}")
        p(f"  SEO_LOW (freq<10):       {len(seo_low):>5} routes, freq {sum(r['total_freq'] for r in seo_low):>10,}")

    # Save CSV
    fieldnames = [
        "page_url", "city_from", "city_to", "price", "distance_km",
        "total_freq", "freq_taksi", "freq_transfer", "freq_mezhgorod", "freq_cena",
        "max_phrase", "max_count", "in_direct", "direct_strategy",
        "segment", "sub_segment",
    ]
    with open(OUTPUT_COMBINED, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in combined:
            writer.writerow(row)

    p(f"\nCSV saved: {OUTPUT_COMBINED} ({len(combined)} rows)")

    # Write report
    report = out.getvalue()
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)

    # Print to console (ASCII-safe summary)
    sys.stdout.write(f"Analysis complete. Report: {OUTPUT_REPORT}\n")
    sys.stdout.write(f"CSV: {OUTPUT_COMBINED}\n")
    sys.stdout.write(f"Routes analyzed: {total_analyzed}\n")
    sys.stdout.write(f"DIRECT: {segments['DIRECT']}, SEO: {segments['SEO']}, IGNORE: {segments['IGNORE']}\n")

    return report


if __name__ == "__main__":
    main()
