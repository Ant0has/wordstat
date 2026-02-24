"""Re-collect Wordstat for the 208 routes that had empty city_to (now fixed)."""
import csv, json, requests, time, os

BASE = r"C:\Users\furse\Downloads\wordstatapi"

API_KEY = os.environ.get("YANDEX_API_KEY", "")
FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")
WORDSTAT_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"
HEADERS = {"Authorization": f"Api-Key {API_KEY}", "Content-Type": "application/json"}

# Load fixed routes
fixed = {}
with open(f"{BASE}/routes_city2city_fixed2.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        fixed[row["page_url"]] = row

# Load original routes to find which had empty city_to
orig_empty = set()
with open(f"{BASE}/routes_city2city.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if not row["city_to"].strip():
            orig_empty.add(row["page_url"])

print(f"Routes to re-collect: {len(orig_empty)}")

# Load existing ws_cloud_results to know what's there
existing = {}
ws_path = f"{BASE}/ws_cloud_results.csv"
with open(ws_path, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")
    ws_fields = reader.fieldnames
    for row in reader:
        existing[row["page_url"]] = row

print(f"Existing WS results: {len(existing)}")

# Collect new Wordstat for the 208 routes
results = []
ok = 0
err = 0
for i, url in enumerate(sorted(orig_empty)):
    r = fixed.get(url)
    if not r:
        continue

    cf = r["city_from"]
    ct = r["city_to"]

    # Clean city names: remove "международный аэропорт..." -> just city
    # For phrase, use simple city names
    cf_clean = cf
    ct_clean = ct

    # Remove long airport prefixes for the phrase
    for prefix in ["международный аэропорт Кольцово ", "Международный аэропорт Казань",
                    "аэропорт Платов", "аэропорт Тюмень (Рощино)", "городской округ Тюмень"]:
        if cf.startswith(prefix):
            # Use the city name from the route context
            if "Екатеринбург" in cf:
                cf_clean = "Екатеринбург"
            elif "Казань" in cf:
                cf_clean = "Казань"
            elif "Тюмень" in cf or "Тюмень" in prefix:
                cf_clean = "Тюмень"
            elif "Ростов" in cf or "Платов" in cf:
                cf_clean = "Ростов-на-Дону"
            break

    for prefix in ["село ", "посёлок ", "рабочий посёлок "]:
        if ct.startswith(prefix):
            ct_clean = ct[len(prefix):]
        if cf.startswith(prefix):
            cf_clean = cf[len(prefix):]

    phrase = f"такси {cf_clean} {ct_clean}"

    payload = {"folderId": FOLDER_ID, "phrase": phrase}
    try:
        resp = requests.post(WORDSTAT_URL, headers=HEADERS, json=payload, timeout=15)
        if resp.status_code == 200:
            d = resp.json()
            tc = int(d.get("totalCount", 0))
            ress = d.get("results", [])
            top1_phrase = ress[0]["phrase"] if ress else ""
            top1_count = int(ress[0]["count"]) if ress else 0

            results.append({
                "page_url": url,
                "city_from": cf,
                "city_to": ct,
                "phrase": phrase,
                "total_count": tc,
                "top_1_phrase": top1_phrase,
                "top_1_count": top1_count,
            })
            ok += 1

            status = f"ws={tc}" if tc > 0 else "ws=0"
            if (i+1) % 10 == 0 or tc > 0:
                print(f"  [{i+1}/{len(orig_empty)}] {phrase:<50s} {status}")
        elif resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 5))
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait)
            # Retry
            resp = requests.post(WORDSTAT_URL, headers=HEADERS, json=payload, timeout=15)
            if resp.status_code == 200:
                d = resp.json()
                tc = int(d.get("totalCount", 0))
                ress = d.get("results", [])
                results.append({
                    "page_url": url, "city_from": cf, "city_to": ct,
                    "phrase": phrase, "total_count": tc,
                    "top_1_phrase": ress[0]["phrase"] if ress else "",
                    "top_1_count": int(ress[0]["count"]) if ress else 0,
                })
                ok += 1
        else:
            print(f"  ERR {resp.status_code}: {phrase} -> {resp.text[:100]}")
            err += 1
    except Exception as e:
        print(f"  ERR: {phrase} -> {e}")
        err += 1

    time.sleep(0.3)

print(f"\nDone: {ok} ok, {err} errors")
print(f"Nonzero: {sum(1 for r in results if r['total_count'] > 0)}")

# Update ws_cloud_results.csv - replace old entries for these URLs
for r in results:
    existing[r["page_url"]] = {
        "page_url": r["page_url"],
        "city_from": r["city_from"],
        "city_to": r["city_to"],
        "phrase": r["phrase"],
        "total_count": str(r["total_count"]),
        "top_1_phrase": r["top_1_phrase"],
        "top_1_count": str(r["top_1_count"]),
    }

# Write updated ws_cloud_results
out_path = f"{BASE}/ws_cloud_results_v2.csv"
with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["page_url","city_from","city_to","phrase","total_count","top_1_phrase","top_1_count"], delimiter=";")
    writer.writeheader()
    for url in sorted(existing.keys()):
        row = existing[url]
        writer.writerow({
            "page_url": row.get("page_url", url),
            "city_from": row.get("city_from", ""),
            "city_to": row.get("city_to", ""),
            "phrase": row.get("phrase", ""),
            "total_count": row.get("total_count", "0"),
            "top_1_phrase": row.get("top_1_phrase", ""),
            "top_1_count": row.get("top_1_count", "0"),
        })

print(f"Wrote: {out_path} ({len(existing)} rows)")

# Also save just the 208 results for review
review_path = f"{BASE}/ws_208_fixed.csv"
with open(review_path, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["page_url","city_from","city_to","phrase","total_count","top_1_phrase","top_1_count"], delimiter=";")
    writer.writeheader()
    for r in sorted(results, key=lambda x: -x["total_count"]):
        writer.writerow(r)

print(f"Wrote review: {review_path}")
