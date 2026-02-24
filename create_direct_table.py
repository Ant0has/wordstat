"""
Создание таблицы для массовой загрузки в Яндекс Директ (Commander)
из файла final_scoring.csv.
"""

import csv
import os

INPUT_PATH = r"C:\Users\furse\Downloads\wordstatapi\final_scoring.csv"
OUTPUT_PATH = r"C:\Users\furse\Downloads\wordstatapi\direct_upload_table.csv"
SUMMARY_PATH = r"C:\Users\furse\Downloads\wordstatapi\direct_summary.csv"

TARGET_SEGMENTS = {
    "SEO_GOLD_DIRECT",
    "SEO_INVEST_DIRECT",
    "DIRECT_ONLY",
    "DIRECT_TEST",
    "DIRECT_LOW",
}

PRIORITY_MAP = {
    "SEO_GOLD_DIRECT": "ВЫСОКИЙ",
    "DIRECT_ONLY": "ВЫСОКИЙ",
    "SEO_INVEST_DIRECT": "СРЕДНИЙ",
    "DIRECT_TEST": "СРЕДНИЙ",
    "DIRECT_LOW": "НИЗКИЙ",
}

BID_MAP = {
    "ВЫСОКИЙ": "50-80₽",
    "СРЕДНИЙ": "30-50₽",
    "НИЗКИЙ": "10-30₽",
}

PRIORITY_ORDER = {"ВЫСОКИЙ": 0, "СРЕДНИЙ": 1, "НИЗКИЙ": 2}

# City name cleaning rules
CITY_REPLACEMENTS = {
    "международный аэропорт Кольцово ": "Екатеринбург",
    "Международный аэропорт Казань": "Казань",
    "городской округ Тюмень": "Тюмень",
}

CITY_PREFIXES_TO_REMOVE = [
    "рабочий посёлок ",  # longest first
    "посёлок ",
    "село ",
]


