#!/usr/bin/env python3
"""
Process Priority 1 routes:
1. Remove PGT/villages and suspicious destinations
2. Calculate prices from distances
3. Generate meta tags
4. Generate page descriptions
5. Output SQL for server update
"""

import csv
import math
import os
import re

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"
INPUT_P1 = os.path.join(BASE_DIR, "priority1_actionable.tsv")
OUTPUT_P1 = os.path.join(BASE_DIR, "priority1_clean.tsv")
OUTPUT_SQL = os.path.join(BASE_DIR, "update_priority1_content.sql")
OUTPUT_DIRECT = os.path.join(BASE_DIR, "priority1_direct_candidates.csv")

# Price formula: 30 rub/km, round up to 500
PRICE_PER_KM = 30
PRICE_BASE = 0

# Words indicating PGT/village/settlement in gorod2
PGT_MARKERS = [
    "посёлок городского типа",
    "поселок городского типа",
    "рабочий посёлок",
    "рабочий поселок",
    "посёлок совхоза",
    "поселок совхоза",
    "посёлок",
    "поселок",
]

# Suspicious generic destination names (repeated across many cities)
SUSPICIOUS_NAMES = {
    "белый", "водный", "орлов", "тульский", "центральный",
    "восточный", "северный", "южный", "западный",
    "первомайский", "комсомольский", "красногвардейский",
    "молочный", "кольцовский",
}

# Keep these despite matching suspicious patterns (real cities)
WHITELIST_CITIES = {
    "октябрьский",  # city in Bashkortostan, 110K population
    "октябрьское",  # could be valid
}


def is_pgt(gorod2: str) -> bool:
    """Check if destination is a PGT/village."""
    g = gorod2.lower().strip()
    for marker in PGT_MARKERS:
        if marker in g:
            return True
    return False


def is_suspicious(gorod2: str) -> bool:
    """Check if destination is a suspicious generic name."""
    g = gorod2.lower().strip()
    # Check if the name (stripped of PGT markers) is in suspicious list
    clean = g
    for marker in PGT_MARKERS:
        clean = clean.replace(marker, "").strip()

    if clean in WHITELIST_CITIES:
        return False

    if clean in SUSPICIOUS_NAMES:
        return True

    return False


def calc_price(distance_km: int) -> int:
    """Calculate price from distance, round UP to nearest 500."""
    raw = PRICE_PER_KM * distance_km + PRICE_BASE
    return int(math.ceil(raw / 500) * 500)


def calc_travel_time(distance_km: int) -> str:
    """Estimate travel time (avg 80 km/h including stops)."""
    hours = distance_km / 80
    h = int(hours)
    m = int((hours - h) * 60)
    if h == 0:
        return f"{m} мин"
    elif m == 0:
        return f"{h} ч"
    else:
        return f"{h} ч {m} мин"


def hours_word(h: int) -> str:
    if h % 10 == 1 and h % 100 != 11:
        return "час"
    elif h % 10 in (2, 3, 4) and h % 100 not in (12, 13, 14):
        return "часа"
    return "часов"


def gen_seo_title(city1: str, city2: str, price: int) -> str:
    """Generate SEO-optimized title."""
    return f"Такси {city1} — {city2} от {price:,}₽ | Заказать трансфер онлайн".replace(",", " ")


def gen_seo_description(city1: str, city2: str, price: int, distance: int, time: str) -> str:
    """Generate SEO meta description."""
    return (
        f"Заказать такси {city1} — {city2} от {price:,}₽. "
        f"Расстояние {distance} км, время в пути ~{time}. "
        f"Подача за 30 мин. Комфортные авто. Фиксированная цена. "
        f"Онлайн-заказ на city2city.ru"
    ).replace(",", " ")


