#!/usr/bin/env python3
"""
SERP analysis for nonzero routes from 109K collection.
Server version — run via nohup on Yandex Cloud VPS.

Input:  ws_109k_nonzero.csv
Output: serp_109k_results.csv
        serp_109k_progress.json

Telegram notifications every 1000 routes + final.
"""

import csv
import json
import os
import sys
import time
import signal
import base64
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = "/home/anton-furs/apps/city2city-wordstat"

API_KEY = os.environ.get("YANDEX_API_KEY", "")
FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")

SEARCH_ASYNC_URL = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
OPERATIONS_URL = "https://operation.api.cloud.yandex.net/operations/"

# Telegram
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Input / Output
NONZERO_CSV = os.path.join(BASE_DIR, "ws_109k_nonzero.csv")
SERP_RESULTS_CSV = os.path.join(BASE_DIR, "serp_109k_results.csv")
SERP_PROGRESS = os.path.join(BASE_DIR, "serp_109k_progress.json")
ERROR_LOG = os.path.join(BASE_DIR, "serp_109k_errors.log")
LOG_FILE = os.path.join(BASE_DIR, "serp_109k.log")

# Rate limits
SEARCH_PAUSE = 0.15
SERP_BATCH_SIZE = 200
SERP_WAIT_SECS = 90

# ============================================================
# COMPETITORS
# ============================================================

# Федеральные агрегаторы трансферов / межгородского такси
FEDERAL_AGGREGATORS = [
    'kiwitaxi.ru', 'intui.travel', 'www.intui.travel',
    'gettransfer.com', 'i-way.ru', 'unitiki.com',
    'kiwi.taxi', 'gobus.online', 'transfer-way.ru',
    'instamotion.ru', 'poputti.com',
    'catalogtaksi.ru', 'catalogtaxi.ru',
    'taxi555.ru', '1taxopark.ru',
    'rustransfer.org', 'obltaxi.ru',
    'taxigator.ru', 'transfers.unitaxi.ru',
    'perevozka24.com', 'jupiter-tmc.ru',
    'mezhgorod-rf.ru', 'tratatur.ru',
    'mobilodeon.ru', 'takse.ru',
]

# Псевдо-региональные — на деле федеральные дорвеи
FEDERAL_DOORWAYS = [
    'deshevotaxi.ru', 'taxivezde.ru', 'taksisvo.ru',
    'mezhgorod-taksi.ru', 'taxi.drive-luxe.ru',
    'taksi-gorod.ru', 'mejgorodtaxi.ru',
    'www.taxi2000.ru', 'vse-taxi.com', 'www.taxi-love.ru',
    'taxiomega.ru', 'www.rome2rio.com',
]

# Яндекс-сервисы
YANDEX_SERVICES = [
    'taxi.yandex.ru', 'yandex.ru', 'uslugi.yandex.ru',
    'dzen.ru', 'go.yandex',
]

# Федеральные такси-сети
FEDERAL_TAXI_CHAINS = [
    'taximaxim.ru', 'vezet.ru', 'city-mobil.ru',
]

# Доски объявлений
CLASSIFIEDS = [
    'avito.ru', 'm.avito.ru', 'www.avito.ru', 'youla.ru',
]

# Справочники
DIRECTORIES = [
    '2gis.ru', 'zoon.ru', 'yell.ru', 'flamp.ru',
    'spravker.ru', 'orgpage.ru',
]

# Попутчики / автобусы
RIDE_TRANSPORT = [
    'blablacar.ru', 'www.blablacar.ru',
    'bus.tutu.ru', 'www.tutu.ru', 'rasp.yandex.ru',
]

# Соцсети
SOCIAL = [
    'vk.com', 'ok.ru', 'drom.ru',
]