def clean_city(name: str) -> str:
    """Clean city name: replace known long names, strip settlement prefixes."""
    cleaned = name.strip()
    for pattern, replacement in CITY_REPLACEMENTS.items():
        if pattern in cleaned:
            cleaned = cleaned.replace(pattern, replacement).strip()
            if not cleaned:
                cleaned = replacement
            return cleaned
    for prefix in CITY_PREFIXES_TO_REMOVE:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    return cleaned


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def main():
    # -- Read input --
    rows = []
    with open(INPUT_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            seg = (row.get("segment") or "").strip()
            if seg in TARGET_SEGMENTS:
                rows.append(row)

    print(f"Прочитано строк с целевыми сегментами: {len(rows)}")

    # -- Build output rows --
    KEYWORD_TEMPLATES = [
        "такси {fr} {to}",
        "такси {fr} {to} цена",
        "заказать такси {fr} {to}",
    ]

    output_rows = []

    for row in rows:
        segment = row["segment"].strip()
        city_from_raw = row["city_from"].strip()
        city_to_raw = row["city_to"].strip()
        city_from = clean_city(city_from_raw)
        city_to = clean_city(city_to_raw)
        price = row["price"].strip()
        total_freq = row["total_freq"].strip()
        page_url = row["page_url"].strip()

        campaign = f"City2City_{segment}"
        group = f"{city_from} - {city_to}"
        priority = PRIORITY_MAP[segment]
        bid_range = BID_MAP[priority]

        title = f"Такси {city_from} → {city_to}"
        title = truncate(title, 56)

        description = (
            f"Заказать такси {city_from} – {city_to}. "
            f"Фиксированная цена {price}₽. Комфортные авто."
        )
        description = truncate(description, 81)

        for tmpl in KEYWORD_TEMPLATES:
            keyword = tmpl.format(fr=city_from, to=city_to)
            output_rows.append(
                {
                    "Кампания": campaign,
                    "Группа": group,
                    "Фраза": keyword,
                    "Заголовок": title,
                    "Текст": description,
                    "Ссылка": page_url,
                    "Цена": price,
                    "Частотность": total_freq,
                    "Сегмент": segment,
                    "Приоритет": priority,
                    "Рекомендация_ставка": bid_range,
                }
            )

    # -- Sort: priority asc, total_freq desc --
    output_rows.sort(
        key=lambda r: (PRIORITY_ORDER[r["Приоритет"]], -float(r["Частотность"]))
    )

    # -- Write main table --
    fieldnames = [
        "Кампания",
        "Группа",
        "Фраза",
        "Заголовок",
        "Текст",
        "Ссылка",
        "Цена",
        "Частотность",
        "Сегмент",
        "Приоритет",
        "Рекомендация_ставка",
    ]

    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Записано строк в direct_upload_table.csv: {len(output_rows)}")

    # -- Build summary --
    from collections import defaultdict

    seg_stats = {}
    seen = set()
    for row in output_rows:
        key = (row["Кампания"], row["Группа"])
        seg = row["Сегмент"]
        freq = float(row["Частотность"])
        if key not in seen:
            seen.add(key)
            if seg not in seg_stats:
                seg_stats[seg] = {"count": 0, "total_freq": 0}
            seg_stats[seg]["count"] += 1
            seg_stats[seg]["total_freq"] += freq

    DAILY_BUDGET_MAP = {
        "SEO_GOLD_DIRECT": "3000-5000₽",
        "DIRECT_ONLY": "3000-5000₽",
        "SEO_INVEST_DIRECT": "1500-3000₽",
        "DIRECT_TEST": "1000-2000₽",
        "DIRECT_LOW": "500-1000₽",
    }

    summary_rows = []
    segment_order = [
        "SEO_GOLD_DIRECT",
        "DIRECT_ONLY",
        "SEO_INVEST_DIRECT",
        "DIRECT_TEST",
        "DIRECT_LOW",
    ]
    for seg in segment_order:
        if seg in seg_stats:
            s = seg_stats[seg]
            summary_rows.append(
                {
                    "Сегмент": seg,
                    "Маршрутов": s["count"],
                    "Суммарная_частотность": int(s["total_freq"]),
                    "Рекомендуемый_дневной_бюджет": DAILY_BUDGET_MAP[seg],
                    "Рекомендуемая_ставка": BID_MAP[PRIORITY_MAP[seg]],
                }
            )

    summary_fields = [
        "Сегмент",
        "Маршрутов",
        "Суммарная_частотность",
        "Рекомендуемый_дневной_бюджет",
        "Рекомендуемая_ставка",
    ]
    with open(SUMMARY_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields, delimiter=";")
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Записано строк в direct_summary.csv: {len(summary_rows)}")

    # -- Print summary to console --
    print("\n" + "=" * 80)
    print("СВОДКА ПО СЕГМЕНТАМ ДЛЯ ЯНДЕКС ДИРЕКТ")
    print("=" * 80)
    total_routes = 0
    total_keywords = 0
    total_freq_all = 0
    for sr in summary_rows:
        cnt = sr["Маршрутов"]
        freq = sr["Суммарная_частотность"]
        total_routes += cnt
        total_keywords += cnt * 3
        total_freq_all += freq
        print(
            f"  {sr['Сегмент']:<22} | "
            f"Маршрутов: {cnt:>5} | "
            f"Частотность: {freq:>10,} | "
            f"Бюджет/день: {sr['Рекомендуемый_дневной_бюджет']:<12} | "
            f"Ставка: {sr['Рекомендуемая_ставка']}"
        )
    print("-" * 80)
    print(f"  ИТОГО: {total_routes} маршрутов, {total_keywords} ключевых фраз, "
          f"суммарная частотность: {total_freq_all:,}")
    print("=" * 80)
    print(f"\nФайлы сохранены:")
    print(f"  {OUTPUT_PATH}")
    print(f"  {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
