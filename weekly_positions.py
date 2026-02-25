#!/usr/bin/env python3
"""
Weekly SERP position monitoring for city2city.ru routes.

Checks positions in Yandex search for priority routes,
saves history, generates report, sends notification.

Usage:
  python3 weekly_positions.py                   # full run
  python3 weekly_positions.py --routes-file X   # custom routes file
  python3 weekly_positions.py --dry-run          # test without API calls
"""

import csv
import json
import os
import sys
import time
import base64
import xml.etree.ElementTree as ET
import argparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================
BASE_DIR = "/home/anton-furs/apps/city2city-monitoring"
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

API_KEY = os.environ.get("YANDEX_API_KEY", "")
FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")

SEARCH_ASYNC_URL = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
OPERATIONS_URL = "https://operation.api.cloud.yandex.net/operations/"

# Files
ROUTES_FILE = os.path.join(DATA_DIR, "monitored_routes.csv")
HISTORY_FILE = os.path.join(DATA_DIR, "positions_history.csv")
LATEST_REPORT = os.path.join(DATA_DIR, "latest_report.txt")
ANALYTICS_FILE = os.path.join(DATA_DIR, "positions_analytics.csv")

# Rate limits
SEARCH_PAUSE = 0.15      # ~7 rps
BATCH_SIZE = 200          # async requests per batch
WAIT_SECS = 90            # wait for deferred results

# Notification config (Telegram bot)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Federal competitors
FEDERAL_COMPETITORS = {
    'kiwitaxi.ru', 'intui.travel', 'gettransfer.com',
    'i-way.ru', 'unitiki.com', 'blablacar.ru',
    'kiwi.taxi', 'gobus.online', 'transfer-way.ru',
    'instamotion.ru', 'poputti.com', 'avito.ru',
    'm.avito.ru', 'youla.ru',
}

# ============================================================
# UTILS
# ============================================================
import requests as req