def gen_main_text(city1: str, city2: str, price: int, distance: int, time: str) -> str:
    """Generate unique page description."""
    h = distance / 80
    hours_int = int(h)

    text = f"""Междугородное такси {city1} — {city2} — удобный способ добраться между городами с комфортом и по фиксированной цене. Расстояние по маршруту составляет {distance} км, среднее время в пути — около {time}.

Стоимость поездки от {price:,}₽. Цена фиксированная и не меняется в зависимости от пробок или погодных условий. В стоимость включена подача автомобиля, ожидание и помощь с багажом.

Мы предлагаем несколько классов автомобилей: эконом, комфорт и минивэн для группы до 7 человек. Все машины проходят регулярный техосмотр, водители — опытные и с лицензией.

Заказать такси {city1} — {city2} можно онлайн на сайте или по телефону. Подача автомобиля — от 30 минут. Возможен заказ заранее на определённую дату и время. Доступна обратная поездка {city2} — {city1} по той же стоимости.""".replace(",", " ")

    return text


def gen_faq(city1: str, city2: str, price: int, distance: int, time: str) -> list:
    """Generate FAQ pairs."""
    return [
        (
            f"Сколько стоит такси {city1} — {city2}?",
            f"Стоимость поездки на такси из {city1} в {city2} — от {price:,}₽. Цена фиксированная и зависит от класса автомобиля.".replace(",", " ")
        ),
        (
            f"Сколько ехать от {city1} до {city2}?",
            f"Расстояние {city1} — {city2} составляет {distance} км. Время в пути — примерно {time} в зависимости от дорожных условий."
        ),
        (
            f"Как заказать такси {city1} — {city2}?",
            f"Оформить заказ можно онлайн на сайте city2city.ru, указав дату, время и маршрут. Также доступен заказ по телефону. Подача автомобиля — от 30 минут."
        ),
        (
            f"Можно ли заказать минивэн {city1} — {city2}?",
            f"Да, доступны минивэны на 6-7 пассажиров. Стоимость минивэна по маршруту {city1} — {city2} рассчитывается индивидуально."
        ),
        (
            f"Можно ли с детским креслом?",
            f"Да, детское кресло предоставляется бесплатно по запросу при оформлении заказа. Укажите возраст ребёнка при бронировании."
        ),
    ]


