#!/usr/bin/env python3
"""
Wordstat-фильтрация ~109K маршрутов из БД city2city.ru
Серверная версия — запуск через nohup на Yandex Cloud VPS.

Цель: найти маршруты с ненулевой частотностью из полной базы 114K,
которые не входят в основные 4204 маршрута.

Вход:  данные из MySQL (city2city.routes)
Выход: ws_109k_results.csv     — все результаты
       ws_109k_nonzero.csv     — только freq > 0 (для SERP-анализа)
       ws_109k_progress.json   — прогресс для resume

Telegram-уведомления: прогресс каждые 5000 маршрутов + финал.
"""

import csv
import json
import os
import sys
import time
import signal
import subprocess
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.parse import urlencode

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = "/home/anton-furs/apps/city2city-wordstat"

API_KEY = os.environ.get("YANDEX_API_KEY", "")
FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")
WORDSTAT_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"

# Telegram
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# MySQL — получим маршруты напрямую из БД
DB_USER = "city2city_user"
DB_PASS = os.environ.get("DB_PASS", "")
DB_NAME = "city2city"

# Output
RESULTS_CSV = os.path.join(BASE_DIR, "ws_109k_results.csv")
NONZERO_CSV = os.path.join(BASE_DIR, "ws_109k_nonzero.csv")
PROGRESS_FILE = os.path.join(BASE_DIR, "ws_109k_progress.json")
ERROR_LOG = os.path.join(BASE_DIR, "ws_109k_errors.log")
LOG_FILE = os.path.join(BASE_DIR, "ws_109k.log")

# Known 4204 routes (slugs) — загрузим из CSV если есть, иначе из БД
KNOWN_ROUTES_CSV = os.path.join(BASE_DIR, "known_4204_slugs.txt")

# Rate limits
PAUSE = 0.25  # 4 rps target
SAVE_EVERY = 100
TG_NOTIFY_EVERY = 5000

# ============================================================
# LOGGING
# ============================================================
log_file = None


def log(msg):
    global log_file
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except:
        pass
    if log_file is None:
        log_file = open(LOG_FILE, "a", encoding="utf-8")
    log_file.write(line + "\n")
    log_file.flush()


def log_error(msg):
    log(f"ERROR: {msg}")
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        data = urlencode({
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
        }).encode()
        req = Request(url, data=data)
        urlopen(req, timeout=10)
    except Exception as e:
        log(f"TG send error: {e}")


# ============================================================
# HTTP CLIENT (no requests dependency — use urllib)
# ============================================================
import urllib.request
import urllib.error


