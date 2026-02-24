"""
Модуль 5: Финальный скоринг и сегментация маршрутов city2city.

Объединяет все собранные данные:
- ws_cloud_results.csv (Wordstat Cloud API, все 4204 маршрута)
- serp_results.csv (SERP-анализ: конкуренты, позиции)
- routes_city2city.csv (базовые данные: расстояние, цена)
- direct_routes_10k.csv (маршруты с чеком >=10K)
- wordstat_results.csv (старый Wordstat, 4 шаблона)

Рассчитывает:
- demand_score (спрос)
- competition_score (сила конкурентов)
- position_score (текущая позиция city2city)
- weakness_score (слабость конкурентов)

Сегментирует:
SEO_GOLD / SEO_INVEST / SEO_DEFEND / DIRECT_ONLY / SEO_AUTOPILOT / DIRECT_TEST / IGNORE

Выход:
- final_scoring.csv — полная таблица со всеми метриками
- segment_summary.csv — сводка по сегментам
- final_report.txt — человекочитаемый отчёт
"""

import csv
import io
import json
import math
import os
import sys
from collections import defaultdict

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"

# ============================================================
# INPUT FILES
# ============================================================
ROUTES_CSV = os.path.join(BASE_DIR, "routes_city2city_fixed2.csv")
WS_CLOUD_CSV = os.path.join(BASE_DIR, "ws_cloud_results_v2.csv")
SERP_CSV = os.path.join(BASE_DIR, "serp_results.csv")
DIRECT_CSV = os.path.join(BASE_DIR, "direct_routes_10k.csv")
OLD_WS_CSV = os.path.join(BASE_DIR, "wordstat_results.csv")

# OUTPUT FILES
OUTPUT_SCORING = os.path.join(BASE_DIR, "final_scoring.csv")
OUTPUT_SUMMARY = os.path.join(BASE_DIR, "segment_summary.csv")
OUTPUT_REPORT = os.path.join(BASE_DIR, "final_report.txt")
OUTPUT_MONITORED = os.path.join(BASE_DIR, "monitored_routes_full.csv")

# ============================================================
# SCORING THRESHOLDS (from TZ)
# ============================================================
HIGH_DEMAND_THRESHOLD = 0.5
WEAK_COMPETITION_THRESHOLD = 0.5
CLOSE_POSITION_THRESHOLD = 0.4
MEDIUM_DEMAND_THRESHOLD = 0.2

# Price threshold for Direct eligibility
DIRECT_PRICE_THRESHOLD = 10000

# Federal competitors
FEDERAL_COMPETITORS = [
    'kiwitaxi.ru', 'intui.travel', 'gettransfer.com',
    'i-way.ru', 'unitiki.com', 'blablacar.ru',
    'kiwi.taxi', 'gobus.online', 'transfer-way.ru',
    'instamotion.ru', 'poputti.com', 'avito.ru',
    'm.avito.ru', 'youla.ru',
]


# ============================================================
# DATA LOADING
# ============================================================

def load_routes(path):
    """Load base route data."""
    routes = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row["page_url"].strip()
            routes[url] = {
                "city_from": row["city_from"],
                "city_to": row["city_to"],
                "distance_km": int(row["distance_km"]) if row["distance_km"] else 0,
                "duration_hours": float(row["duration_hours"]) if row["duration_hours"] else 0,
                "price": int(row["price"]) if row["price"] else 0,
            }
    return routes


def load_ws_cloud(path):
    """Load Wordstat Cloud API results (semicolon-delimited)."""
    ws = {}
    if not os.path.exists(path):
        return ws
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            url = row["page_url"].strip()
            total_count = int(row["total_count"]) if row["total_count"] else 0

            # Parse related queries from JSON
            related_json = row.get("related_json", "[]")
            try:
                related = json.loads(related_json) if related_json else []
            except:
                related = []

            # Top related phrases
            top_related = []
            for r in related[:5]:
                if isinstance(r, dict):
                    phrase = r.get("phrase", "")
                    count = int(r.get("count", 0))
                    if phrase:
                        top_related.append(f"{phrase} ({count})")

            ws[url] = {
                "total_count": total_count,
                "phrase": row.get("phrase", ""),
                "top_1_phrase": row.get("top_1_phrase", ""),
                "top_1_count": int(row.get("top_1_count", 0) or 0),
                "related_top5": "; ".join(top_related) if top_related else "",
            }
    return ws


