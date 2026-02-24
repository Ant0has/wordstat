#!/usr/bin/env python3
"""
Add new 109K routes to whitelist.json and sitemap.xml on city2city.ru.

1. Read scoring_109k.csv (from wordstat dir)
2. Compare with current whitelist.json
3. Add missing routes to whitelist
4. Regenerate sitemap.xml with all routes
5. Save backup + report
"""

import csv
import json
import os
import shutil
from datetime import datetime

BASE_DIR = "/home/anton-furs/apps/city2city-wordstat"
FRONT_DIR = "/home/anton-furs/apps/city2city.ru/front"

SCORING_CSV = os.path.join(BASE_DIR, "serp_109k_results.csv")
WHITELIST_FILE = os.path.join(FRONT_DIR, "whitelist.json")
SITEMAP_FILE = os.path.join(FRONT_DIR, "public/sitemap.xml")

REPORT_FILE = os.path.join(BASE_DIR, "whitelist_update_report.txt")
ADDED_ROUTES_FILE = os.path.join(BASE_DIR, "added_routes.txt")

TODAY = datetime.now().strftime("%Y-%m-%d")


def load_new_routes():
    """Load routes from SERP 109K results, deduplicate, filter noise."""
    routes = {}
    with open(SCORING_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            slug = row.get("slug", "").strip()
            if not slug:
                continue
            freq = int(row.get("freq", "0") or "0")
            title = row.get("title", "")

            if slug not in routes or freq > routes[slug]["freq"]:
                routes[slug] = {"slug": slug, "freq": freq, "title": title}

    # Filter noise
    filtered = {}
    noise_svo = 0
    noise_mezh = 0
    noise_same = 0
    noise_transfer = 0

    for slug, data in routes.items():
        # svo-taxi single city pages
        if slug.startswith("svo-taxi-"):
            noise_svo += 1
            continue
        # transfer single city pages
        if slug.startswith("transfer-") and slug.count("-") <= 1:
            noise_transfer += 1
            continue
        # mezhgorod aggregate pages
        if "mezhgorod" in slug:
            noise_mezh += 1
            continue
        # digit-prefixed pages (16-mezhgorod-kazan, 102-taxi-mezhgorod-ufa)
        first_part = slug.split("-")[0]
        if first_part.isdigit():
            noise_mezh += 1
            continue
        # same-city
        parts = slug.split("-")
        mid = len(parts) // 2
        if mid > 0 and len(parts) >= 2:
            left = "-".join(parts[:mid])
            right = "-".join(parts[mid:])
            if left == right:
                noise_same += 1
                continue

        filtered[slug] = data

    print(f"Total from SERP: {len(routes)}")
    print(f"Filtered out: svo={noise_svo}, mezhgorod={noise_mezh}, same-city={noise_same}, transfer={noise_transfer}")
    print(f"Real intercity routes: {len(filtered)}")

    return filtered


def update_whitelist(new_routes):
    """Add missing routes to whitelist.json."""
    # Backup
    backup_file = WHITELIST_FILE + f".bak.{TODAY}"
    shutil.copy2(WHITELIST_FILE, backup_file)
    print(f"\nBackup: {backup_file}")

    # Load current whitelist
    with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
        whitelist = json.load(f)

    current_slugs = set(whitelist)
    print(f"Current whitelist: {len(current_slugs)} entries")

    # Find missing routes
    added = []
    already_in = []
    for slug in sorted(new_routes.keys()):
        html_slug = slug + ".html"
        if html_slug not in current_slugs:
            whitelist.append(html_slug)
            added.append(slug)
        else:
            already_in.append(slug)

    print(f"Already in whitelist: {len(already_in)}")
    print(f"NEW added: {len(added)}")
    print(f"New whitelist total: {len(whitelist)}")

    # Sort whitelist
    whitelist.sort()

    # Save
    with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
        json.dump(whitelist, f, ensure_ascii=False)

    return added, already_in


def update_sitemap(new_routes, added_slugs):
    """Regenerate sitemap.xml with all routes."""
    # Backup
    backup_file = SITEMAP_FILE + f".bak.{TODAY}"
    shutil.copy2(SITEMAP_FILE, backup_file)
    print(f"\nSitemap backup: {backup_file}")

    # Read current sitemap URLs
    current_urls = set()
    with open(SITEMAP_FILE, "r", encoding="utf-8") as f:
        content = f.read()
        import re
        for m in re.finditer(r"<loc>(.*?)</loc>", content):
            current_urls.add(m.group(1))

    print(f"Current sitemap URLs: {len(current_urls)}")

    # Add new URLs
    new_entries = []
    for slug in added_slugs:
        url = f"https://city2city.ru/{slug}.html"
        if url not in current_urls:
            new_entries.append(url)

    print(f"New sitemap entries to add: {len(new_entries)}")

    # Append to sitemap (before closing </urlset>)
    if new_entries:
        with open(SITEMAP_FILE, "r", encoding="utf-8") as f:
            sitemap = f.read()

        insert_block = ""
        for url in sorted(new_entries):
            insert_block += f"""  <url>
    <loc>{url}</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
"""
        sitemap = sitemap.replace("</urlset>", insert_block + "</urlset>")

        with open(SITEMAP_FILE, "w", encoding="utf-8") as f:
            f.write(sitemap)

    total_after = len(current_urls) + len(new_entries)
    print(f"Sitemap total URLs after: {total_after}")

    return new_entries


def save_report(new_routes, added, already_in, sitemap_added):
    """Save detailed report and list of added routes."""
    # Added routes list
    with open(ADDED_ROUTES_FILE, "w", encoding="utf-8") as f:
        f.write(f"# Routes added to whitelist.json on {TODAY}\n")
        f.write(f"# Total: {len(added)}\n\n")
        for slug in sorted(added):
            freq = new_routes[slug]["freq"]
            title = new_routes[slug]["title"]
            f.write(f"{slug}\t{freq}\t{title}\n")

    # Full report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(f"WHITELIST & SITEMAP UPDATE REPORT\n")
        f.write(f"Date: {TODAY}\n")
        f.write(f"{'='*60}\n\n")

        f.write(f"New routes analyzed: {len(new_routes)}\n")
        f.write(f"Already in whitelist: {len(already_in)}\n")
        f.write(f"Added to whitelist: {len(added)}\n")
        f.write(f"Added to sitemap: {len(sitemap_added)}\n\n")

        f.write(f"TOP-50 added routes by frequency:\n")
        f.write(f"{'-'*60}\n")
        sorted_added = sorted(added, key=lambda s: new_routes[s]["freq"], reverse=True)
        for i, slug in enumerate(sorted_added[:50]):
            freq = new_routes[slug]["freq"]
            title = new_routes[slug]["title"]
            f.write(f"  {i+1:>3}. {freq:>6}  {slug:<50} {title}\n")

        f.write(f"\n{'='*60}\n")
        f.write(f"Files modified:\n")
        f.write(f"  {WHITELIST_FILE}\n")
        f.write(f"  {SITEMAP_FILE}\n")
        f.write(f"\nBackups created with .bak.{TODAY} suffix\n")

    print(f"\nReport: {REPORT_FILE}")
    print(f"Added routes list: {ADDED_ROUTES_FILE}")


def main():
    print("=" * 60)
    print("WHITELIST & SITEMAP UPDATE")
    print(f"Date: {TODAY}")
    print("=" * 60)

    # Load new routes
    new_routes = load_new_routes()

    # Update whitelist
    added, already_in = update_whitelist(new_routes)

    # Update sitemap
    sitemap_added = update_sitemap(new_routes, added)

    # Save report
    save_report(new_routes, added, already_in, sitemap_added)

    print(f"\n{'='*60}")
    print(f"DONE!")
    print(f"  Whitelist: +{len(added)} routes")
    print(f"  Sitemap: +{len(sitemap_added)} URLs")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