def api_post(url, payload, max_retries=3):
    """POST with retry and backoff using urllib (no pip install needed)."""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "Content-Type": "application/json",
    }
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            resp = urllib.request.urlopen(req, timeout=30)
            body = resp.read().decode("utf-8")
            return json.loads(body)
        except urllib.error.HTTPError as e:
            code = e.code
            if code == 429:
                wait = int(e.headers.get("Retry-After", 5 * (attempt + 1)))
                log(f"  429 rate limit, waiting {wait}s...")
                time.sleep(wait)
            elif code == 503:
                log(f"  503 unavailable, waiting {10 * (attempt + 1)}s...")
                time.sleep(10 * (attempt + 1))
            else:
                body = ""
                try:
                    body = e.read().decode("utf-8")[:200]
                except:
                    pass
                log_error(f"HTTP {code}: {body}")
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
# DATA LOADING
# ============================================================
def load_known_slugs():
    """Load slugs of known 4204 routes to exclude them."""
    known = set()
    if os.path.exists(KNOWN_ROUTES_CSV):
        with open(KNOWN_ROUTES_CSV, "r", encoding="utf-8") as f:
            for line in f:
                slug = line.strip()
                if slug:
                    known.add(slug)
        log(f"Loaded {len(known)} known slugs from file")
    else:
        # Fallback: get from DB — routes with distance_km > 0
        log("No known slugs file, querying DB for routes with distance...")
        try:
            result = subprocess.run(
                ["mysql", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME, "-N",
                 "-e", "SELECT url FROM routes WHERE distance_km > 0"],
                capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.strip().split("\n"):
                slug = line.strip()
                if slug:
                    known.add(slug)
            log(f"Got {len(known)} known slugs from DB")
            # Save for future runs
            with open(KNOWN_ROUTES_CSV, "w", encoding="utf-8") as f:
                for s in sorted(known):
                    f.write(s + "\n")
        except Exception as e:
            log_error(f"Failed to get known slugs: {e}")
    return known


def load_routes_from_db(known_slugs):
    """Load new routes directly from MySQL."""
    log("Loading routes from MySQL...")
    routes = []
    try:
        result = subprocess.run(
            ["mysql", "-u", DB_USER, f"-p{DB_PASS}", DB_NAME, "-N",
             "-e", "SELECT url, title FROM routes WHERE (distance_km IS NULL OR distance_km = 0)"],
            capture_output=True, text=True, timeout=60
        )
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            url = parts[0].strip()
            title = parts[1].strip()
            if not url or not title:
                continue
            if url in known_slugs:
                continue

            # Build phrase from title
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
    except Exception as e:
        log_error(f"MySQL error: {e}")

    log(f"Loaded {len(routes)} new routes from DB")
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
stop_flag = False


def signal_handler(sig, frame):
    global stop_flag
    stop_flag = True
    log("Signal received, finishing current batch...")


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    os.makedirs(BASE_DIR, exist_ok=True)

    log("=" * 60)
    log("WORDSTAT 109K: Server-side frequency check")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    send_telegram("🔍 <b>Wordstat 109K запущен</b>\nСервер: начинаю проверку ~109K маршрутов")

    # Load data
    known_slugs = load_known_slugs()
    routes = load_routes_from_db(known_slugs)

    if not routes:
        log("No routes to process!")
        send_telegram("⚠️ Wordstat 109K: нет маршрутов для обработки")
        return

    progress = load_progress()
    collected_urls = set(progress["collected"])
    log(f"Already collected: {len(collected_urls)}")

    pending = [r for r in routes if r["url"] not in collected_urls]
    log(f"Pending: {len(pending)}")

    eta_hours = len(pending) / 4 / 3600
    log(f"Estimated time: {eta_hours:.1f} hours at 4 rps")

    send_telegram(
        f"📊 Wordstat 109K\n"
        f"Всего: {len(routes):,}\n"
        f"Уже собрано: {len(collected_urls):,}\n"
        f"Осталось: {len(pending):,}\n"
        f"ETA: ~{eta_hours:.1f}ч"
    )

    # Open CSV for append
    file_exists = os.path.exists(RESULTS_CSV) and os.path.getsize(RESULTS_CSV) > 0
    csvfile = open(RESULTS_CSV, "a", encoding="utf-8", newline="")
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
    last_tg_notify = 0

    for i, route in enumerate(pending):
        if stop_flag:
            log("Stopping by signal...")
            break

        payload = {
            "folderId": FOLDER_ID,
            "phrase": route["phrase"],
        }

        data = api_post(WORDSTAT_URL, payload)

        if data is not None:
            total_count = int(data.get("totalCount", 0))
            results = data.get("results", [])

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

        # Progress save
        total_done = success + errors
        if total_done == 1 or total_done % SAVE_EVERY == 0:
            progress["collected"] = list(collected_urls)
            save_progress(progress)
            csvfile.flush()

            elapsed = time.time() - start_time
            rate = success / elapsed if elapsed > 0 else 0
            remaining = len(pending) - i - 1
            eta_mins = remaining / rate / 60 if rate > 0 else 0
            pct = len(collected_urls) / len(routes) * 100
            log(f"  [{i+1}/{len(pending)}] ({pct:.1f}%) ok={success} err={errors} "
                f"nonzero={nonzero} rate={rate:.1f}/s ETA={eta_mins:.0f}min")

        # Telegram notification every 5000
        if total_done - last_tg_notify >= TG_NOTIFY_EVERY:
            last_tg_notify = total_done
            elapsed = time.time() - start_time
            rate = success / elapsed if elapsed > 0 else 0
            remaining = len(pending) - i - 1
            eta_hrs = remaining / rate / 3600 if rate > 0 else 0
            pct = len(collected_urls) / len(routes) * 100
            send_telegram(
                f"📊 Wordstat 109K: {pct:.1f}%\n"
                f"✅ {success:,} / ❌ {errors} / 🎯 nonzero: {nonzero}\n"
                f"⏱ {rate:.1f} rps, ETA: {eta_hrs:.1f}ч"
            )

        time.sleep(PAUSE)

    csvfile.close()
    progress["collected"] = list(collected_urls)
    save_progress(progress)

    elapsed = time.time() - start_time

    log(f"\nDone: {success} ok, {errors} errors, {nonzero} nonzero, {elapsed:.0f}s")

    # Write nonzero CSV
    write_nonzero()

    # Final notification
    hours = elapsed / 3600
    send_telegram(
        f"✅ <b>Wordstat 109K завершён!</b>\n"
        f"Обработано: {success:,}\n"
        f"Ошибок: {errors}\n"
        f"С частотностью >0: <b>{nonzero:,}</b>\n"
        f"Время: {hours:.1f}ч\n"
        f"Результат: ws_109k_nonzero.csv"
    )


def write_nonzero():
    """Extract routes with freq > 0 into separate CSV."""
    if not os.path.exists(RESULTS_CSV):
        log("No results file yet.")
        return

    nonzero = []
    with open(RESULTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            tc = int(row["total_count"]) if row["total_count"] else 0
            if tc > 0:
                nonzero.append(row)

    nonzero.sort(key=lambda r: -int(r["total_count"]))

    with open(NONZERO_CSV, "w", encoding="utf-8", newline="") as f:
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

    if nonzero:
        total_freq = sum(int(r["total_count"]) for r in nonzero)
        log(f"  Total frequency: {total_freq:,}")
        log(f"  Top-10:")
        for r in nonzero[:10]:
            log(f"    {r['title']:50s} freq={r['total_count']}")


if __name__ == "__main__":
    main()