# Все "сильные" конкуренты — федеральный уровень
ALL_FEDERAL = set(
    FEDERAL_AGGREGATORS + FEDERAL_DOORWAYS +
    YANDEX_SERVICES + FEDERAL_TAXI_CHAINS +
    CLASSIFIEDS + DIRECTORIES + RIDE_TRANSPORT + SOCIAL
)

# ============================================================
# UTILS
# ============================================================
stop_flag = False


def signal_handler(sig, frame):
    global stop_flag
    stop_flag = True
    log("Signal received, stopping after current batch...")


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except:
        pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def log_error(msg):
    log(f"ERROR: {msg}")
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except:
        pass


def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}).encode("utf-8")
        rq = Request(url, data=data, headers={"Content-Type": "application/json"})
        urlopen(rq, timeout=10)
    except Exception as e:
        log(f"Telegram error: {e}")


def api_post(url, payload, max_retries=3):
    data = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Api-Key {API_KEY}", "Content-Type": "application/json"}
    for attempt in range(max_retries):
        try:
            rq = Request(url, data=data, headers=headers, method="POST")
            resp = urlopen(rq, timeout=30)
            return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:200]
            except:
                pass
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
            elif e.code == 503:
                time.sleep(10 * (attempt + 1))
            else:
                log_error(f"HTTP {e.code}: {body}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(2 * (attempt + 1))
        except Exception as e:
            log_error(f"Request error: {e}")
            if attempt == max_retries - 1:
                return None
            time.sleep(3 * (attempt + 1))
    return None


def api_get(url, max_retries=3):
    headers = {"Authorization": f"Api-Key {API_KEY}"}
    for attempt in range(max_retries):
        try:
            rq = Request(url, headers=headers)
            resp = urlopen(rq, timeout=30)
            return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
            elif attempt == max_retries - 1:
                return None
            else:
                time.sleep(2 * (attempt + 1))
        except Exception as e:
            if attempt == max_retries - 1:
                return None
            time.sleep(3 * (attempt + 1))
    return None


# ============================================================
# LOAD ROUTES
# ============================================================
def load_routes():
    routes = {}
    with open(NONZERO_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            slug = row.get("url", "").strip()
            if not slug:
                continue
            freq = int(row.get("total_count", "0") or "0")
            phrase = row.get("phrase", "").strip()
            title = row.get("title", "").strip()

            if slug not in routes or freq > routes[slug]["freq"]:
                page_url = f"https://city2city.ru/{slug}"
                routes[slug] = {
                    "slug": slug,
                    "page_url": page_url,
                    "phrase": phrase,
                    "title": title,
                    "freq": freq,
                }

    return sorted(routes.values(), key=lambda x: x["freq"], reverse=True)


# ============================================================
# CLASSIFY DOMAIN
# ============================================================
def classify_domain(domain):
    """Classify a domain into competitor category."""
    dl = (domain or "").lower().strip()
    if not dl:
        return "unknown", False

    # city2city — это мы
    if "city2city" in dl:
        return "own", False

    # Проверка по спискам
    for d in FEDERAL_AGGREGATORS:
        if d in dl:
            return "federal_aggregator", True
    for d in FEDERAL_DOORWAYS:
        if d in dl:
            return "federal_doorway", True
    for d in YANDEX_SERVICES:
        if d in dl:
            return "yandex", True
    for d in FEDERAL_TAXI_CHAINS:
        if d in dl:
            return "federal_chain", True
    for d in CLASSIFIEDS:
        if d in dl:
            return "classifieds", True
    for d in DIRECTORIES:
        if d in dl:
            return "directory", True
    for d in RIDE_TRANSPORT:
        if d in dl:
            return "ride_transport", True
    for d in SOCIAL:
        if d in dl:
            return "social", True

    # Эвристика: региональное такси
    taxi_keywords = ('taxi', 'taksi', 'transfer', 'perevoz', 'mezhgorod')
    if any(kw in dl for kw in taxi_keywords):
        return "regional_taxi", False

    return "other", False


# ============================================================
# SERP XML PARSING
# ============================================================
def parse_serp_xml(raw_b64):
    try:
        raw_bytes = base64.b64decode(raw_b64)
        root = ET.fromstring(raw_bytes)
    except Exception:
        return None

    result = {
        "total_found": 0,
        "domains": [],
        "federal_count": 0,
        "regional_taxi_count": 0,
        "yandex_count": 0,
        "classifieds_count": 0,
        "directory_count": 0,
        "city2city_position": None,
        "top10_json": "[]",
        "competitor_details": "",
    }

    # Total found
    for found in root.findall(".//{*}found"):
        if found.get("priority") == "phrase":
            try:
                result["total_found"] = int(found.text)
            except:
                pass
            break

    # Top-30 groups
    groups = root.findall(".//{*}group")
    top_items = []
    category_counts = {}

    for pos, group in enumerate(groups[:30], 1):
        domain_el = group.find(".//{*}domain")
        url_el = group.find(".//{*}url")
        title_el = group.find(".//{*}title")

        domain = domain_el.text if domain_el is not None else ""
        url_val = url_el.text if url_el is not None else ""
        title = ""
        if title_el is not None:
            title = "".join(title_el.itertext())

        category, is_federal = classify_domain(domain)

        top_items.append({
            "position": pos,
            "domain": domain,
            "url": url_val,
            "title": title[:100],
            "category": category,
        })

        # Count by category
        category_counts[category] = category_counts.get(category, 0) + 1

        # City2city position
        if category == "own" and result["city2city_position"] is None:
            result["city2city_position"] = pos

        # Count strong (federal-level) competitors
        if is_federal:
            result["federal_count"] += 1

        # Count regional taxi
        if category == "regional_taxi":
            result["regional_taxi_count"] += 1

        # Yandex
        if category == "yandex":
            result["yandex_count"] += 1

        # Classifieds
        if category == "classifieds":
            result["classifieds_count"] += 1

        # Directories
        if category == "directory":
            result["directory_count"] += 1

    result["domains"] = [t["domain"] for t in top_items[:10]]
    result["top10_json"] = json.dumps(top_items[:10], ensure_ascii=False)

    # Compact category summary: "federal_aggregator:3|yandex:2|regional_taxi:4"
    cat_parts = []
    for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1]):
        if cat != "own":
            cat_parts.append(f"{cat}:{cnt}")
    result["competitor_details"] = "|".join(cat_parts)

    return result


