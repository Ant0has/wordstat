"""
Full pipeline: Wordstat frequency + SERP analysis via Yandex Search API (Cloud).

Phase 1: Collect Wordstat frequency for ALL routes (replaces old Wordstat API)
Phase 2: Send SERP async requests + collect results
Phase 3: Save everything

Resume capability via progress files.
"""

import csv
import json
import os
import sys
import time
import signal
import base64
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"

API_KEY = os.environ.get("YANDEX_API_KEY", "")
FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")

WORDSTAT_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"
SEARCH_ASYNC_URL = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
OPERATIONS_URL = "https://operation.api.cloud.yandex.net/operations/"

# Input
ROUTES_CSV = os.path.join(BASE_DIR, "routes_city2city.csv")

# Output
WS_RESULTS_CSV = os.path.join(BASE_DIR, "ws_cloud_results.csv")
WS_PROGRESS = os.path.join(BASE_DIR, "ws_cloud_progress.json")
SERP_RESULTS_CSV = os.path.join(BASE_DIR, "serp_results.csv")
SERP_OPS_FILE = os.path.join(BASE_DIR, "serp_operations.json")
SERP_PROGRESS = os.path.join(BASE_DIR, "serp_progress.json")
ERROR_LOG = os.path.join(BASE_DIR, "pipeline_errors.log")

# Rate limits
WORDSTAT_PAUSE = 0.25   # 4 rps (conservative)
SEARCH_PAUSE = 0.15     # ~7 rps
SERP_BATCH_SIZE = 200   # send 200 async, wait, collect
SERP_WAIT_SECS = 90     # wait before collecting results

# Templates for Wordstat
TEMPLATES = [
    "taksi {city_from} {city_to}",
]
# We only need the main "taksi" query for Search API Wordstat
# since it returns related queries automatically

# Federal competitors for SERP scoring
FEDERAL_COMPETITORS = [
    'kiwitaxi.ru', 'intui.travel', 'gettransfer.com',
    'i-way.ru', 'unitiki.com', 'blablacar.ru',
    'kiwi.taxi', 'gobus.online', 'transfer-way.ru',
    'instamotion.ru', 'poputti.com', 'avito.ru',
    'm.avito.ru', 'youla.ru',
]

# ============================================================
# UTILS
# ============================================================
import requests as req

HEADERS = {
    "Authorization": f"Api-Key {API_KEY}",
    "Content-Type": "application/json",
}

stop_flag = False


def signal_handler(sig, frame):
    global stop_flag
    stop_flag = True
    log("Ctrl+C received, finishing current batch...")


signal.signal(signal.SIGINT, signal_handler)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except:
        pass


def log_error(msg):
    log(f"ERROR: {msg}")
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


def api_post(url, payload, max_retries=3):
    """POST with retry and backoff."""
    for attempt in range(max_retries):
        try:
            r = req.post(url, headers=HEADERS, json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 5 * (attempt + 1)))
                log(f"  429 rate limit, waiting {wait}s...")
                time.sleep(wait)
            elif r.status_code == 503:
                log(f"  503 service unavailable, waiting {10 * (attempt + 1)}s...")
                time.sleep(10 * (attempt + 1))
            else:
                log_error(f"HTTP {r.status_code}: {r.text[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    return None
        except Exception as e:
            log_error(f"Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                return None
    return None


def api_get(url, max_retries=3):
    """GET with retry."""
    for attempt in range(max_retries):
        try:
            r = req.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 5 * (attempt + 1)))
                time.sleep(wait)
            else:
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                else:
                    return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                return None
    return None


