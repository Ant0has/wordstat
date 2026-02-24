"""
Comprehensive analytics for 109K SERP dataset.
"""

import csv
import math
import os
import re
import sys
from collections import defaultdict

BASE_DIR = "C:/Users/furse/Downloads/wordstatapi"
SERP_CSV = os.path.join(BASE_DIR, "serp_109k_results.csv")
WS_CSV = os.path.join(BASE_DIR, "ws_109k_nonzero.csv")
OUTPUT_SCORING = os.path.join(BASE_DIR, "scoring_109k.csv")
OUTPUT_SUMMARY = os.path.join(BASE_DIR, "segment_summary_109k.csv")
MAX_FREQ_REFERENCE = 42000
HIGH_DEMAND_THRESHOLD = 0.5
MEDIUM_DEMAND_THRESHOLD = 0.2
WEAK_COMPETITION_THRESHOLD = 0.5
CLOSE_POSITION_THRESHOLD = 0.4


def separator(char="=", width=90):
    return char * width


def header(title, char="=", width=90):
    line = char * width
    return f"\n{line}\n  {title}\n{line}"


def safe_int(val, default=0):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def load_serp(path):
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            pos_raw = row.get("city2city_position", "").strip()
            rows.append({
                "page_url": row.get("page_url", "").strip(),
                "slug": row.get("slug", "").strip(),
                "title": row.get("title", "").strip(),
                "phrase": row.get("phrase", "").strip(),
                "freq": safe_int(row.get("freq", 0)),
                "total_found": safe_int(row.get("total_found", 0)),
                "federal_count": safe_int(row.get("federal_count", 0)),
                "regional_taxi_count": safe_int(row.get("regional_taxi_count", 0)),
                "yandex_count": safe_int(row.get("yandex_count", 0)),
                "classifieds_count": safe_int(row.get("classifieds_count", 0)),
                "directory_count": safe_int(row.get("directory_count", 0)),
                "city2city_position": safe_float(pos_raw) if pos_raw else None,
                "top10_domains": row.get("top10_domains", "").strip(),
                "competitor_details": row.get("competitor_details", "").strip(),
                "top10_json": row.get("top10_json", "").strip(),
            })
    return rows


def load_ws(path):
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            slug = row.get("url", "").strip()
            if slug:
                rows[slug] = {
                    "total_count": safe_int(row.get("total_count", 0)),
                    "top_1_phrase": row.get("top_1_phrase", "").strip(),
                    "top_1_count": safe_int(row.get("top_1_count", 0)),
                }
    return rows


def is_noise(slug):
    s = slug.lower().strip()
    if s.startswith("svo-taxi-"):
        return True
    if "mezhgorod" in s:
        return True
    if re.match(r"^\d+[-]", s):
        return True
    if s.startswith("transfer-"):
        return True
    parts = s.split("-")
    if len(parts) == 2 and parts[0] == parts[1]:
        return True
    if len(parts) >= 4 and len(parts) % 2 == 0:
        mid = len(parts) // 2
        first_half = "-".join(parts[:mid])
        second_half = "-".join(parts[mid:])
        if first_half == second_half:
            return True
    return False


def compute_demand_score(freq):
    if freq <= 0:
        return 0.0
    return min(1.0, math.log(1 + freq) / math.log(1 + MAX_FREQ_REFERENCE))


def compute_competition_score(federal_count, regional_taxi_count, total_found):
    fed = min(federal_count / 30.0, 1.0)
    reg = min(regional_taxi_count / 30.0, 1.0)
    total = min(total_found / 1000000.0, 1.0)
    return 0.5 * fed + 0.3 * (1 - reg) + 0.2 * total


def compute_position_score(city2city_position):
    if city2city_position is None:
        return 0.0
    pos = city2city_position
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