# ============================================================
# SERP BATCH PROCESSING
# ============================================================
def send_serp_batch(routes_batch):
    ops = {}
    for route in routes_batch:
        if stop_flag:
            break

        phrase = route["phrase"]
        if not phrase:
            continue

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
            ops[route["slug"]] = {
                "op_id": data["id"],
                "slug": route["slug"],
                "page_url": route["page_url"],
                "phrase": phrase,
                "title": route["title"],
                "freq": route["freq"],
            }
        else:
            log_error(f"SERP send failed: {phrase}")

        time.sleep(SEARCH_PAUSE)

    return ops


def collect_serp_results(ops_dict):
    results = {}
    not_done = []

    for slug, info in ops_dict.items():
        if stop_flag:
            break

        data = api_get(f"{OPERATIONS_URL}{info['op_id']}")
        if data and data.get("done"):
            response = data.get("response", {})
            raw_data = response.get("rawData", "")
            if raw_data:
                parsed = parse_serp_xml(raw_data)
                if parsed:
                    parsed["slug"] = slug
                    parsed["page_url"] = info["page_url"]
                    parsed["phrase"] = info["phrase"]
                    parsed["title"] = info["title"]
                    parsed["freq"] = info["freq"]
                    results[slug] = parsed
                else:
                    log_error(f"XML parse failed: {slug}")
            else:
                log_error(f"No rawData: {slug}")
        elif data and not data.get("done"):
            not_done.append(slug)
        else:
            log_error(f"SERP collect failed: {slug}")

        time.sleep(0.05)

    return results, not_done