def escape_sql(s: str) -> str:
    """Escape string for SQL."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def main():
    # Read P1
    rows = []
    with open(INPUT_P1, encoding="cp1251") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)

    print(f"Input: {len(rows)} routes")

    # Filter
    removed_pgt = []
    removed_suspicious = []
    clean = []

    for row in rows:
        g2 = row["gorod2"]
        url = row["url"]

        if is_pgt(g2):
            removed_pgt.append((url, g2))
            continue

        if is_suspicious(g2):
            removed_suspicious.append((url, g2))
            continue

        clean.append(row)

    print(f"Removed PGT: {len(removed_pgt)}")
    for u, g in removed_pgt[:5]:
        print(f"  {u.replace('https://city2city.ru/', '')} -> {g}")

    print(f"Removed suspicious: {len(removed_suspicious)}")
    for u, g in removed_suspicious[:5]:
        print(f"  {u.replace('https://city2city.ru/', '')} -> {g}")

    print(f"Clean routes: {len(clean)}")

    # Calculate prices and generate content
    results = []
    sql_lines = []
    sql_lines.append(f"-- Priority 1: Update {len(clean)} routes with content")
    sql_lines.append(f"-- Generated: 2026-02-24")
    sql_lines.append("START TRANSACTION;")
    sql_lines.append("")

    direct_candidates = []

    for row in clean:
        url = row["url"]
        slug = url.replace("https://city2city.ru/", "").replace(".html", "")
        g1 = row["gorod1"]
        g2 = row["gorod2"]
        dist = int(row["rasstoyanie"].strip())

        # Clean city names for display
        city1 = g1.strip()
        city2 = g2.strip()
        # Remove "аэропорт ..." prefix for clean city name
        if city1.startswith("аэропорт"):
            # Extract city name from airport name
            city1_display = city1  # keep full name for title
        else:
            city1_display = city1

        price = calc_price(dist)
        time = calc_travel_time(dist)

        seo_title = gen_seo_title(city1_display, city2, price)
        seo_desc = gen_seo_description(city1_display, city2, price, dist, time)
        main_text = gen_main_text(city1_display, city2, price, dist, time)
        faqs = gen_faq(city1_display, city2, price, dist, time)

        results.append({
            "slug": slug,
            "url": url,
            "city1": city1_display,
            "city2": city2,
            "distance": dist,
            "price": price,
            "time": time,
            "seo_title": seo_title,
        })

        # Direct candidate if price >= 10000
        if price >= 10000:
            direct_candidates.append({
                "url": url,
                "city1": city1_display,
                "city2": city2,
                "distance": dist,
                "price": price,
            })

        # SQL UPDATE
        sql_lines.append(f"-- {city1_display} -> {city2} ({dist}km, {price}rub)")
        sql_lines.append(f"UPDATE routes SET")
        sql_lines.append(f"  price = {price},")
        sql_lines.append(f"  distance_km = {dist},")
        sql_lines.append(f"  seo_title = '{escape_sql(seo_title)}',")
        sql_lines.append(f"  seo_description = '{escape_sql(seo_desc)}',")
        sql_lines.append(f"  main_text = '{escape_sql(main_text)}',")

        for i, (q, a) in enumerate(faqs, 1):
            sql_lines.append(f"  faq{i}_q = '{escape_sql(q)}',")
            sql_lines.append(f"  faq{i}_a = '{escape_sql(a)}',")

        sql_lines.append(f"  content_updated_at = NOW()")
        sql_lines.append(f"WHERE url = '{escape_sql(slug)}';")
        sql_lines.append("")

    sql_lines.append("COMMIT;")

    # Also deindex removed routes
    sql_lines.append("")
    sql_lines.append("-- Deindex PGT and suspicious routes")
    all_removed_slugs = []
    for url, _ in removed_pgt + removed_suspicious:
        slug = url.replace("https://city2city.ru/", "").replace(".html", "")
        all_removed_slugs.append(slug)

    if all_removed_slugs:
        slugs_str = ", ".join(f"'{s}'" for s in all_removed_slugs)
        sql_lines.append(f"UPDATE routes SET is_indexable = 0 WHERE url IN ({slugs_str});")

    # Write outputs
    with open(OUTPUT_SQL, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines))
    print(f"\nSQL: {OUTPUT_SQL}")

    # Write clean TSV
    with open(OUTPUT_P1, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["url", "gorod1", "gorod2", "rasstoyanie", "price", "time", "seo_title"])
        for r in results:
            w.writerow([r["url"], r["city1"], r["city2"], r["distance"], r["price"], r["time"], r["seo_title"]])
    print(f"Clean TSV: {OUTPUT_P1} ({len(results)} rows)")

    # Write Direct candidates
    with open(OUTPUT_DIRECT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["url", "gorod1", "gorod2", "distance", "price"])
        for r in sorted(direct_candidates, key=lambda x: x["price"], reverse=True):
            w.writerow([r["url"], r["city1"], r["city2"], r["distance"], r["price"]])
    print(f"Direct candidates (price>=10k): {OUTPUT_DIRECT} ({len(direct_candidates)} rows)")

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"  Input: {len(rows)}")
    print(f"  Removed (PGT): {len(removed_pgt)}")
    print(f"  Removed (suspicious): {len(removed_suspicious)}")
    print(f"  Clean routes: {len(clean)}")
    print(f"  Direct candidates (>=10k): {len(direct_candidates)}")
    print(f"  Price range: {min(r['price'] for r in results):,} - {max(r['price'] for r in results):,}")
    print(f"  Avg price: {sum(r['price'] for r in results)//len(results):,}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