def load_serp(path):
    """Load SERP analysis results (semicolon-delimited)."""
    serp = {}
    if not os.path.exists(path):
        return serp
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            url = row["page_url"].strip()
            serp[url] = {
                "total_found": int(row.get("total_found", 0) or 0),
                "federal_count": int(row.get("federal_count", 0) or 0),
                "local_taxi_count": int(row.get("local_taxi_count", 0) or 0),
                "city2city_position": int(row["city2city_position"]) if row.get("city2city_position") else None,
                "top10_domains": row.get("top10_domains", ""),
            }
    return serp


def load_direct(path):
    """Load Direct routes with check >= 10K."""
    direct = {}
    if not os.path.exists(path):
        return direct
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        for cols in reader:
            if len(cols) < 9:
                continue
            url = cols[4].strip()
            direct[url] = {
                "price": int(cols[2]) if cols[2] else 0,
                "city_type_from": cols[5],
                "city_type_to": cols[6],
                "freq_forecast": cols[7],
                "strategy": cols[8],
            }
    return direct


def load_old_wordstat(path):
    """Load old Wordstat API results (4 templates, semicolon-delimited)."""
    ws = defaultdict(lambda: {"templates": {}, "total_freq": 0})
    if not os.path.exists(path):
        return dict(ws)
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            url = row["page_url"].strip()
            template = row.get("template", "").strip()
            total_count = int(row["total_count"]) if row["total_count"] else 0
            ws[url]["templates"][template] = total_count
            ws[url]["total_freq"] += total_count
    return dict(ws)


# ============================================================
# NORMALIZATION FUNCTIONS
# ============================================================

def normalize_log(values):
    """Log-normalize a list of values to [0, 1]."""
    if not values:
        return []
    log_vals = [math.log1p(v) for v in values]
    mn = min(log_vals)
    mx = max(log_vals)
    rng = mx - mn if mx > mn else 1
    return [(v - mn) / rng for v in log_vals]


def normalize_linear(values):
    """Linear min-max normalize to [0, 1]."""
    if not values:
        return []
    mn = min(values)
    mx = max(values)
    rng = mx - mn if mx > mn else 1
    return [(v - mn) / rng for v in values]


# ============================================================
# SCORING
# ============================================================

def compute_demand_score(freq):
    """Demand score from total frequency (log-normalized)."""
    # Will be computed in batch via normalize_log
    pass


def compute_position_score(pos):
    """Position score from city2city position in SERP."""
    if pos is None:
        return 0.0
    if pos <= 3:
        return 1.0
    elif pos <= 10:
        return 0.7
    elif pos <= 20:
        return 0.4
    elif pos <= 30:
        return 0.2
    else:
        return 0.0


def compute_competition_raw(federal_count, local_taxi_count, total_found):
    """Raw competition score (higher = stronger competitors)."""
    # federal_count: 0-30 (30 results analyzed)
    # local_taxi_count: 0-30
    # total_found: can be millions

    fed_norm = min(federal_count / 10, 1.0)  # Normalize: 10+ federals = max
    # Less local taxis = stronger competition
    local_inverse = 1 - min(local_taxi_count / 10, 1.0)
    # Total found (log)
    total_norm = math.log1p(total_found) / 20 if total_found > 0 else 0  # ~20 for 500M results

    return 0.5 * fed_norm + 0.3 * local_inverse + 0.2 * min(total_norm, 1.0)


def classify_route(demand_score, weakness_score, position_score, price):
    """
    Classify route into segment based on scores.
    Uses TZ classification + price-based Direct logic.
    """
    # First check: if zero demand
    if demand_score == 0:
        return "IGNORE"

    # Price-based Direct override: high check routes always go to Direct
    # (regardless of competition or position)
    if price >= DIRECT_PRICE_THRESHOLD:
        # But also add SEO tag for combined strategy
        if demand_score >= HIGH_DEMAND_THRESHOLD:
            if weakness_score >= WEAK_COMPETITION_THRESHOLD:
                if position_score >= CLOSE_POSITION_THRESHOLD:
                    return "SEO_GOLD_DIRECT"  # Both SEO and Direct
                else:
                    return "SEO_INVEST_DIRECT"  # Invest in SEO + Direct for now
            else:
                return "DIRECT_ONLY"  # Strong competitors, only Direct
        elif demand_score >= MEDIUM_DEMAND_THRESHOLD:
            return "DIRECT_TEST"
        else:
            return "DIRECT_LOW"

    # Regular SEO-focused classification (price < 10K)
    if demand_score >= HIGH_DEMAND_THRESHOLD:
        if weakness_score >= WEAK_COMPETITION_THRESHOLD:
            if position_score >= CLOSE_POSITION_THRESHOLD:
                return "SEO_GOLD"
            else:
                return "SEO_INVEST"
        else:
            if position_score >= CLOSE_POSITION_THRESHOLD:
                return "SEO_DEFEND"
            else:
                return "SEO_HARD"  # Hard to compete, low check — low priority SEO
    elif demand_score >= MEDIUM_DEMAND_THRESHOLD:
        if weakness_score >= WEAK_COMPETITION_THRESHOLD:
            return "SEO_AUTOPILOT"
        else:
            return "SEO_MONITOR"
    else:
        return "IGNORE"