def write_row(writer, res):
    writer.writerow([
        res["page_url"],
        res["slug"],
        res.get("title", ""),
        res["phrase"],
        res.get("freq", 0),
        res["total_found"],
        res["federal_count"],
        res["regional_taxi_count"],
        res["yandex_count"],
        res["classifieds_count"],
        res["directory_count"],
        res["city2city_position"] or "",
        "|".join(res["domains"]),
        res.get("competitor_details", ""),
        res["top10_json"],
    ])


# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 60)
    log("SERP ANALYSIS: 109K nonzero routes")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    routes = load_routes()
    log(f"Loaded {len(routes)} unique nonzero routes")

    # Progress
    progress = {"collected": [], "operations": {}}
    if os.path.exists(SERP_PROGRESS):
        try:
            with open(SERP_PROGRESS, "r", encoding="utf-8") as f:
                progress = json.load(f)
        except:
            pass

    collected_slugs = set(progress.get("collected", []))
    pending_ops = progress.get("operations", {})

    pending_routes = [r for r in routes if r["slug"] not in collected_slugs]
    log(f"Already collected: {len(collected_slugs)}")
    log(f"Pending ops: {len(pending_ops)}")
    log(f"Routes to process: {len(pending_routes)}")

    if not pending_routes and not pending_ops:
        log("All done!")
        return

    total_to_process = len(pending_routes)
    total_batches = (total_to_process + SERP_BATCH_SIZE - 1) // SERP_BATCH_SIZE
    eta_min = total_batches * (30 + SERP_WAIT_SECS + 30) // 60

    send_telegram(
        f"🔍 <b>SERP 109K started</b>\n"
        f"Routes: {total_to_process}\n"
        f"Already done: {len(collected_slugs)}\n"
        f"Batches: ~{total_batches}\n"
        f"ETA: ~{eta_min} min"
    )

    # Open CSV
    file_exists = os.path.exists(SERP_RESULTS_CSV) and os.path.getsize(SERP_RESULTS_CSV) > 0
    csvfile = open(SERP_RESULTS_CSV, "a", encoding="utf-8-sig", newline="")
    writer = csv.writer(csvfile, delimiter=";")
    if not file_exists:
        writer.writerow([
            "page_url", "slug", "title", "phrase", "freq",
            "total_found", "federal_count", "regional_taxi_count",
            "yandex_count", "classifieds_count", "directory_count",
            "city2city_position", "top10_domains",
            "competitor_details", "top10_json",
        ])

    total_success = len(collected_slugs)
    total_errors = 0
    start_time = time.time()

    # Collect pending ops from previous run
    if pending_ops:
        log(f"\nCollecting {len(pending_ops)} pending from previous run...")
        results, not_done = collect_serp_results(pending_ops)
        for slug, res in results.items():
            write_row(writer, res)
            collected_slugs.add(slug)
            total_success += 1
        for slug in results:
            pending_ops.pop(slug, None)
        for slug in list(pending_ops.keys()):
            if slug not in not_done:
                pending_ops.pop(slug, None)
                total_errors += 1
        csvfile.flush()
        log(f"Collected {len(results)}, still pending: {len(not_done)}")

    # New routes to send
    new_pending = [r for r in pending_routes
                   if r["slug"] not in collected_slugs
                   and r["slug"] not in pending_ops]

    log(f"\nNew routes to send: {len(new_pending)}")
    real_batches = (len(new_pending) + SERP_BATCH_SIZE - 1) // SERP_BATCH_SIZE

    batch_num = 0
    for batch_start in range(0, len(new_pending), SERP_BATCH_SIZE):
        if stop_flag:
            break

        batch = new_pending[batch_start:batch_start + SERP_BATCH_SIZE]
        batch_num += 1
        log(f"\n--- Batch {batch_num}/{real_batches}: {len(batch)} routes "
            f"({batch_start+1}-{batch_start+len(batch)}/{len(new_pending)}) ---")

        # Send
        new_ops = send_serp_batch(batch)
        pending_ops.update(new_ops)
        log(f"Sent {len(new_ops)} requests")

        # Save progress
        progress["collected"] = list(collected_slugs)
        progress["operations"] = pending_ops
        with open(SERP_PROGRESS, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False)

        if stop_flag:
            break

        # Wait
        log(f"Waiting {SERP_WAIT_SECS}s...")
        for sec in range(SERP_WAIT_SECS):
            if stop_flag:
                break
            time.sleep(1)
            if (sec + 1) % 30 == 0:
                log(f"  ...{sec+1}/{SERP_WAIT_SECS}s")

        if stop_flag:
            break

        # Collect
        log("Collecting results...")
        results, not_done = collect_serp_results(pending_ops)

        batch_ok = 0
        for slug, res in results.items():
            write_row(writer, res)
            collected_slugs.add(slug)
            total_success += 1
            batch_ok += 1
        for slug in results:
            pending_ops.pop(slug, None)

        csvfile.flush()
        progress["collected"] = list(collected_slugs)
        progress["operations"] = pending_ops
        with open(SERP_PROGRESS, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False)

        elapsed = time.time() - start_time
        avg_batch = elapsed / batch_num if batch_num > 0 else 150
        remaining = real_batches - batch_num
        eta = remaining * avg_batch / 60

        log(f"Batch {batch_num}: +{batch_ok}, not_done: {len(not_done)}, "
            f"total: {total_success}/{len(routes)}, ETA: {eta:.0f}min")

        # Retry not-done
        if not_done and not stop_flag:
            log(f"Retrying {len(not_done)} after 30s...")
            time.sleep(30)
            retry_ops = {s: pending_ops[s] for s in not_done if s in pending_ops}
            r2, still = collect_serp_results(retry_ops)
            for slug, res in r2.items():
                write_row(writer, res)
                collected_slugs.add(slug)
                total_success += 1
                pending_ops.pop(slug, None)

            if still and not stop_flag:
                log(f"  Still {len(still)}, retrying in 60s...")
                time.sleep(60)
                retry2 = {s: pending_ops[s] for s in still if s in pending_ops}
                r3, still2 = collect_serp_results(retry2)
                for slug, res in r3.items():
                    write_row(writer, res)
                    collected_slugs.add(slug)
                    total_success += 1
                    pending_ops.pop(slug, None)
                for s in still2:
                    pending_ops.pop(s, None)
                    total_errors += 1
                    log_error(f"Gave up: {s}")

            csvfile.flush()
            progress["collected"] = list(collected_slugs)
            progress["operations"] = pending_ops
            with open(SERP_PROGRESS, "w", encoding="utf-8") as f:
                json.dump(progress, f, ensure_ascii=False)

        # Telegram every 5 batches
        if batch_num % 5 == 0:
            send_telegram(
                f"🔍 SERP 109K: {batch_num}/{real_batches}\n"
                f"Done: {total_success}/{len(routes)}\n"
                f"Errors: {total_errors}\n"
                f"ETA: ~{eta:.0f} min"
            )

    csvfile.close()

    elapsed = time.time() - start_time
    log(f"\n{'=' * 60}")
    log(f"SERP COMPLETE: {total_success} ok, {total_errors} errors, {elapsed/60:.1f} min")
    log(f"{'=' * 60}")

    send_telegram(
        f"✅ <b>SERP 109K COMPLETE</b>\n"
        f"Collected: {total_success}\n"
        f"Errors: {total_errors}\n"
        f"Time: {elapsed/60:.1f} min\n"
        f"File: serp_109k_results.csv"
    )


if __name__ == "__main__":
    main()
