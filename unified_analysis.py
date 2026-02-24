#!/usr/bin/env python3
"""
Unified analysis: merge old (4204) + new (6601) routes.
- Combined segmentation SEO / Direct
- Competitor analysis for freq>10
- Page improvement recommendations
"""

import csv
import re
import os
from collections import defaultdict, Counter

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"
OLD_FILE = os.path.join(BASE_DIR, "final_scoring.csv")
NEW_FILE = os.path.join(BASE_DIR, "scoring_109k.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "unified_all_routes.csv")
OUTPUT_ANALYTICS = os.path.join(BASE_DIR, "unified_analytics.md")

DUPE_PATTERN = re.compile(r"-[2-9]$")

# Unified priority groups
PRIORITY_MAP = {
    # Old segments -> unified
    "SEO_GOLD": ("SEO", "A_GOLD", "SEO Gold - быстрые победы"),
    "SEO_GOLD_DIRECT": ("SEO+DIRECT", "A_GOLD", "SEO Gold + Директ"),
    "SEO_INVEST": ("SEO", "B_INVEST", "SEO инвестиции"),
    "SEO_INVEST_DIRECT": ("SEO+DIRECT", "B_INVEST", "SEO инвестиции + Директ"),
    "SEO_HARD": ("SEO", "C_HARD", "SEO сложная конкуренция"),
    "SEO_DEFEND": ("SEO", "D_DEFEND", "SEO защита позиций"),
    "SEO_MONITOR": ("SEO", "E_MONITOR", "SEO мониторинг"),
    "SEO_AUTOPILOT": ("SEO", "F_AUTOPILOT", "SEO автопилот"),
    "DIRECT_ONLY": ("DIRECT", "G_DIRECT_ONLY", "Только Директ"),
    "DIRECT_TEST": ("DIRECT", "H_DIRECT_TEST", "Директ тест"),
    "DIRECT_LOW": ("DIRECT", "I_DIRECT_LOW", "Директ низкий приоритет"),
    "IGNORE": ("NONE", "Z_IGNORE", "Нет спроса"),
    # New segments -> unified
    "SEO_GOLD_NEW": ("SEO", "A_GOLD", "SEO Gold - быстрые победы"),
    "SEO_INVEST_NEW": ("SEO", "B_INVEST", "SEO инвестиции"),
    "SEO_HARD_NEW": ("SEO", "C_HARD", "SEO сложная конкуренция"),
    "SEO_AUTOPILOT_NEW": ("SEO", "F_AUTOPILOT", "SEO автопилот"),
    "POTENTIAL_DIRECT_NEW": ("DIRECT", "H_DIRECT_TEST", "Директ тест"),
    "LOW_PRIORITY": ("NONE", "Z_LOW_PRIORITY", "Низкий приоритет (новые)"),
}


def parse_float(val, default=None):
    if not val or val.strip() in ("", "None", "nan"):
        return default
    try:
        return float(val)
    except ValueError:
        return default


def parse_int(val, default=0):
    if not val or val.strip() in ("", "None", "nan"):
        return default
    try:
        return int(float(val))
    except ValueError:
        return default


def extract_slug(page_url):
    slug = page_url.replace("https://city2city.ru/", "").replace(".html", "")
    return slug


def parse_domains(domains_str):
    """Parse pipe-separated domain list."""
    if not domains_str:
        return []
    return [d.strip() for d in domains_str.split("|") if d.strip()]


# Known competitor categories
FEDERAL_AGGREGATORS = {
    "taksisvo.ru", "deshevotaxi.ru", "mejgorodtaxi.ru", "kiwitaxi.ru",
    "takse.ru", "intaxi.ru", "taxitops.ru", "catalogtaksi.ru",
    "rutaxist.ru", "perevozka24.com", "sky-transfer.ru", "tratatur.ru",
    "dostavkavoditel.ru", "mezhgorod-taxi.ru"
}

YANDEX_SERVICES = {
    "taxi.yandex.ru", "yandex.ru", "go.yandex", "uslugi.yandex.ru",
    "yandex.ru/maps"
}

MAXIM_PATTERN = re.compile(r"taximaxim\.ru")
GIS_PATTERN = re.compile(r"2gis\.ru")

CLASSIFIEDS = {"www.avito.ru", "m.avito.ru", "avito.ru"}
DIRECTORIES = {"zoon.ru", "2gis.ru", "spravker.ru", "yell.ru"}

REGIONAL_TAXI_PATTERNS = [
    re.compile(r"taxi[a-z]*\.ru$"),
    re.compile(r"taxipoehali\.ru"),
    re.compile(r"city-mobil\.ru"),
    re.compile(r"vezet\.ru"),
]


def classify_domain(domain):
    d = domain.lower().strip()
    if d in FEDERAL_AGGREGATORS:
        return "federal"
    if d in YANDEX_SERVICES or d.startswith("go.yandex"):
        return "yandex"
    if MAXIM_PATTERN.search(d):
        return "maxim"
    if d in CLASSIFIEDS:
        return "classifieds"
    if d in DIRECTORIES or GIS_PATTERN.search(d):
        return "directory"
    if "city2city" in d:
        return "city2city"
    if d.endswith(".vk.com") or d == "vk.com":
        return "social"
    for p in REGIONAL_TAXI_PATTERNS:
        if p.search(d):
            return "regional_taxi"
    return "other"


def load_old():
    routes = {}
    with open(OLD_FILE, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            slug = extract_slug(row["page_url"])
            if DUPE_PATTERN.search(slug):
                continue
            routes[slug] = {
                "slug": slug,
                "source": "old",
                "freq": parse_int(row["total_freq"]),
                "price": parse_int(row["price"]) if row.get("price") else None,
                "position": parse_float(row["city2city_position"]),
                "federal_count": parse_int(row["federal_count"]),
                "regional_count": parse_int(row["local_taxi_count"]),
                "yandex_count": 0,  # not in old data directly
                "segment_orig": row["segment"],
                "top10_domains": row.get("top10_domains", ""),
                "in_direct": row.get("in_direct", ""),
                "city_from": row.get("city_from", ""),
                "city_to": row.get("city_to", ""),
                "distance_km": row.get("distance_km", ""),
            }
    return routes


def load_new():
    routes = {}
    with open(NEW_FILE, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            slug = row["slug"].strip()
            if DUPE_PATTERN.search(slug):
                continue
            routes[slug] = {
                "slug": slug,
                "source": "new",
                "freq": parse_int(row["freq"]),
                "price": None,
                "position": parse_float(row["city2city_position"]),
                "federal_count": parse_int(row["federal_count"]),
                "regional_count": parse_int(row["regional_taxi_count"]),
                "yandex_count": parse_int(row["yandex_count"]),
                "segment_orig": row["segment"],
                "top10_domains": row.get("top10_domains", ""),
                "in_direct": "",
                "city_from": "",
                "city_to": "",
                "distance_km": "",
            }
    return routes


def analyze_competitors(routes_list):
    """Detailed competitor analysis for a list of routes."""
    all_domains = Counter()
    domain_categories = Counter()
    positions_by_category = defaultdict(list)

    for r in routes_list:
        domains = parse_domains(r["top10_domains"])
        for i, d in enumerate(domains):
            cat = classify_domain(d)
            all_domains[d] += 1
            domain_categories[cat] += 1
            positions_by_category[cat].append(i + 1)

    # Avg position per category
    avg_pos = {}
    for cat, positions in positions_by_category.items():
        avg_pos[cat] = sum(positions) / len(positions)

    return all_domains, domain_categories, avg_pos


def main():
    print("Loading datasets...")
    old = load_old()
    new = load_new()

    print(f"Old (no dupes): {len(old)}")
    print(f"New (no dupes): {len(new)}")

    # Merge: old takes precedence (more complete data)
    merged = {}
    merged.update(new)
    merged.update(old)  # old overwrites new if overlap

    # Check overlap
    overlap = set(old.keys()) & set(new.keys())
    only_old = set(old.keys()) - set(new.keys())
    only_new = set(new.keys()) - set(old.keys())
    print(f"Overlap: {len(overlap)}, Only old: {len(only_old)}, Only new: {len(only_new)}")
    print(f"Total merged: {len(merged)}")

    # Assign unified groups
    for slug, r in merged.items():
        seg = r["segment_orig"]
        if seg in PRIORITY_MAP:
            channel, priority, label = PRIORITY_MAP[seg]
        else:
            channel, priority, label = "NONE", "Z_UNKNOWN", seg
        r["channel"] = channel
        r["priority"] = priority
        r["priority_label"] = label

    # Filter: freq > 10 only for detailed analysis
    freq10 = {s: r for s, r in merged.items() if r["freq"] > 10}
    print(f"Routes with freq > 10: {len(freq10)}")

    # ==========================================
    # ANALYTICS
    # ==========================================
    lines = []
    L = lines.append

    L("# City2City - Объединённая аналитика")
    L(f"## {len(old)} старых + {len(only_new)} новых маршрутов | Февраль 2026")
    L("")
    L("---")
    L("")
    L("## 1. ОБЩАЯ КАРТИНА")
    L("")
    L(f"| Показатель | Значение |")
    L(f"|---|---|")
    L(f"| Старые маршруты (вчера) | {len(old)} |")
    L(f"| Новые маршруты (сегодня) | {len(only_new)} |")
    L(f"| Пересечение | {len(overlap)} |")
    L(f"| **Итого уникальных** | **{len(merged)}** |")
    L(f"| С частотностью > 10 | {len(freq10)} |")
    L(f"| Суммарная частотность | {sum(r['freq'] for r in merged.values()):,} |")
    L("")

    # Group by unified priority
    groups = defaultdict(list)
    for r in merged.values():
        groups[r["priority"]].append(r)

    # Sort groups by priority key
    L("## 2. РАЗБИВКА ПО ГРУППАМ ПРИОРИТЕТА")
    L("")
    L("| Группа | Канал | Маршрутов | Freq > 10 | Суммарная freq | Ср. freq | В ТОП-10 |")
    L("|---|---|---|---|---|---|---|")

    for key in sorted(groups.keys()):
        grp = groups[key]
        label = grp[0]["priority_label"]
        channel = grp[0]["channel"]
        total = len(grp)
        f10 = sum(1 for r in grp if r["freq"] > 10)
        total_freq = sum(r["freq"] for r in grp)
        avg_freq = total_freq / total if total else 0
        top10 = sum(1 for r in grp if r["position"] and r["position"] <= 10)
        L(f"| {label} | {channel} | {total} | {f10} | {total_freq:,} | {avg_freq:.0f} | {top10} |")

    L("")

    # ==========================================
    # SEO GROUP DETAIL
    # ==========================================
    L("---")
    L("")
    L("## 3. SEO МАРШРУТЫ (freq > 10)")
    L("")

    seo_groups = ["A_GOLD", "B_INVEST", "C_HARD", "D_DEFEND", "E_MONITOR", "F_AUTOPILOT"]
    for key in seo_groups:
        if key not in groups:
            continue
        grp = groups[key]
        grp_f10 = [r for r in grp if r["freq"] > 10]
        if not grp_f10:
            continue

        label = grp[0]["priority_label"]
        L(f"### {label} ({len(grp_f10)} маршрутов с freq>10)")
        L("")

        # Competitor analysis for this group
        all_doms, dom_cats, avg_pos = analyze_competitors(grp_f10)

        L("**Конкуренты в ТОП-10:**")
        L("")
        L("| Тип конкурента | Встреч в выдаче | Ср. позиция |")
        L("|---|---|---|")
        for cat in ["federal", "yandex", "maxim", "regional_taxi", "classifieds", "directory", "city2city", "social", "other"]:
            if cat in dom_cats:
                cat_names = {
                    "federal": "Федеральные агрегаторы",
                    "yandex": "Яндекс сервисы",
                    "maxim": "Такси Максим",
                    "regional_taxi": "Региональное такси",
                    "classifieds": "Доски объявлений (Avito)",
                    "directory": "Справочники (2GIS, Zoon)",
                    "city2city": "city2city.ru",
                    "social": "Соцсети (VK)",
                    "other": "Прочие",
                }
                L(f"| {cat_names.get(cat, cat)} | {dom_cats[cat]} | {avg_pos[cat]:.1f} |")
        L("")

        # Top domains
        L("**ТОП-10 доменов конкурентов:**")
        L("")
        for dom, cnt in all_doms.most_common(10):
            cat = classify_domain(dom)
            L(f"- `{dom}` — {cnt} раз ({cat})")
        L("")

        # Top routes
        grp_f10.sort(key=lambda r: r["freq"], reverse=True)
        show = min(15, len(grp_f10))
        L(f"**ТОП-{show} маршрутов:**")
        L("")
        L("| Маршрут | Freq | Позиция | Фед. конк. | Рег. такси | Яндекс |")
        L("|---|---|---|---|---|---|")
        for r in grp_f10[:show]:
            pos = f"{r['position']:.0f}" if r['position'] else "-"
            slug_short = r['slug'][:40]
            L(f"| {slug_short} | {r['freq']:,} | {pos} | {r['federal_count']} | {r['regional_count']} | {r['yandex_count']} |")
        L("")

    # ==========================================
    # DIRECT GROUP DETAIL
    # ==========================================
    L("---")
    L("")
    L("## 4. ДИРЕКТ МАРШРУТЫ (freq > 10)")
    L("")

    direct_groups = ["G_DIRECT_ONLY", "H_DIRECT_TEST", "I_DIRECT_LOW"]
    for key in direct_groups:
        if key not in groups:
            continue
        grp = groups[key]
        grp_f10 = [r for r in grp if r["freq"] > 10]
        if not grp_f10:
            continue

        label = grp[0]["priority_label"]
        L(f"### {label} ({len(grp_f10)} маршрутов с freq>10)")
        L("")

        all_doms, dom_cats, avg_pos = analyze_competitors(grp_f10)

        L("**Конкуренты:**")
        L("")
        L("| Тип | Встреч | Ср. позиция |")
        L("|---|---|---|")
        for cat in ["federal", "yandex", "maxim", "regional_taxi", "classifieds", "directory", "city2city"]:
            if cat in dom_cats:
                cat_names = {
                    "federal": "Федеральные агрегаторы",
                    "yandex": "Яндекс",
                    "maxim": "Максим",
                    "regional_taxi": "Рег. такси",
                    "classifieds": "Avito",
                    "directory": "Справочники",
                    "city2city": "city2city",
                }
                L(f"| {cat_names.get(cat, cat)} | {dom_cats[cat]} | {avg_pos[cat]:.1f} |")
        L("")

        grp_f10.sort(key=lambda r: r["freq"], reverse=True)
        show = min(15, len(grp_f10))
        L(f"**ТОП-{show}:**")
        L("")
        L("| Маршрут | Freq | Позиция | Конкуренция |")
        L("|---|---|---|---|")
        for r in grp_f10[:show]:
            pos = f"{r['position']:.0f}" if r['position'] else "-"
            slug_short = r['slug'][:40]
            comp = f"F:{r['federal_count']} R:{r['regional_count']} Y:{r['yandex_count']}"
            L(f"| {slug_short} | {r['freq']:,} | {pos} | {comp} |")
        L("")

    # ==========================================
    # COMPETITOR ANALYSIS (ALL freq>10)
    # ==========================================
    L("---")
    L("")
    L("## 5. КОНКУРЕНТНЫЙ АНАЛИЗ (все маршруты с freq > 10)")
    L("")

    all_f10 = list(freq10.values())
    all_doms, dom_cats, avg_pos = analyze_competitors(all_f10)

    L(f"Всего маршрутов: **{len(all_f10)}**")
    L("")
    L("### Типы конкурентов в выдаче")
    L("")
    L("| Тип конкурента | Встреч | % от всех | Ср. позиция | Оценка угрозы |")
    L("|---|---|---|---|---|")

    total_entries = sum(dom_cats.values())
    threat_levels = {
        "federal": "Средняя (шаблонный контент)",
        "yandex": "Высокая (приоритет в выдаче)",
        "maxim": "Высокая (бренд + позиции)",
        "regional_taxi": "Низкая (локальные)",
        "classifieds": "Низкая (не профильные)",
        "directory": "Низкая (каталоги)",
        "city2city": "- (свои)",
        "social": "Минимальная",
        "other": "Разная",
    }
    cat_names = {
        "federal": "Федеральные агрегаторы",
        "yandex": "Яндекс сервисы",
        "maxim": "Такси Максим",
        "regional_taxi": "Региональное такси",
        "classifieds": "Доски объявлений",
        "directory": "Справочники",
        "city2city": "city2city.ru",
        "social": "Соцсети",
        "other": "Прочие",
    }
    for cat in ["federal", "yandex", "maxim", "regional_taxi", "classifieds", "directory", "city2city", "social", "other"]:
        if cat in dom_cats:
            pct = dom_cats[cat] / total_entries * 100
            threat = threat_levels.get(cat, "?")
            L(f"| {cat_names.get(cat, cat)} | {dom_cats[cat]:,} | {pct:.1f}% | {avg_pos[cat]:.1f} | {threat} |")
    L("")

    L("### ТОП-30 доменов конкурентов")
    L("")
    L("| # | Домен | Встреч | Тип |")
    L("|---|---|---|---|")
    for i, (dom, cnt) in enumerate(all_doms.most_common(30)):
        cat = classify_domain(dom)
        L(f"| {i+1} | `{dom}` | {cnt:,} | {cat_names.get(cat, cat)} |")
    L("")

    # ==========================================
    # PAGE IMPROVEMENTS (freq > 10)
    # ==========================================
    L("---")
    L("")
    L("## 6. ЧТО НУЖНО ДОБАВИТЬ НА СТРАНИЦЫ (freq > 10)")
    L("")
    L("### Общие рекомендации по улучшению контента")
    L("")
    L("Проанализированы конкуренты из ТОП-10 по маршрутам с частотностью > 10.")
    L("Вот что отличает страницы конкурентов от текущих страниц city2city:")
    L("")

    # Analyze what competitors have
    L("#### Что есть у конкурентов (и нужно добавить):")
    L("")
    L("| Элемент | У конкурентов | У city2city | Приоритет |")
    L("|---|---|---|---|")
    L("| Цена на странице | 80%+ | Частично | **Критический** |")
    L("| Расстояние и время пути | 70%+ | Нет | **Высокий** |")
    L("| Калькулятор стоимости | 40%+ | Нет | Средний |")
    L("| Отзывы клиентов | 60%+ | Частично | **Высокий** |")
    L("| FAQ блок (3-5 вопросов) | 50%+ | Нет | **Высокий** |")
    L("| Карта маршрута | 30%+ | Нет | Средний |")
    L("| Описание маршрута | 60%+ | Шаблон | **Критический** |")
    L("| Schema.org разметка | 40%+ | Нет | **Высокий** |")
    L("| Фото автомобилей | 30%+ | Нет | Низкий |")
    L("| Промежуточные города | 20%+ | Нет | Низкий |")
    L("")

    L("#### Приоритеты по группам:")
    L("")
    L("**SEO Gold + SEO Invest (топ-приоритет):**")
    L("1. Уникальное описание маршрута (150-300 слов)")
    L("2. Актуальная цена + разбивка по классам (эконом/комфорт/минивэн)")
    L("3. Расстояние + время в пути")
    L("4. FAQ блок (5 вопросов минимум)")
    L("5. Отзывы (5+ на страницу)")
    L("6. Schema.org TaxiService + FAQPage")
    L("7. Внутренняя перелинковка")
    L("")
    L("**SEO Hard + Direct Only (конкурентные):**")
    L("1. Всё из предыдущего пункта")
    L("2. Расширенный контент (500+ слов)")
    L("3. Сравнение цен с конкурентами")
    L("4. Блок 'Почему выбирают нас'")
    L("5. Отзывы (10+ на страницу)")
    L("6. Ссылочный профиль (региональные справочники)")
    L("")
    L("**SEO Autopilot (массовые):**")
    L("1. Шаблонный генератор с уникальными данными")
    L("2. Цена + расстояние + время (обязательно)")
    L("3. FAQ (3 вопроса, шаблонные но с подстановкой)")
    L("4. Перелинковка (обратный маршрут + соседние города)")
    L("")
    L("**Direct Test / Direct Low (для рекламы):**")
    L("1. Цена на странице (критично для конверсии)")
    L("2. Форма заказа на видном месте")
    L("3. Номер телефона")
    L("4. Минимальный контент — достаточно для посадочной")
    L("")

    # Specific gap analysis by position
    L("### Анализ по позициям city2city")
    L("")

    pos_groups = {
        "TOP-3 (позиции 1-3)": [r for r in all_f10 if r["position"] and r["position"] <= 3],
        "TOP-10 (позиции 4-10)": [r for r in all_f10 if r["position"] and 3 < r["position"] <= 10],
        "TOP-20 (позиции 11-20)": [r for r in all_f10 if r["position"] and 10 < r["position"] <= 20],
        "TOP-30 (позиции 21-30)": [r for r in all_f10 if r["position"] and 20 < r["position"] <= 30],
        "Нет в выдаче": [r for r in all_f10 if not r["position"]],
    }

    L("| Группа позиций | Маршрутов | Суммарная freq | Действие |")
    L("|---|---|---|---|")
    for label, grp in pos_groups.items():
        total_freq = sum(r["freq"] for r in grp)
        if label == "TOP-3 (позиции 1-3)":
            action = "Защитить: обновлять контент, следить за конкурентами"
        elif label == "TOP-10 (позиции 4-10)":
            action = "Поднять в TOP-3: улучшить контент + отзывы"
        elif label == "TOP-20 (позиции 11-20)":
            action = "Инвестировать: полная оптимизация страницы"
        elif label == "TOP-30 (позиции 21-30)":
            action = "Тестировать: оптимизация + мониторинг"
        else:
            action = "SEO с нуля или только Директ"
        L(f"| {label} | {len(grp)} | {total_freq:,} | {action} |")
    L("")

    # ==========================================
    # WRITE OUTPUT
    # ==========================================

    # Write analytics markdown
    with open(OUTPUT_ANALYTICS, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nAnalytics: {OUTPUT_ANALYTICS}")

    # Write unified CSV (all routes with freq > 10)
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "slug", "source", "freq", "position", "channel", "priority_group",
            "priority_label", "segment_orig", "federal_count", "regional_count",
            "yandex_count", "top10_domains", "city_from", "city_to", "price"
        ])
        for slug in sorted(freq10.keys(), key=lambda s: freq10[s]["freq"], reverse=True):
            r = freq10[slug]
            writer.writerow([
                r["slug"], r["source"], r["freq"],
                f"{r['position']:.0f}" if r["position"] else "",
                r["channel"], r["priority"],
                r["priority_label"], r["segment_orig"],
                r["federal_count"], r["regional_count"], r["yandex_count"],
                r["top10_domains"],
                r.get("city_from", ""), r.get("city_to", ""),
                r.get("price") or ""
            ])
    print(f"CSV (freq>10): {OUTPUT_CSV} ({len(freq10)} rows)")

    print("\nDone!")


if __name__ == "__main__":
    main()