# ============================================================
# MAIN PIPELINE
# ============================================================

def main():
    out = io.StringIO()
    p = lambda *a, **kw: print(*a, **kw, file=out)

    p("=" * 80)
    p("FINAL SCORING: City2City Route Analysis")
    p("=" * 80)

    # 1. Load all data sources
    p("\n--- Loading data ---")
    routes = load_routes(ROUTES_CSV)
    p(f"Routes:           {len(routes)}")

    ws_cloud = load_ws_cloud(WS_CLOUD_CSV)
    p(f"Wordstat Cloud:   {len(ws_cloud)}")

    serp = load_serp(SERP_CSV)
    p(f"SERP results:     {len(serp)}")

    direct = load_direct(DIRECT_CSV)
    p(f"Direct (>=10K):   {len(direct)}")

    old_ws = load_old_wordstat(OLD_WS_CSV)
    p(f"Old Wordstat:     {len(old_ws)}")

    # 2. Merge all data into unified records
    p("\n--- Merging data ---")
    all_urls = set(routes.keys())
    p(f"Total unique URLs: {len(all_urls)}")

    records = []
    for url in all_urls:
        rt = routes[url]
        wsc = ws_cloud.get(url, {})
        sr = serp.get(url, {})
        dr = direct.get(url, {})
        ows = old_ws.get(url, {})

        # Frequency: prefer Cloud API data, fallback to old Wordstat
        freq_cloud = wsc.get("total_count", 0)
        freq_old = ows.get("total_freq", 0)
        total_freq = max(freq_cloud, freq_old)  # Take the higher one

        # Old Wordstat template breakdown (if available)
        templates = ows.get("templates", {})
        freq_taksi = templates.get("такси {city_from} {city_to}", 0)
        freq_transfer = templates.get("трансфер {city_from} {city_to}", 0)
        freq_mezhgorod = templates.get("межгород {city_from} {city_to}", 0)

        # Price
        price = rt["price"]

        # SERP data
        total_found = sr.get("total_found", 0)
        federal_count = sr.get("federal_count", 0)
        local_taxi_count = sr.get("local_taxi_count", 0)
        city2city_position = sr.get("city2city_position", None)
        top10_domains = sr.get("top10_domains", "")

        # Direct data
        in_direct = url in direct
        direct_strategy = dr.get("strategy", "")
        city_type_from = dr.get("city_type_from", "")
        city_type_to = dr.get("city_type_to", "")

        # Related queries from Cloud API
        related_top5 = wsc.get("related_top5", "")

        records.append({
            "page_url": url,
            "city_from": rt["city_from"],
            "city_to": rt["city_to"],
            "distance_km": rt["distance_km"],
            "price": price,
            "total_freq": total_freq,
            "freq_cloud": freq_cloud,
            "freq_old_total": freq_old,
            "freq_taksi": freq_taksi,
            "freq_transfer": freq_transfer,
            "freq_mezhgorod": freq_mezhgorod,
            "total_found": total_found,
            "federal_count": federal_count,
            "local_taxi_count": local_taxi_count,
            "city2city_position": city2city_position,
            "top10_domains": top10_domains,
            "in_direct": "YES" if in_direct else "NO",
            "direct_strategy": direct_strategy,
            "city_type_from": city_type_from,
            "city_type_to": city_type_to,
            "related_queries": related_top5,
            "has_serp": "YES" if url in serp else "NO",
        })

    p(f"Merged records: {len(records)}")

    # Stats on data coverage
    has_freq = sum(1 for r in records if r["total_freq"] > 0)
    has_serp_data = sum(1 for r in records if r["has_serp"] == "YES")
    p(f"With frequency > 0: {has_freq}")
    p(f"With SERP data:     {has_serp_data}")

    # 3. Compute scores
    p("\n--- Computing scores ---")

    # demand_score: log-normalize total_freq
    freqs = [r["total_freq"] for r in records]
    demand_scores = normalize_log(freqs)

    # competition_score: compute raw, then normalize
    comp_raws = [compute_competition_raw(
        r["federal_count"], r["local_taxi_count"], r["total_found"]
    ) for r in records]
    # Normalize competition raw scores to [0, 1]
    comp_scores = normalize_linear(comp_raws)

    # position_score
    pos_scores = [compute_position_score(r["city2city_position"]) for r in records]

    # weakness_score = 1 - competition_score
    weakness_scores = [1 - c for c in comp_scores]

    # Apply scores to records
    for i, rec in enumerate(records):
        rec["demand_score"] = round(demand_scores[i], 4)
        rec["competition_score"] = round(comp_scores[i], 4)
        rec["position_score"] = round(pos_scores[i], 4)
        rec["weakness_score"] = round(weakness_scores[i], 4)

    # 4. Classify
    p("\n--- Classifying routes ---")
    for rec in records:
        rec["segment"] = classify_route(
            rec["demand_score"],
            rec["weakness_score"],
            rec["position_score"],
            rec["price"],
        )

    # Sort by total_freq descending
    records.sort(key=lambda r: -r["total_freq"])

    # 5. Statistics
    p("\n" + "=" * 80)
    p("SEGMENTATION RESULTS")
    p("=" * 80)

    segment_counts = defaultdict(int)
    segment_freq = defaultdict(int)
    segment_routes = defaultdict(list)
    for rec in records:
        seg = rec["segment"]
        segment_counts[seg] += 1
        segment_freq[seg] += rec["total_freq"]
        segment_routes[seg].append(rec)

    total_freq_all = sum(segment_freq.values()) or 1

    # Segment groups for display
    direct_segments = ["SEO_GOLD_DIRECT", "SEO_INVEST_DIRECT", "DIRECT_ONLY", "DIRECT_TEST", "DIRECT_LOW"]
    seo_segments = ["SEO_GOLD", "SEO_INVEST", "SEO_DEFEND", "SEO_HARD", "SEO_AUTOPILOT", "SEO_MONITOR"]
    ignore_segments = ["IGNORE"]

    p(f"\nTotal routes:  {len(records)}")
    p(f"With demand:   {has_freq} ({has_freq/len(records)*100:.1f}%)")
    p(f"Zero demand:   {len(records) - has_freq} ({(len(records)-has_freq)/len(records)*100:.1f}%)")

    p(f"\n{'Segment':<22} {'Routes':>8} {'%':>7} {'Total Freq':>12} {'Avg Freq':>10}")
    p("-" * 65)

    # Direct group
    direct_total = sum(segment_counts.get(s, 0) for s in direct_segments)
    direct_freq_total = sum(segment_freq.get(s, 0) for s in direct_segments)
    p(f"\n>> DIRECT GROUP ({direct_total} routes, freq {direct_freq_total:,})")
    for seg in direct_segments:
        cnt = segment_counts.get(seg, 0)
        if cnt == 0:
            continue
        freq = segment_freq.get(seg, 0)
        avg_f = freq / cnt if cnt > 0 else 0
        p(f"  {seg:<20} {cnt:>8} {cnt/len(records)*100:>6.1f}% {freq:>12,} {avg_f:>10,.0f}")

    # SEO group
    seo_total = sum(segment_counts.get(s, 0) for s in seo_segments)
    seo_freq_total = sum(segment_freq.get(s, 0) for s in seo_segments)
    p(f"\n>> SEO GROUP ({seo_total} routes, freq {seo_freq_total:,})")
    for seg in seo_segments:
        cnt = segment_counts.get(seg, 0)
        if cnt == 0:
            continue
        freq = segment_freq.get(seg, 0)
        avg_f = freq / cnt if cnt > 0 else 0
        p(f"  {seg:<20} {cnt:>8} {cnt/len(records)*100:>6.1f}% {freq:>12,} {avg_f:>10,.0f}")

    # Ignore
    p(f"\n>> IGNORE ({segment_counts.get('IGNORE', 0)} routes)")

    # 6. TOP routes for each actionable segment
    for seg_name, description in [
        ("SEO_GOLD_DIRECT", "SEO + Direct: high demand, weak competition, we're close"),
        ("SEO_INVEST_DIRECT", "SEO investment + Direct: high demand, weak competition, we're far"),
        ("DIRECT_ONLY", "Direct only: high demand, strong competition"),
        ("SEO_GOLD", "SEO Gold: high demand, weak competition, close position (low check)"),
        ("SEO_INVEST", "SEO Invest: high demand, weak competition, far position (low check)"),
        ("SEO_DEFEND", "SEO Defend: high demand, strong competition, but we're in top"),
    ]:
        routes_seg = segment_routes.get(seg_name, [])
        if not routes_seg:
            continue

        p(f"\n{'=' * 80}")
        p(f"TOP-15 {seg_name}: {description}")
        p(f"{'=' * 80}")
        p(f"{'#':>3} {'Route':<55} {'Freq':>7} {'Price':>9} {'Pos':>5} {'Demand':>7} {'Weak':>7}")
        p("-" * 98)
        for i, r in enumerate(routes_seg[:15], 1):
            rn = f"{r['city_from']} -> {r['city_to']}"
            if len(rn) > 53:
                rn = rn[:50] + "..."
            pos_str = str(r['city2city_position']) if r['city2city_position'] else "-"
            p(f"{i:>3} {rn:<55} {r['total_freq']:>7,} {r['price']:>8,}R {pos_str:>5} "
              f"{r['demand_score']:>7.3f} {r['weakness_score']:>7.3f}")

    # 7. Key insights
    p(f"\n{'=' * 80}")
    p(f"KEY INSIGHTS")
    p(f"{'=' * 80}")

    # Routes where city2city is in top-3
    top3_routes = [r for r in records if r["city2city_position"] and r["city2city_position"] <= 3 and r["total_freq"] > 0]
    top3_routes.sort(key=lambda r: -r["total_freq"])
    p(f"\nRoutes where city2city is TOP-3 ({len(top3_routes)} total, top 15):")
    for r in top3_routes[:15]:
        p(f"  #{r['city2city_position']} | {r['city_from']} -> {r['city_to']} | freq={r['total_freq']:,} | price={r['price']:,}R | {r['segment']}")

    # High-frequency routes NOT in top-10
    high_freq_no_top = [r for r in records
                        if r["total_freq"] >= 100
                        and (r["city2city_position"] is None or r["city2city_position"] > 10)]
    high_freq_no_top.sort(key=lambda r: -r["total_freq"])
    p(f"\nHigh-frequency routes (>=100) NOT in top-10 ({len(high_freq_no_top)} total):")
    for r in high_freq_no_top[:15]:
        pos_str = str(r['city2city_position']) if r['city2city_position'] else "not found"
        p(f"  {r['city_from']} -> {r['city_to']} | freq={r['total_freq']:,} | pos={pos_str} | {r['segment']}")

    # Direct budget potential
    p(f"\n--- DIRECT BUDGET POTENTIAL ---")
    direct_recs = [r for r in records if r["segment"] in direct_segments and r["total_freq"] > 0]
    if direct_recs:
        total_direct_freq = sum(r["total_freq"] for r in direct_recs)
        avg_price = sum(r["price"] for r in direct_recs) / len(direct_recs)
        p(f"Total Direct-eligible routes:  {len(direct_recs)}")
        p(f"Total frequency:               {total_direct_freq:,}")
        p(f"Average check:                 {avg_price:,.0f}R")

        # Estimate: assume 2% CTR, 5% conversion
        est_clicks = total_direct_freq * 0.02
        est_orders = est_clicks * 0.05
        est_revenue = est_orders * avg_price
        p(f"\nEstimates (2% CTR, 5% conv):")
        p(f"  Monthly clicks:  ~{est_clicks:,.0f}")
        p(f"  Monthly orders:  ~{est_orders:,.0f}")
        p(f"  Monthly revenue: ~{est_revenue:,.0f}R")

    # SEO opportunity
    p(f"\n--- SEO OPPORTUNITY ---")
    seo_recs = [r for r in records if r["segment"] in seo_segments and r["total_freq"] > 0]
    if seo_recs:
        total_seo_freq = sum(r["total_freq"] for r in seo_recs)
        p(f"Total SEO routes:    {len(seo_recs)}")
        p(f"Total frequency:     {total_seo_freq:,}")
        gold_recs = [r for r in seo_recs if "GOLD" in r["segment"]]
        invest_recs = [r for r in seo_recs if "INVEST" in r["segment"]]
        p(f"  SEO_GOLD:   {len(gold_recs)} routes (quick wins)")
        p(f"  SEO_INVEST: {len(invest_recs)} routes (need work)")

    # 8. Save outputs
    p(f"\n{'=' * 80}")
    p(f"SAVING OUTPUTS")
    p(f"{'=' * 80}")

    # 8a. final_scoring.csv
    fieldnames = [
        "page_url", "city_from", "city_to", "distance_km", "price",
        "total_freq", "freq_cloud", "freq_old_total",
        "freq_taksi", "freq_transfer", "freq_mezhgorod",
        "demand_score", "competition_score", "position_score", "weakness_score",
        "total_found", "federal_count", "local_taxi_count",
        "city2city_position", "top10_domains",
        "in_direct", "direct_strategy", "city_type_from", "city_type_to",
        "segment", "has_serp", "related_queries",
    ]
    with open(OUTPUT_SCORING, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";",
                                extrasaction='ignore')
        writer.writeheader()
        for rec in records:
            row = dict(rec)
            # Convert None to empty string for CSV
            if row["city2city_position"] is None:
                row["city2city_position"] = ""
            writer.writerow(row)
    p(f"Saved: {OUTPUT_SCORING} ({len(records)} rows)")

    # 8b. segment_summary.csv
    with open(OUTPUT_SUMMARY, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "segment", "count", "pct_of_total", "total_freq", "avg_freq",
            "avg_price", "avg_demand_score", "avg_weakness_score",
            "example_routes",
        ])
        all_segments = direct_segments + seo_segments + ignore_segments
        for seg in all_segments:
            recs = segment_routes.get(seg, [])
            if not recs:
                continue
            cnt = len(recs)
            freq = sum(r["total_freq"] for r in recs)
            avg_freq = freq / cnt if cnt > 0 else 0
            avg_price_seg = sum(r["price"] for r in recs) / cnt if cnt > 0 else 0
            avg_demand = sum(r["demand_score"] for r in recs) / cnt if cnt > 0 else 0
            avg_weakness = sum(r["weakness_score"] for r in recs) / cnt if cnt > 0 else 0
            examples = ", ".join(f"{r['city_from']}-{r['city_to']}" for r in recs[:5])
            writer.writerow([
                seg, cnt, f"{cnt/len(records)*100:.1f}%", freq, f"{avg_freq:.0f}",
                f"{avg_price_seg:.0f}", f"{avg_demand:.3f}", f"{avg_weakness:.3f}",
                examples,
            ])
    p(f"Saved: {OUTPUT_SUMMARY}")

    # 8c. monitored_routes_full.csv (for server weekly monitoring)
    monitored = [r for r in records if r["total_freq"] > 0]
    with open(OUTPUT_MONITORED, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["page_url", "city_from", "city_to", "price", "segment", "total_freq"])
        for rec in monitored:
            writer.writerow([
                rec["page_url"], rec["city_from"], rec["city_to"],
                rec["price"], rec["segment"], rec["total_freq"],
            ])
    p(f"Saved: {OUTPUT_MONITORED} ({len(monitored)} routes for weekly monitoring)")

    # 9. Write report
    report = out.getvalue()
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(report)
    p(f"Saved: {OUTPUT_REPORT}")

    # Console summary
    sys.stdout.write(f"\n{'='*60}\n")
    sys.stdout.write(f"Final Scoring Complete!\n")
    sys.stdout.write(f"{'='*60}\n")
    sys.stdout.write(f"Routes analyzed:  {len(records)}\n")
    sys.stdout.write(f"With demand > 0:  {has_freq}\n")
    sys.stdout.write(f"With SERP data:   {has_serp_data}\n")
    sys.stdout.write(f"\nSegments:\n")

    for seg in direct_segments + seo_segments + ignore_segments:
        cnt = segment_counts.get(seg, 0)
        if cnt > 0:
            sys.stdout.write(f"  {seg:<22} {cnt:>6}\n")

    sys.stdout.write(f"\nOutputs:\n")
    sys.stdout.write(f"  {OUTPUT_SCORING}\n")
    sys.stdout.write(f"  {OUTPUT_SUMMARY}\n")
    sys.stdout.write(f"  {OUTPUT_REPORT}\n")
    sys.stdout.write(f"  {OUTPUT_MONITORED}\n")

    return report


if __name__ == "__main__":
    main()