# ============================================================
# LOAD ROUTES
# ============================================================
def load_routes():
    routes = []
    with open(ROUTES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            routes.append({
                "city_from": row["city_from"],
                "city_to": row["city_to"],
                "page_url": row["page_url"].strip(),
                "distance_km": int(row["distance_km"]) if row["distance_km"] else 0,
                "price": int(row["price"]) if row["price"] else 0,
            })
    return routes


# ============================================================
# PHASE 1: WORDSTAT FREQUENCY
# ============================================================
def load_ws_progress():
    if os.path.exists(WS_PROGRESS):
        with open(WS_PROGRESS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"collected": []}


def save_ws_progress(progress):
    with open(WS_PROGRESS, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False)


def collect_wordstat(routes):
    """Collect Wordstat frequency for all routes using Search API."""
    log("=" * 60)
    log("PHASE 1: Wordstat Frequency Collection")
    log("=" * 60)

    progress = load_ws_progress()
    collected_urls = set(progress["collected"])

    # Filter routes not yet collected
    pending = [r for r in routes if r["page_url"] not in collected_urls]
    log(f"Total routes: {len(routes)}")
    log(f"Already collected: {len(collected_urls)}")
    log(f"Pending: {len(pending)}")

    if not pending:
        log("All Wordstat data already collected!")
        return

    # Open CSV for append
    file_exists = os.path.exists(WS_RESULTS_CSV) and os.path.getsize(WS_RESULTS_CSV) > 0
    csvfile = open(WS_RESULTS_CSV, "a", encoding="utf-8-sig", newline="")
    writer = csv.writer(csvfile, delimiter=";")
    if not file_exists:
        writer.writerow([
            "page_url", "city_from", "city_to",
            "phrase", "total_count",
            "top_1_phrase", "top_1_count",
            "top_2_phrase", "top_2_count",
            "top_3_phrase", "top_3_count",
            "related_json",
        ])

    success = 0
    errors = 0
    start_time = time.time()

    for i, route in enumerate(pending):
        if stop_flag:
            log("Stopping by user request...")
            break

        phrase = f"\u0442\u0430\u043a\u0441\u0438 {route['city_from']} {route['city_to']}"

        payload = {
            "folderId": FOLDER_ID,
            "phrase": phrase,
        }

        data = api_post(WORDSTAT_URL, payload)

        if data is not None:
            total_count = int(data.get("totalCount", 0))
            results = data.get("results", [])

            # Top 3 related
            top = results[:3] if results else []
            top_phrases = [(t.get("phrase", ""), int(t.get("count", 0))) for t in top]
            while len(top_phrases) < 3:
                top_phrases.append(("", 0))

            # Full related JSON
            related = json.dumps(results[:10], ensure_ascii=False) if results else "[]"

            writer.writerow([
                route["page_url"], route["city_from"], route["city_to"],
                phrase, total_count,
                top_phrases[0][0], top_phrases[0][1],
                top_phrases[1][0], top_phrases[1][1],
                top_phrases[2][0], top_phrases[2][1],
                related,
            ])

            collected_urls.add(route["page_url"])
            success += 1
        else:
            errors += 1
            log_error(f"Failed: {phrase}")

        # Progress save every 50
        if (success + errors) % 50 == 0:
            progress["collected"] = list(collected_urls)
            save_ws_progress(progress)
            csvfile.flush()

            elapsed = time.time() - start_time
            rate = success / elapsed if elapsed > 0 else 0
            eta_mins = (len(pending) - i - 1) / rate / 60 if rate > 0 else 0
            log(f"  [{i+1}/{len(pending)}] ok={success} err={errors} "
                f"rate={rate:.1f}/s ETA={eta_mins:.0f}min")

        time.sleep(WORDSTAT_PAUSE)

    csvfile.close()
    progress["collected"] = list(collected_urls)
    save_ws_progress(progress)

    elapsed = time.time() - start_time
    log(f"\nWordstat done: {success} ok, {errors} errors, {elapsed:.0f}s")


# ============================================================
# PHASE 2: SERP ANALYSIS (deferred/async)
# ============================================================
def load_serp_progress():
    if os.path.exists(SERP_PROGRESS):
        with open(SERP_PROGRESS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"collected": [], "operations": {}}


def save_serp_progress(progress):
    with open(SERP_PROGRESS, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False)


def parse_serp_xml(raw_b64):
    """Parse SERP XML response, extract top-10 domains and scoring data."""
    try:
        raw_bytes = base64.b64decode(raw_b64)
        root = ET.fromstring(raw_bytes)
    except Exception as e:
        return None

    result = {
        "total_found": 0,
        "domains": [],
        "federal_count": 0,
        "dedicated_pages": 0,
        "local_taxi_count": 0,
        "city2city_position": None,
        "top10_json": "[]",
    }

    # Total found
    for found in root.findall(".//{*}found"):
        if found.get("priority") == "phrase":
            try:
                result["total_found"] = int(found.text)
            except:
                pass
            break

    # Top-30 groups (3 pages of Yandex)
    groups = root.findall(".//{*}group")
    top10 = []
    for pos, group in enumerate(groups[:30], 1):
        domain_el = group.find(".//{*}domain")
        url_el = group.find(".//{*}url")
        title_el = group.find(".//{*}title")

        domain = domain_el.text if domain_el is not None else ""
        url = url_el.text if url_el is not None else ""
        title = ""
        if title_el is not None:
            title = "".join(title_el.itertext())

        top10.append({
            "position": pos,
            "domain": domain,
            "url": url,
            "title": title[:100],
        })

        # Scoring
        domain_lower = domain.lower() if domain else ""
        if domain_lower in FEDERAL_COMPETITORS or any(fc in domain_lower for fc in FEDERAL_COMPETITORS):
            result["federal_count"] += 1
        if "city2city" in domain_lower:
            result["city2city_position"] = pos
        if ("taxi" in domain_lower or "transfer" in domain_lower or
            "taksi" in domain_lower or "perevoz" in domain_lower):
            if domain_lower not in FEDERAL_COMPETITORS:
                result["local_taxi_count"] += 1

    result["domains"] = [t["domain"] for t in top10]
    result["top10_json"] = json.dumps(top10, ensure_ascii=False)

    return result


def send_serp_batch(routes_batch):
    """Send a batch of async SERP requests, return {url: operation_id}."""
    ops = {}
    for route in routes_batch:
        if stop_flag:
            break

        phrase = f"\u0442\u0430\u043a\u0441\u0438 {route['city_from']} {route['city_to']}"
        payload = {
            "folderId": FOLDER_ID,
            "query": {
                "searchType": "SEARCH_TYPE_RU",
                "queryText": phrase,
                "familyMode": "FAMILY_MODE_NONE",
                "page": 0,
            },
            "sortSpec": {
                "sortMode": "SORT_MODE_BY_RELEVANCE",
                "sortOrder": "SORT_ORDER_DESC",
            },
            "groupSpec": {
                "groupMode": "GROUP_MODE_DEEP",
                "groupsOnPage": 30,
                "docsInGroup": 1,
            },
            "maxPassages": 1,
            "region": "225",
            "responseFormat": "FORMAT_XML",
        }

        data = api_post(SEARCH_ASYNC_URL, payload)
        if data and data.get("id"):
            ops[route["page_url"]] = {
                "op_id": data["id"],
                "phrase": phrase,
                "city_from": route["city_from"],
                "city_to": route["city_to"],
            }
        else:
            log_error(f"SERP send failed: {phrase}")

        time.sleep(SEARCH_PAUSE)

    return ops


def collect_serp_results(ops_dict):
    """Collect deferred SERP results by operation IDs."""
    results = {}
    not_done = []

    for url, info in ops_dict.items():
        if stop_flag:
            break

        data = api_get(f"{OPERATIONS_URL}{info['op_id']}")
        if data and data.get("done"):
            response = data.get("response", {})
            raw_data = response.get("rawData", "")
            if raw_data:
                parsed = parse_serp_xml(raw_data)
                if parsed:
                    parsed["page_url"] = url
                    parsed["phrase"] = info["phrase"]
                    parsed["city_from"] = info["city_from"]
                    parsed["city_to"] = info["city_to"]
                    results[url] = parsed
                else:
                    log_error(f"XML parse failed: {url}")
            else:
                log_error(f"No rawData: {url}")
        elif data and not data.get("done"):
            not_done.append(url)
        else:
            log_error(f"SERP collect failed: {url}")

        time.sleep(0.05)  # light throttle for GET

    return results, not_done


def run_serp_analysis(routes):
    """Full SERP analysis: send batches, wait, collect."""
    log("\n" + "=" * 60)
    log("PHASE 2: SERP Analysis (Deferred Mode)")
    log("=" * 60)

    progress = load_serp_progress()
    collected_urls = set(progress["collected"])
    pending_ops = progress.get("operations", {})  # ops from previous run

    # Filter routes not yet collected
    pending = [r for r in routes if r["page_url"] not in collected_urls]
    log(f"Total routes: {len(routes)}")
    log(f"Already collected SERP: {len(collected_urls)}")
    log(f"Pending operations from last run: {len(pending_ops)}")
    log(f"New to send: {len(pending) - len(pending_ops)}")

    # Open CSV for append
    file_exists = os.path.exists(SERP_RESULTS_CSV) and os.path.getsize(SERP_RESULTS_CSV) > 0
    csvfile = open(SERP_RESULTS_CSV, "a", encoding="utf-8-sig", newline="")
    writer = csv.writer(csvfile, delimiter=";")
    if not file_exists:
        writer.writerow([
            "page_url", "city_from", "city_to", "phrase",
            "total_found", "federal_count", "local_taxi_count",
            "city2city_position", "top10_domains", "top10_json",
        ])

    total_success = 0
    total_errors = 0

    # First: collect any pending operations from previous run
    if pending_ops:
        log(f"\nCollecting {len(pending_ops)} pending operations from last run...")
        results, not_done = collect_serp_results(pending_ops)
        for url, res in results.items():
            writer.writerow([
                res["page_url"], res["city_from"], res["city_to"], res["phrase"],
                res["total_found"], res["federal_count"], res["local_taxi_count"],
                res["city2city_position"] or "",
                "|".join(res["domains"]),
                res["top10_json"],
            ])
            collected_urls.add(url)
            total_success += 1

        # Remove collected from pending
        for url in results:
            pending_ops.pop(url, None)
        for url in list(pending_ops.keys()):
            if url not in [u for u in not_done]:
                pending_ops.pop(url, None)

        log(f"Collected {len(results)}, still pending: {len(not_done)}")

    # Now process new routes in batches
    # Filter out routes that are in pending_ops (already sent but not collected)
    new_pending = [r for r in pending
                   if r["page_url"] not in collected_urls
                   and r["page_url"] not in pending_ops]

    log(f"\nSending new SERP requests: {len(new_pending)}")

    batch_num = 0
    for batch_start in range(0, len(new_pending), SERP_BATCH_SIZE):
        if stop_flag:
            break

        batch = new_pending[batch_start:batch_start + SERP_BATCH_SIZE]
        batch_num += 1
        log(f"\n--- Batch {batch_num}: sending {len(batch)} requests "
            f"({batch_start+1}-{batch_start+len(batch)}/{len(new_pending)}) ---")

        # Send batch
        new_ops = send_serp_batch(batch)
        pending_ops.update(new_ops)
        log(f"Sent {len(new_ops)} requests")

        # Save progress (operations)
        progress["collected"] = list(collected_urls)
        progress["operations"] = pending_ops
        save_serp_progress(progress)

        if stop_flag:
            break

        # Wait for processing
        log(f"Waiting {SERP_WAIT_SECS}s for results to process...")
        for sec in range(SERP_WAIT_SECS):
            if stop_flag:
                break
            time.sleep(1)
            if (sec + 1) % 30 == 0:
                log(f"  ...{sec+1}/{SERP_WAIT_SECS}s")

        if stop_flag:
            break

        # Collect results
        log("Collecting results...")
        results, not_done = collect_serp_results(pending_ops)

        for url, res in results.items():
            writer.writerow([
                res["page_url"], res["city_from"], res["city_to"], res["phrase"],
                res["total_found"], res["federal_count"], res["local_taxi_count"],
                res["city2city_position"] or "",
                "|".join(res["domains"]),
                res["top10_json"],
            ])
            collected_urls.add(url)
            total_success += 1

        # Cleanup collected from pending_ops
        for url in results:
            pending_ops.pop(url, None)

        csvfile.flush()
        progress["collected"] = list(collected_urls)
        progress["operations"] = pending_ops
        save_serp_progress(progress)

        log(f"Batch {batch_num}: collected {len(results)}, not done: {len(not_done)}, "
            f"total: {total_success}")

        # Retry not-done ones
        if not_done and not stop_flag:
            log(f"Retrying {len(not_done)} not-done operations after 30s...")
            time.sleep(30)
            retry_ops = {u: pending_ops[u] for u in not_done if u in pending_ops}
            results2, still_pending = collect_serp_results(retry_ops)
            for url, res in results2.items():
                writer.writerow([
                    res["page_url"], res["city_from"], res["city_to"], res["phrase"],
                    res["total_found"], res["federal_count"], res["local_taxi_count"],
                    res["city2city_position"] or "",
                    "|".join(res["domains"]),
                    res["top10_json"],
                ])
                collected_urls.add(url)
                total_success += 1
                pending_ops.pop(url, None)

            progress["collected"] = list(collected_urls)
            progress["operations"] = pending_ops
            save_serp_progress(progress)

    csvfile.close()
    log(f"\nSERP done: {total_success} collected, {total_errors} errors, "
        f"{len(pending_ops)} still pending")


# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 60)
    log("FULL PIPELINE: Yandex Search API")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    routes = load_routes()
    log(f"Loaded {len(routes)} routes")

    # Phase 1: Wordstat
    collect_wordstat(routes)

    if stop_flag:
        log("Stopped after Wordstat phase. Run again to continue.")
        return

    # Phase 2: SERP
    run_serp_analysis(routes)

    log("\n" + "=" * 60)
    log("PIPELINE COMPLETE")
    log(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)


if __name__ == "__main__":
    main()