def assign_segment(demand_score, weakness_score, position_score, freq):
    high_demand = demand_score >= HIGH_DEMAND_THRESHOLD
    medium_demand = demand_score >= MEDIUM_DEMAND_THRESHOLD
    weak_comp = weakness_score >= WEAK_COMPETITION_THRESHOLD
    close_pos = position_score >= CLOSE_POSITION_THRESHOLD
    has_position = position_score > 0

    if high_demand and weak_comp and close_pos:
        return "SEO_GOLD_NEW"
    elif high_demand and weak_comp and not has_position:
        return "SEO_INVEST_NEW"
    elif high_demand and not weak_comp:
        return "SEO_HARD_NEW"
    elif medium_demand and weak_comp and has_position:
        return "SEO_AUTOPILOT_NEW"
    elif freq > 50 and not has_position:
        return "POTENTIAL_DIRECT_NEW"
    elif freq > 0:
        return "LOW_PRIORITY"
    else:
        return "ZERO_DEMAND"


def main():
    print(header("ANALYSIS OF 109K SERP DATASET"))
    print(f"  Script: analyze_109k_serp.py")
    print(f"  Input:  {SERP_CSV}")
    print(f"          {WS_CSV}")
    print()

    serp_data = load_serp(SERP_CSV)
    ws_data = load_ws(WS_CSV)
    print(f"  Loaded {len(serp_data)} SERP rows")
    print(f"  Loaded {len(ws_data)} Wordstat rows")

    print(header("1. OVERVIEW"))

    total_with_serp = len(serp_data)
    print(f"\n  Total routes with SERP data: {total_with_serp:,}")

    slug_best = {}
    for row in serp_data:
        slug = row["slug"]
        if slug not in slug_best or row["freq"] > slug_best[slug]["freq"]:
            slug_best[slug] = row

    deduped = list(slug_best.values())
    print(f"  After dedup by slug (keep highest freq): {len(deduped):,}")

    noise_routes = [r for r in deduped if is_noise(r["slug"])]
    clean_routes = [r for r in deduped if not is_noise(r["slug"])]

    noise_by_type = defaultdict(list)
    for r in noise_routes:
        s = r["slug"].lower()
        if s.startswith("svo-taxi-"):
            noise_by_type["svo-taxi-*"].append(r)
        elif "mezhgorod" in s:
            noise_by_type["mezhgorod"].append(r)
        elif re.match(r"^\d+[-]", s):
            noise_by_type["digit-prefix"].append(r)
        elif s.startswith("transfer-"):
            noise_by_type["transfer-*"].append(r)
        else:
            noise_by_type["same-city"].append(r)

    print(f"\n  Noise filtered out: {len(noise_routes):,}")
    for ntype, nlist in sorted(noise_by_type.items()):
        examples = ", ".join([r["slug"] for r in nlist[:3]])
        print(f"    {ntype:20s}: {len(nlist):5d}  (e.g. {examples})")

    print(f"\n  >>> REAL INTERCITY ROUTES: {len(clean_routes):,} <<<")
    total_freq_clean = sum(r["freq"] for r in clean_routes)
    print(f"  >>> Total monthly searches: {total_freq_clean:,} <<<")

    # SECTION 2: CITY2CITY POSITIONS
    print(header("2. CITY2CITY POSITIONS"))

    pos_buckets = {
        "TOP-3": [], "TOP-5": [], "TOP-10": [],
        "TOP-20": [], "TOP-30": [], "NOT in TOP-30": [],
    }
    for r in clean_routes:
        pos = r["city2city_position"]
        if pos is None:
            pos_buckets["NOT in TOP-30"].append(r)
        elif pos <= 3:
            for k in ["TOP-3","TOP-5","TOP-10","TOP-20","TOP-30"]:
                pos_buckets[k].append(r)
        elif pos <= 5:
            for k in ["TOP-5","TOP-10","TOP-20","TOP-30"]:
                pos_buckets[k].append(r)
        elif pos <= 10:
            for k in ["TOP-10","TOP-20","TOP-30"]:
                pos_buckets[k].append(r)
        elif pos <= 20:
            for k in ["TOP-20","TOP-30"]:
                pos_buckets[k].append(r)
        elif pos <= 30:
            pos_buckets["TOP-30"].append(r)

    pos_hdr = "  " + f"{'Position':<20s} {'Routes':>8s} {'Total Freq':>12s} {'Avg Freq':>10s}"
    print(f"\n{pos_hdr}")
    print(f"  {'-'*52}")
    for label in ["TOP-3", "TOP-5", "TOP-10", "TOP-20", "TOP-30", "NOT in TOP-30"]:
        rin = pos_buckets[label]
        cnt = len(rin)
        tf = sum(r["freq"] for r in rin)
        af = tf / cnt if cnt > 0 else 0
        print(f"  {label:<20s} {cnt:>8,d} {tf:>12,d} {af:>10.1f}")

    top3r = sorted(pos_buckets["TOP-3"], key=lambda r: r["freq"], reverse=True)
    print(f"\n  --- Routes IN TOP-3 (top 20 by freq) ---")
    print(f"  {'#':>3s}  {'Slug':<45s} {'Freq':>8s} {'Pos':>5s} {'Fed':>4s} {'Reg':>4s}")
    for i, r in enumerate(top3r[:20], 1):
        print(f"  {i:>3d}  {r['slug']:<45s} {r['freq']:>8,d} {r['city2city_position']:>5.0f} {r['federal_count']:>4d} {r['regional_taxi_count']:>4d}")

    t10n3 = [r for r in pos_buckets["TOP-10"] if r["city2city_position"] is not None and r["city2city_position"] > 3]
    t10n3s = sorted(t10n3, key=lambda r: r["freq"], reverse=True)
    print(f"\n  --- Routes IN TOP-10 but NOT TOP-3 (top 20 by freq) ---")
    print(f"  {'#':>3s}  {'Slug':<45s} {'Freq':>8s} {'Pos':>5s} {'Fed':>4s} {'Reg':>4s}")
    for i, r in enumerate(t10n3s[:20], 1):
        print(f"  {i:>3d}  {r['slug']:<45s} {r['freq']:>8,d} {r['city2city_position']:>5.0f} {r['federal_count']:>4d} {r['regional_taxi_count']:>4d}")

    # SECTION 3: COMPETITION ANALYSIS
    print(header("3. COMPETITION ANALYSIS"))

    if clean_routes:
        avg_fed = sum(r["federal_count"] for r in clean_routes) / len(clean_routes)
        avg_reg = sum(r["regional_taxi_count"] for r in clean_routes) / len(clean_routes)
        avg_yandex = sum(r["yandex_count"] for r in clean_routes) / len(clean_routes)
        print(f"\n  Average federal_count:       {avg_fed:.2f}")
        print(f"  Average regional_taxi_count: {avg_reg:.2f}")
        print(f"  Average yandex_count:        {avg_yandex:.2f}")

    fed_dist = {"0": [], "1-3": [], "4-6": [], "7-10": [], "10+": []}
    for r in clean_routes:
        fc = r["federal_count"]
        if fc == 0: fed_dist["0"].append(r)
        elif fc <= 3: fed_dist["1-3"].append(r)
        elif fc <= 6: fed_dist["4-6"].append(r)
        elif fc <= 10: fed_dist["7-10"].append(r)
        else: fed_dist["10+"].append(r)

    print(f"\n  Distribution of federal_count:")
    print(f"  {'Range':<10s} {'Routes':>8s} {'%':>7s} {'Total Freq':>12s}")
    print(f"  {'-'*40}")
    for lb in ["0", "1-3", "4-6", "7-10", "10+"]:
        rin = fed_dist[lb]
        cnt = len(rin)
        pct = cnt / len(clean_routes) * 100 if clean_routes else 0
        tf = sum(r["freq"] for r in rin)
        print(f"  {lb:<10s} {cnt:>8,d} {pct:>6.1f}% {tf:>12,d}")

    weakest = [r for r in clean_routes if r["federal_count"] == 0 and r["regional_taxi_count"] < 3]
    wk_sorted = sorted(weakest, key=lambda r: r["freq"], reverse=True)
    print(f"\n  WEAKEST COMPETITION (federal=0, regional_taxi<3): {len(weakest):,} routes")
    print(f"  Top 30 by freq:")
    print(f"  {'#':>3s}  {'Slug':<45s} {'Freq':>8s} {'Pos':>5s} {'Fed':>4s} {'Reg':>4s} {'Yandex':>6s}")
    for i, r in enumerate(wk_sorted[:30], 1):
        ps = f"{r['city2city_position']:.0f}" if r["city2city_position"] is not None else "-"
        print(f"  {i:>3d}  {r['slug']:<45s} {r['freq']:>8,d} {ps:>5s} {r['federal_count']:>4d} {r['regional_taxi_count']:>4d} {r['yandex_count']:>6d}")

    strongest = [r for r in clean_routes if r["federal_count"] > 5]
    st_sorted = sorted(strongest, key=lambda r: r["freq"], reverse=True)
    print(f"\n  STRONGEST COMPETITION (federal>5): {len(strongest):,} routes")
    print(f"  Top 20 examples:")
    print(f"  {'#':>3s}  {'Slug':<45s} {'Freq':>8s} {'Pos':>5s} {'Fed':>4s} {'Reg':>4s}")
    for i, r in enumerate(st_sorted[:20], 1):
        ps = f"{r['city2city_position']:.0f}" if r["city2city_position"] is not None else "-"
        print(f"  {i:>3d}  {r['slug']:<45s} {r['freq']:>8,d} {ps:>5s} {r['federal_count']:>4d} {r['regional_taxi_count']:>4d}")

    # SECTION 4: SCORING & SEGMENTATION
    print(header("4. SCORING & SEGMENTATION"))

    scored_routes = []
    for r in clean_routes:
        freq = r["freq"]
        ds = compute_demand_score(freq)
        cs = compute_competition_score(r["federal_count"], r["regional_taxi_count"], r["total_found"])
        wks = 1.0 - cs
        ps = compute_position_score(r["city2city_position"])
        seg = assign_segment(ds, wks, ps, freq)
        scored = dict(r)
        scored["demand_score"] = round(ds, 4)
        scored["competition_score"] = round(cs, 4)
        scored["weakness_score"] = round(wks, 4)
        scored["position_score"] = round(ps, 4)
        scored["segment"] = seg
        scored_routes.append(scored)

    segments = defaultdict(list)
    for r in scored_routes:
        segments[r["segment"]].append(r)

    seg_order = [
        "SEO_GOLD_NEW", "SEO_INVEST_NEW", "SEO_HARD_NEW",
        "SEO_AUTOPILOT_NEW", "POTENTIAL_DIRECT_NEW", "LOW_PRIORITY", "ZERO_DEMAND",
    ]

    print(f"\n  {'Segment':<25s} {'Routes':>8s} {'Total Freq':>12s} {'Avg Freq':>10s} {'Med Freq':>10s}")
    print(f"  {'-'*68}")
    for seg in seg_order:
        rin = segments.get(seg, [])
        if not rin:
            print(f"  {seg:<25s} {0:>8d} {0:>12d} {0:>10.1f} {0:>10.1f}")
            continue
        cnt = len(rin)
        tf = sum(r["freq"] for r in rin)
        af = tf / cnt
        sf = sorted([r["freq"] for r in rin])
        mf = sf[len(sf) // 2]
        print(f"  {seg:<25s} {cnt:>8,d} {tf:>12,d} {af:>10.1f} {mf:>10.1f}")

    for seg in seg_order:
        rin = segments.get(seg, [])
        if not rin:
            continue
        top5 = sorted(rin, key=lambda r: r["freq"], reverse=True)[:5]
        print(f"\n  --- {seg} (top 5) ---")
        print(f"  {'Slug':<45s} {'Freq':>8s} {'Pos':>5s} {'DmS':>5s} {'WkS':>5s} {'PosS':>5s}")
        for r in top5:
            ps = f"{r['city2city_position']:.0f}" if r["city2city_position"] is not None else "-"
            print(f"  {r['slug']:<45s} {r['freq']:>8,d} {ps:>5s} {r['demand_score']:>5.2f} {r['weakness_score']:>5.2f} {r['position_score']:>5.2f}")

    # SECTION 5: SAVING OUTPUT FILES
    print(header("5. SAVING OUTPUT FILES"))

    out_cols = [
        "page_url", "slug", "title", "phrase", "freq",
        "city2city_position", "federal_count", "regional_taxi_count",
        "yandex_count", "demand_score", "competition_score",
        "weakness_score", "position_score", "segment", "top10_domains",
    ]
    srs = sorted(scored_routes, key=lambda r: r["freq"], reverse=True)

    with open(OUTPUT_SCORING, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_cols, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for r in srs:
            out = {}
            for col in out_cols:
                val = r.get(col, "")
                if val is None:
                    val = ""
                out[col] = val
            writer.writerow(out)

    print(f"\n  Saved {len(srs):,} scored routes to:")
    print(f"    {OUTPUT_SCORING}")

    summary_rows = []
    for seg in seg_order:
        rin = segments.get(seg, [])
        cnt = len(rin)
        tf = sum(r["freq"] for r in rin) if rin else 0
        af = tf / cnt if cnt > 0 else 0
        sf = sorted([r["freq"] for r in rin]) if rin else [0]
        mf = sf[len(sf) // 2]
        ts = "; ".join([r["slug"] for r in sorted(rin, key=lambda x: x["freq"], reverse=True)[:10]])
        summary_rows.append({
            "segment": seg, "route_count": cnt, "total_freq": tf,
            "avg_freq": round(af, 1), "median_freq": mf, "top_10_slugs": ts,
        })

    with open(OUTPUT_SUMMARY, "w", encoding="utf-8-sig", newline="") as f:
        cols = ["segment", "route_count", "total_freq", "avg_freq", "median_freq", "top_10_slugs"]
        writer = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    print(f"  Saved segment summary to:")
    print(f"    {OUTPUT_SUMMARY}")

    # SECTION 6: KEY FINDINGS
    print(header("6. KEY FINDINGS"))

    golden = [r for r in scored_routes if
              r["freq"] > 100 and
              r["city2city_position"] is not None and
              r["city2city_position"] <= 10 and
              r["weakness_score"] >= WEAK_COMPETITION_THRESHOLD]
    golden_sorted = sorted(golden, key=lambda r: r["freq"], reverse=True)
    golden_freq = sum(r["freq"] for r in golden)

    print(f"\n  GOLDEN OPPORTUNITIES (freq>100, TOP-10, weak competition)")
    print(f"  Total: {len(golden):,} routes | Total freq: {golden_freq:,}")
    print(f"  {'#':>3s}  {'Slug':<45s} {'Freq':>8s} {'Pos':>5s} {'Fed':>4s} {'Reg':>4s} {'WkS':>5s}")
    for i, r in enumerate(golden_sorted[:40], 1):
        ps = f"{r['city2city_position']:.0f}" if r["city2city_position"] is not None else "-"
        print(f"  {i:>3d}  {r['slug']:<45s} {r['freq']:>8,d} {ps:>5s} {r['federal_count']:>4d} {r['regional_taxi_count']:>4d} {r['weakness_score']:>5.2f}")

    invest = [r for r in scored_routes if
              r["freq"] > 100 and
              r["city2city_position"] is None and
              r["weakness_score"] >= WEAK_COMPETITION_THRESHOLD]
    invest_sorted = sorted(invest, key=lambda r: r["freq"], reverse=True)
    invest_freq = sum(r["freq"] for r in invest)

    print(f"\n  INVEST OPPORTUNITIES (freq>100, NOT in TOP-30, weak competition)")
    print(f"  Total: {len(invest):,} routes | Total freq: {invest_freq:,}")
    print(f"  {'#':>3s}  {'Slug':<45s} {'Freq':>8s} {'Fed':>4s} {'Reg':>4s} {'WkS':>5s}")
    for i, r in enumerate(invest_sorted[:40], 1):
        print(f"  {i:>3d}  {r['slug']:<45s} {r['freq']:>8,d} {r['federal_count']:>4d} {r['regional_taxi_count']:>4d} {r['weakness_score']:>5.2f}")

    direct_cand = [r for r in scored_routes if
                   r["freq"] > 50 and r["city2city_position"] is None]
    direct_sorted = sorted(direct_cand, key=lambda r: r["freq"], reverse=True)
    direct_freq = sum(r["freq"] for r in direct_cand)

    print(f"\n  NEW DIRECT CANDIDATES (freq>50, NOT in TOP-30)")
    print(f"  Total: {len(direct_cand):,} routes | Total freq: {direct_freq:,}")
    print(f"  {'#':>3s}  {'Slug':<45s} {'Freq':>8s} {'Fed':>4s} {'Reg':>4s} {'Comp':>5s}")
    for i, r in enumerate(direct_sorted[:40], 1):
        print(f"  {i:>3d}  {r['slug']:<45s} {r['freq']:>8,d} {r['federal_count']:>4d} {r['regional_taxi_count']:>4d} {r['competition_score']:>5.2f}")

    # TRAFFIC POTENTIAL SUMMARY
    print(f"\n  {separator('-', 70)}")
    print(f"  TRAFFIC POTENTIAL SUMMARY")
    print(f"  {separator('-', 70)}")

    act_segs = ["SEO_GOLD_NEW", "SEO_INVEST_NEW", "SEO_HARD_NEW", "SEO_AUTOPILOT_NEW", "POTENTIAL_DIRECT_NEW"]
    actionable = [r for r in scored_routes if r["segment"] in act_segs]
    actionable_freq = sum(r["freq"] for r in actionable)
    total_all_freq = sum(r["freq"] for r in scored_routes)

    print(f"  All scored intercity routes: {len(scored_routes):,} | Total freq: {total_all_freq:,}")
    print(f"  Actionable routes:           {len(actionable):,} | Total freq: {actionable_freq:,}")
    print()
    for seg in act_segs:
        rin = segments.get(seg, [])
        tf = sum(r["freq"] for r in rin)
        print(f"    {seg:<25s}: {len(rin):>6,d} routes | freq: {tf:>10,d}")

    print(f"\n  If we reach TOP-3 on GOLDEN routes:")
    print(f"    Estimated CTR ~30% for TOP-1, ~15% for TOP-3")
    print(f"    Golden routes freq: {golden_freq:,}")
    print(f"    Potential monthly clicks (15% CTR): ~{int(golden_freq * 0.15):,}")

    print(f"\n  If we enter TOP-10 on INVEST routes:")
    print(f"    Invest routes freq: {invest_freq:,}")
    print(f"    Potential monthly clicks (10% CTR): ~{int(invest_freq * 0.10):,}")

    total_potential = int(golden_freq * 0.15 + invest_freq * 0.10)
    print(f"\n  >>> TOTAL POTENTIAL FROM GOLD + INVEST: ~{total_potential:,} monthly clicks <<<")

    print(f"\n{separator('=')}")
    print(f"  ANALYSIS COMPLETE")
    print(f"{separator('=')}")


if __name__ == "__main__":
    main()
