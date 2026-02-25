#!/usr/bin/env python3
"""
Apply compromise route update to city2city.ru:
1. Generate SQL to set is_indexable=1 for RETURN_FULL routes
2. Update whitelist.json (add RETURN_FULL + RETURN_NOINDEX)
3. Update sitemap.xml (add only RETURN_FULL)

Run on SERVER: python3 apply_compromise_update.py
"""

import json
import os
import re
import shutil
from datetime import datetime

BASE_DIR = "/home/anton-furs/apps/city2city-wordstat"
FRONT_DIR = "/home/anton-furs/apps/city2city.ru/front"

RETURN_FULL_FILE = os.path.join(BASE_DIR, "compromise_return_full.txt")
RETURN_NOINDEX_FILE = os.path.join(BASE_DIR, "compromise_return_noindex.txt")

WHITELIST_FILE = os.path.join(FRONT_DIR, "whitelist.json")
SITEMAP_FILE = os.path.join(FRONT_DIR, "public/sitemap.xml")
SQL_FILE = os.path.join(BASE_DIR, "compromise_update_indexable.sql")

TODAY = datetime.now().strftime("%Y-%m-%d")


def load_slugs(filepath):
    """Load slugs from a text file (one per line)."""
    slugs = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            slug = line.strip()
            if slug and not slug.startswith("#"):
                slugs.append(slug)
    return slugs


def generate_sql(return_full_slugs):
    """Generate SQL to set is_indexable=1 for RETURN_FULL routes."""
    lines = []
    lines.append(f"-- Compromise update: set is_indexable=1 for {len(return_full_slugs)} routes")
    lines.append(f"-- Generated: {TODAY}")
    lines.append(f"-- These routes will be indexed by search engines")
    lines.append("")
    lines.append("START TRANSACTION;")
    lines.append("")

    # Batch UPDATE using IN clause (more efficient than individual UPDATEs)
    # Split into chunks of 500 for safety
    chunk_size = 500
    for i in range(0, len(return_full_slugs), chunk_size):
        chunk = return_full_slugs[i:i + chunk_size]
        urls_str = ", ".join(f"'{slug}'" for slug in chunk)
        lines.append(f"-- Batch {i // chunk_size + 1}: routes {i + 1}-{i + len(chunk)}")
        lines.append(f"UPDATE routes SET is_indexable = 1 WHERE url IN ({urls_str});")
        lines.append("")

    lines.append("-- Verify counts")
    lines.append("SELECT is_indexable, COUNT(*) as cnt FROM routes GROUP BY is_indexable;")
    lines.append("")
    lines.append("COMMIT;")

    with open(SQL_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"SQL file: {SQL_FILE}")
    print(f"  Routes to set is_indexable=1: {len(return_full_slugs)}")


def update_whitelist(return_full_slugs, return_noindex_slugs):
    """Add compromise routes to whitelist.json."""
    # Backup
    backup_file = WHITELIST_FILE + f".compromise.{TODAY}"
    shutil.copy2(WHITELIST_FILE, backup_file)
    print(f"\nWhitelist backup: {backup_file}")

    # Load current
    with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
        whitelist = json.load(f)

    current_set = set(whitelist)
    print(f"Current whitelist: {len(current_set)} entries")

    # Add RETURN_FULL + RETURN_NOINDEX
    all_new = return_full_slugs + return_noindex_slugs
    added = 0
    already = 0
    for slug in all_new:
        html_slug = slug + ".html"
        if html_slug not in current_set:
            whitelist.append(html_slug)
            current_set.add(html_slug)
            added += 1
        else:
            already += 1

    whitelist.sort()

    with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
        json.dump(whitelist, f, ensure_ascii=False)

    print(f"Already in whitelist: {already}")
    print(f"Added to whitelist: {added}")
    print(f"New whitelist total: {len(whitelist)}")

    return added


def update_sitemap(return_full_slugs):
    """Add RETURN_FULL routes to sitemap.xml."""
    # Backup
    backup_file = SITEMAP_FILE + f".compromise.{TODAY}"
    shutil.copy2(SITEMAP_FILE, backup_file)
    print(f"\nSitemap backup: {backup_file}")

    # Read current URLs
    with open(SITEMAP_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    current_urls = set()
    for m in re.finditer(r"<loc>(.*?)</loc>", content):
        current_urls.add(m.group(1))

    print(f"Current sitemap URLs: {len(current_urls)}")

    # Find new entries
    new_entries = []
    already = 0
    for slug in return_full_slugs:
        url = f"https://city2city.ru/{slug}.html"
        if url not in current_urls:
            new_entries.append(url)
        else:
            already += 1

    print(f"Already in sitemap: {already}")
    print(f"New sitemap entries: {len(new_entries)}")

    # Insert before </urlset>
    if new_entries:
        insert_block = ""
        for url in sorted(new_entries):
            insert_block += f"""  <url>
    <loc>{url}</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
"""
        content = content.replace("</urlset>", insert_block + "</urlset>")

        with open(SITEMAP_FILE, "w", encoding="utf-8") as f:
            f.write(content)

    total = len(current_urls) + len(new_entries)
    print(f"Sitemap total URLs: {total}")

    return len(new_entries)


def main():
    print("=" * 60)
    print("COMPROMISE ROUTE UPDATE")
    print(f"Date: {TODAY}")
    print("=" * 60)

    # Load slug lists
    return_full = load_slugs(RETURN_FULL_FILE)
    return_noindex = load_slugs(RETURN_NOINDEX_FILE)

    print(f"\nROUTES TO RETURN:")
    print(f"  RETURN_FULL (whitelist + sitemap + is_indexable=1): {len(return_full)}")
    print(f"  RETURN_NOINDEX (whitelist only, noindex): {len(return_noindex)}")
    print(f"  TOTAL returning: {len(return_full) + len(return_noindex)}")

    # 1. Generate SQL
    print(f"\n{'='*60}")
    print("STEP 1: Generate SQL for is_indexable update")
    print("=" * 60)
    generate_sql(return_full)

    # 2. Update whitelist
    print(f"\n{'='*60}")
    print("STEP 2: Update whitelist.json")
    print("=" * 60)
    wl_added = update_whitelist(return_full, return_noindex)

    # 3. Update sitemap
    print(f"\n{'='*60}")
    print("STEP 3: Update sitemap.xml")
    print("=" * 60)
    sm_added = update_sitemap(return_full)

    # Summary
    print(f"\n{'='*60}")
    print("DONE!")
    print(f"  SQL generated: {SQL_FILE}")
    print(f"  Whitelist: +{wl_added} entries")
    print(f"  Sitemap: +{sm_added} URLs")
    print(f"\nNEXT STEP: Run the SQL file to update is_indexable in MySQL:")
    print(f"  mysql -u <user> -p'<pass>' <db> < {SQL_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