HEADERS = {
    "Authorization": f"Api-Key {API_KEY}",
    "Content-Type": "application/json",
}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    log_file = os.path.join(LOGS_DIR, f"positions_{datetime.now().strftime('%Y%m%d')}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def api_post(url, payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            r = req.post(url, headers=HEADERS, json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 10 * (attempt + 1)))
                log(f"  429, waiting {wait}s...")
                time.sleep(wait)
            elif r.status_code == 503:
                time.sleep(15 * (attempt + 1))
            else:
                log(f"  HTTP {r.status_code}: {r.text[:200]}")
                time.sleep(3 * (attempt + 1))
        except Exception as e:
            log(f"  Error: {e}")
            time.sleep(5 * (attempt + 1))
    return None


def api_get(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            r = req.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                time.sleep(10 * (attempt + 1))
            else:
                time.sleep(3 * (attempt + 1))
        except Exception as e:
            time.sleep(5 * (attempt + 1))
    return None


def send_telegram(message):
    """Send notification via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("Telegram not configured, skipping notification")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }
        r = req.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            log("Telegram notification sent")
            return True
        else:
            log(f"Telegram error: {r.status_code}")
            return False
    except Exception as e:
        log(f"Telegram error: {e}")
        return False


# ============================================================
# SERP PARSING
# ============================================================
def parse_serp_xml(raw_b64):
    """Parse XML, return position data."""
    try:
        raw = base64.b64decode(raw_b64)
        root = ET.fromstring(raw)
    except Exception:
        return None

    result = {
        "city2city_position": None,
        "city2city_url": "",
        "total_found": 0,
        "federal_count": 0,
        "top5_domains": [],
    }

    # Total found
    for found in root.findall(".//{*}found"):
        if found.get("priority") == "phrase":
            try:
                result["total_found"] = int(found.text)
            except:
                pass
            break

    # Groups (up to 30)
    groups = root.findall(".//{*}group")
    for pos, group in enumerate(groups[:30], 1):
        domain_el = group.find(".//{*}domain")
        url_el = group.find(".//{*}url")
        domain = domain_el.text.lower() if domain_el is not None else ""
        url = url_el.text if url_el is not None else ""

        if pos <= 5:
            result["top5_domains"].append(domain)

        if "city2city" in domain and result["city2city_position"] is None:
            result["city2city_position"] = pos
            result["city2city_url"] = url

        if domain in FEDERAL_COMPETITORS or any(fc in domain for fc in FEDERAL_COMPETITORS):
            result["federal_count"] += 1

    return result


# ============================================================
# LOAD ROUTES TO MONITOR
# ============================================================
def load_monitored_routes():
    """Load routes list for monitoring."""
    if not os.path.exists(ROUTES_FILE):
        log(f"Routes file not found: {ROUTES_FILE}")
        log("Creating empty template...")
        with open(ROUTES_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["page_url", "city_from", "city_to", "price", "segment"])
        return []

    routes = []
    with open(ROUTES_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            routes.append(row)
    return routes


def load_history():
    """Load position history."""
    history = defaultdict(list)  # url -> [(date, position), ...]
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                history[row["page_url"]].append({
                    "date": row["date"],
                    "position": int(row["position"]) if row["position"] else None,
                    "federal_count": int(row.get("federal_count", 0)),
                })
    return dict(history)


def get_previous_position(history, url):
    """Get last known position for a URL."""
    records = history.get(url, [])
    if records:
        return records[-1].get("position")
    return None


# ============================================================
# MAIN COLLECTION
# ============================================================
def collect_positions(routes):
    """Send SERP requests and collect positions."""
    log(f"Collecting positions for {len(routes)} routes...")

    all_results = {}
    ops_pending = {}

    # Send in batches
    for batch_start in range(0, len(routes), BATCH_SIZE):
        batch = routes[batch_start:batch_start + BATCH_SIZE]
        batch_end = min(batch_start + BATCH_SIZE, len(routes))
        log(f"Batch {batch_start+1}-{batch_end}/{len(routes)}: sending...")

        # Send async requests
        for route in batch:
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
                "maxPassages": 0,
                "region": "225",
                "responseFormat": "FORMAT_XML",
            }

            data = api_post(SEARCH_ASYNC_URL, payload)
            if data and data.get("id"):
                ops_pending[route["page_url"]] = {
                    "op_id": data["id"],
                    "route": route,
                }
            time.sleep(SEARCH_PAUSE)

        log(f"Sent {len(ops_pending)} requests, waiting {WAIT_SECS}s...")
        time.sleep(WAIT_SECS)

        # Collect results
        collected = 0
        not_done = []
        for url, info in list(ops_pending.items()):
            resp = api_get(f"{OPERATIONS_URL}{info['op_id']}")
            if resp and resp.get("done"):
                raw = resp.get("response", {}).get("rawData", "")
                if raw:
                    parsed = parse_serp_xml(raw)
                    if parsed:
                        all_results[url] = parsed
                        collected += 1
                del ops_pending[url]
            elif resp and not resp.get("done"):
                not_done.append(url)
            else:
                del ops_pending[url]
            time.sleep(0.05)

        log(f"Collected {collected}, not done: {len(not_done)}")

        # Retry not-done
        if not_done:
            log(f"Retrying {len(not_done)} after 30s...")
            time.sleep(30)
            for url in not_done:
                if url not in ops_pending:
                    continue
                info = ops_pending[url]
                resp = api_get(f"{OPERATIONS_URL}{info['op_id']}")
                if resp and resp.get("done"):
                    raw = resp.get("response", {}).get("rawData", "")
                    if raw:
                        parsed = parse_serp_xml(raw)
                        if parsed:
                            all_results[url] = parsed
                            collected += 1
                if url in ops_pending:
                    del ops_pending[url]

    log(f"Total collected: {len(all_results)}/{len(routes)}")
    return all_results


# ============================================================
# SAVE & REPORT
# ============================================================
def save_results(routes, results, history):
    """Save to history CSV and generate report."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Append to history
    with open(HISTORY_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if os.path.getsize(HISTORY_FILE) == 0:
            writer.writerow(["date", "page_url", "city_from", "city_to",
                             "position", "federal_count", "total_found"])

        for route in routes:
            url = route["page_url"]
            res = results.get(url, {})
            pos = res.get("city2city_position")
            writer.writerow([
                today, url, route["city_from"], route["city_to"],
                pos if pos else "",
                res.get("federal_count", ""),
                res.get("total_found", ""),
            ])

    # Generate analytics CSV (latest snapshot + delta)
    analytics_rows = []
    improved = 0
    dropped = 0
    new_in_top10 = 0
    lost_from_top10 = 0

    for route in routes:
        url = route["page_url"]
        res = results.get(url, {})
        current_pos = res.get("city2city_position")
        prev_pos = get_previous_position(history, url)

        delta = None
        trend = ""
        if current_pos and prev_pos:
            delta = prev_pos - current_pos  # positive = improved
            if delta > 0:
                trend = f"+{delta}"
                improved += 1
            elif delta < 0:
                trend = str(delta)
                dropped += 1
            else:
                trend = "="
        elif current_pos and not prev_pos:
            trend = "NEW"
            new_in_top10 += 1
        elif not current_pos and prev_pos:
            trend = "LOST"
            lost_from_top10 += 1
        else:
            trend = "-"

        analytics_rows.append({
            "page_url": url,
            "city_from": route["city_from"],
            "city_to": route["city_to"],
            "price": route.get("price", ""),
            "segment": route.get("segment", ""),
            "position": current_pos if current_pos else "",
            "prev_position": prev_pos if prev_pos else "",
            "delta": trend,
            "federal_count": res.get("federal_count", ""),
            "top5": "|".join(res.get("top5_domains", [])),
        })

    # Sort: by position (in top first), then by no position
    analytics_rows.sort(key=lambda x: (
        0 if x["position"] else 1,
        x["position"] if x["position"] else 999
    ))

    with open(ANALYTICS_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "page_url", "city_from", "city_to", "price", "segment",
            "position", "prev_position", "delta", "federal_count", "top5"
        ], delimiter=";")
        writer.writeheader()
        for row in analytics_rows:
            writer.writerow(row)

    # Generate text report
    in_top3 = [r for r in analytics_rows if r["position"] and r["position"] <= 3]
    in_top10 = [r for r in analytics_rows if r["position"] and r["position"] <= 10]
    in_top30 = [r for r in analytics_rows if r["position"] and r["position"] <= 30]
    not_found = [r for r in analytics_rows if not r["position"]]

    report = []
    report.append(f"=== CITY2CITY POSITION REPORT: {today} ===")
    report.append(f"")
    report.append(f"Routes monitored: {len(routes)}")
    report.append(f"TOP-3:  {len(in_top3)}")
    report.append(f"TOP-10: {len(in_top10)}")
    report.append(f"TOP-30: {len(in_top30)}")
    report.append(f"Not in TOP-30: {len(not_found)}")
    report.append(f"")
    report.append(f"Changes vs previous:")
    report.append(f"  Improved: {improved}")
    report.append(f"  Dropped:  {dropped}")
    report.append(f"  New in TOP-30:  {new_in_top10}")
    report.append(f"  Lost from TOP-30: {lost_from_top10}")

    if in_top3:
        report.append(f"\n--- TOP-3 ({len(in_top3)}) ---")
        for r in in_top3:
            report.append(f"  #{r['position']} {r['city_from']} -> {r['city_to']} [{r['delta']}]")

    # Biggest improvements
    big_improve = [r for r in analytics_rows if r["delta"].startswith("+") and int(r["delta"]) >= 3]
    if big_improve:
        report.append(f"\n--- BIGGEST IMPROVEMENTS ---")
        for r in sorted(big_improve, key=lambda x: -int(x["delta"]))[:10]:
            report.append(f"  {r['city_from']} -> {r['city_to']}: "
                         f"#{r['prev_position']} -> #{r['position']} ({r['delta']})")

    # Biggest drops
    big_drops = [r for r in analytics_rows if r["delta"].lstrip("-").isdigit()
                 and int(r["delta"]) <= -3]
    if big_drops:
        report.append(f"\n--- BIGGEST DROPS ---")
        for r in sorted(big_drops, key=lambda x: int(x["delta"]))[:10]:
            report.append(f"  {r['city_from']} -> {r['city_to']}: "
                         f"#{r['prev_position']} -> #{r['position']} ({r['delta']})")

    report_text = "\n".join(report)

    with open(LATEST_REPORT, "w", encoding="utf-8") as f:
        f.write(report_text)

    log(f"Report saved to {LATEST_REPORT}")
    log(f"Analytics saved to {ANALYTICS_FILE}")

    return report_text, {
        "total": len(routes),
        "top3": len(in_top3),
        "top10": len(in_top10),
        "top30": len(in_top30),
        "not_found": len(not_found),
        "improved": improved,
        "dropped": dropped,
    }


def build_notification(stats, report_text):
    """Build Telegram notification message."""
    msg = (
        f"<b>city2city.ru Position Report</b>\n"
        f"\n"
        f"Routes: {stats['total']}\n"
        f"TOP-3: {stats['top3']} | TOP-10: {stats['top10']} | TOP-30: {stats['top30']}\n"
        f"Not found: {stats['not_found']}\n"
        f"\n"
    )
    if stats["improved"] or stats["dropped"]:
        msg += (
            f"Changes:\n"
            f"  &#x2B06; Improved: {stats['improved']}\n"
            f"  &#x2B07; Dropped: {stats['dropped']}\n"
        )
    msg += f"\nFull report on server: {ANALYTICS_FILE}"
    return msg


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Weekly SERP position monitor")
    parser.add_argument("--routes-file", help="Custom routes CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Test without API calls")
    args = parser.parse_args()

    if args.routes_file:
        global ROUTES_FILE
        ROUTES_FILE = args.routes_file

    log("=" * 50)
    log("WEEKLY POSITION MONITORING")
    log("=" * 50)

    routes = load_monitored_routes()
    if not routes:
        log("No routes to monitor. Add routes to monitored_routes.csv")
        return

    log(f"Loaded {len(routes)} routes to monitor")

    history = load_history()
    log(f"History: {len(history)} routes with previous data")

    if args.dry_run:
        log("DRY RUN - skipping API calls")
        return

    # Collect positions
    results = collect_positions(routes)

    # Save & report
    report_text, stats = save_results(routes, results, history)

    # Print report
    print("\n" + report_text)

    # Send notification
    notification = build_notification(stats, report_text)
    send_telegram(notification)

    log("\nDone!")


if __name__ == "__main__":
    main()
