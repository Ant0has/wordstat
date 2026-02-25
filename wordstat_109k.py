"""
Разовый скрипт: Wordstat-проверка ~109K маршрутов из БД city2city.ru
которые НЕ входят в основные 4204 маршрута.

Цель: найти маршруты с ненулевой частотностью — кандидаты на развитие.
Маршруты с freq > 0 потом пойдут на SERP-анализ отдельным скриптом.

Источник данных: new_routes_titles.tsv (url\ttitle) — экспорт из MySQL.
Wordstat-запрос = title в нижнем регистре (уже формат "такси Город1 Город2").

Вход:  new_routes_titles.tsv (109K строк)
Выход: ws_109k_results.csv     — все результаты
       ws_109k_nonzero.csv     — только freq > 0 (для SERP-анализа)
       ws_109k_progress.json   — прогресс для resume

API: Yandex Cloud Search API (Wordstat topRequests) — бесплатно (Preview).
"""

import csv
import json
import os
import sys
import time
import signal
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"

API_KEY = os.environ.get("YANDEX_API_KEY", "")
FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")

WORDSTAT_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"

# Input
TITLES_TSV = os.path.join(BASE_DIR, "new_routes_titles.tsv")

# Output
RESULTS_CSV = os.path.join(BASE_DIR, "ws_109k_results.csv")
NONZERO_CSV = os.path.join(BASE_DIR, "ws_109k_nonzero.csv")
PROGRESS_FILE = os.path.join(BASE_DIR, "ws_109k_progress.json")
ERROR_LOG = os.path.join(BASE_DIR, "ws_109k_errors.log")

# Rate limits
PAUSE = 0.25  # 4 rps
SAVE_EVERY = 100  # save progress every N routes

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
    log("Ctrl+C — finishing current batch...")


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
                log(f"  503 unavailable, waiting {10 * (attempt + 1)}s...")
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


# ============================================================
# LOAD ROUTES
# ============================================================
def load_routes():
    """Load routes from TSV export (url\ttitle)."""
    routes = []
    with open(TITLES_TSV, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) < 2:
                continue
            url = parts[0].strip()
            title = parts[1].strip()
            if not url or not title:
                continue

            # Build Wordstat phrase from title
            # Title = "Такси Москва Абдулино" -> phrase = "такси Москва Абдулино"
            # Keep original case for city names but lowercase "такси"/"трансфер"
            phrase = title
            if phrase.startswith("Такси "):
                phrase = "такси " + phrase[6:]
            elif phrase.startswith("Трансфер "):
                phrase = "трансфер " + phrase[9:]

            routes.append({
                "url": url,
                "title": title,
                "phrase": phrase,
            })
    return routes


# ============================================================
# PROGRESS
# ============================================================
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"collected": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False)


# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 60)
    log("WORDSTAT 109K: Frequency check for all DB routes")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    routes = load_routes()
    log(f"Loaded {len(routes)} routes from TSV")

    progress = load_progress()
    collected_urls = set(progress["collected"])
    log(f"Already collected: {len(collected_urls)}")

    # Filter pending
    pending = [r for r in routes if r["url"] not in collected_urls]
    log(f"Pending: {len(pending)}")

    if not pending:
        log("All routes already collected!")
        write_nonzero()
        return

    # ETA
    eta_hours = len(pending) / 4 / 3600
    log(f"Estimated time: {eta_hours:.1f} hours at 4 rps")

    # Open CSV for append
    file_exists = os.path.exists(RESULTS_CSV) and os.path.getsize(RESULTS_CSV) > 0
    csvfile = open(RESULTS_CSV, "a", encoding="utf-8-sig", newline="")
    writer = csv.writer(csvfile, delimiter=";")
    if not file_exists:
        writer.writerow([
            "url", "title", "phrase", "total_count",
            "top_1_phrase", "top_1_count",
            "top_2_phrase", "top_2_count",
            "top_3_phrase", "top_3_count",
        ])

    success = 0
    errors = 0
    nonzero = 0
    start_time = time.time()

    for i, route in enumerate(pending):
        if stop_flag:
            log("Stopping by user request...")
            break

        payload = {
            "folderId": FOLDER_ID,
            "phrase": route["phrase"],
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

            writer.writerow([
                route["url"], route["title"], route["phrase"], total_count,
                top_phrases[0][0], top_phrases[0][1],
                top_phrases[1][0], top_phrases[1][1],
                top_phrases[2][0], top_phrases[2][1],
            ])

            collected_urls.add(route["url"])
            success += 1
            if total_count > 0:
                nonzero += 1
        else:
            errors += 1
            log_error(f"Failed: {route['phrase']}")

        # Progress save every 50 routes or first route
        total_done = success + errors
        if total_done == 1 or total_done % 50 == 0:
            progress["collected"] = list(collected_urls)
            save_progress(progress)
            csvfile.flush()

            elapsed = time.time() - start_time
            rate = success / elapsed if elapsed > 0 else 0
            remaining = len(pending) - i - 1
            eta_mins = remaining / rate / 60 if rate > 0 else 0
            pct = (len(collected_urls)) / len(routes) * 100
            log(f"  [{i+1}/{len(pending)}] ({pct:.1f}%) ok={success} err={errors} "
                f"nonzero={nonzero} rate={rate:.1f}/s ETA={eta_mins:.0f}min")

        time.sleep(PAUSE)

    csvfile.close()
    progress["collected"] = list(collected_urls)
    save_progress(progress)

    elapsed = time.time() - start_time
    log(f"\nDone: {success} ok, {errors} errors, {nonzero} nonzero, {elapsed:.0f}s")

    # Write nonzero CSV
    write_nonzero()


def write_nonzero():
    """Extract routes with freq > 0 into separate CSV for SERP analysis."""
    if not os.path.exists(RESULTS_CSV):
        log("No results file yet.")
        return

    nonzero = []
    with open(RESULTS_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            tc = int(row["total_count"]) if row["total_count"] else 0
            if tc > 0:
                nonzero.append(row)

    nonzero.sort(key=lambda r: -int(r["total_count"]))

    with open(NONZERO_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["url", "title", "phrase", "total_count",
                         "top_1_phrase", "top_1_count",
                         "top_2_phrase", "top_2_count",
                         "top_3_phrase", "top_3_count"])
        for row in nonzero:
            writer.writerow([
                row["url"], row["title"], row["phrase"], row["total_count"],
                row.get("top_1_phrase", ""), row.get("top_1_count", ""),
                row.get("top_2_phrase", ""), row.get("top_2_count", ""),
                row.get("top_3_phrase", ""), row.get("top_3_count", ""),
            ])

    log(f"Nonzero routes: {len(nonzero)} saved to {NONZERO_CSV}")

    # Quick stats
    if nonzero:
        total_freq = sum(int(r["total_count"]) for r in nonzero)
        log(f"  Total frequency: {total_freq:,}")
        log(f"  Top-5:")
        for r in nonzero[:5]:
            log(f"    {r['title']:50s} freq={r['total_count']}")


if __name__ == "__main__":
    main()
