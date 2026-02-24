"""
Тестовый сбор частотности для 100 фраз (20 маршрутов × 5 шаблонов)
через API Яндекс Вордстат (api.wordstat.yandex.net)
"""
import csv
import json
import time
import requests

TOKEN = "y0__xDj0orvARifkT4gx43HwhYwteKH-Acx1sjvWulgE9dFI7Ibxc5QIiJ10w"
API_URL = "https://api.wordstat.yandex.net/v1/topRequests"
ROUTES_FILE = r"C:\Users\furse\Downloads\wordstatapi\routes_city2city.csv"
OUTPUT_CSV = r"C:\Users\furse\Downloads\wordstatapi\test_100_results.csv"
OUTPUT_JSONL = r"C:\Users\furse\Downloads\wordstatapi\test_100_raw.jsonl"

TEMPLATES = [
    "такси {city_from} {city_to}",
    "трансфер {city_from} {city_to}",
    "межгород {city_from} {city_to}",
    "такси {city_from} {city_to} цена",
    "{city_from} {city_to} на машине",
]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

PAUSE = 0.15  # ~7 rps (лимит 10 rps)
MAX_ROUTES = 20  # 20 маршрутов × 5 шаблонов = 100 фраз


def load_routes(path, limit):
    routes = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break
            routes.append({
                "city_from": row["city_from"],
                "city_to": row["city_to"],
                "page_url": row["page_url"],
            })
    return routes


def generate_phrases(routes, templates):
    phrases = []
    for route in routes:
        for tpl in templates:
            phrase = tpl.format(
                city_from=route["city_from"],
                city_to=route["city_to"],
            )
            phrases.append({
                "phrase": phrase,
                "template": tpl,
                "city_from": route["city_from"],
                "city_to": route["city_to"],
                "page_url": route["page_url"],
            })
    return phrases


def fetch_wordstat(phrase_text):
    payload = {
        "phrase": phrase_text,
        "numPhrases": 10,
    }
    try:
        r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json(), None
        elif r.status_code == 429:
            return None, f"429 Quota exceeded: {r.text}"
        else:
            return None, f"HTTP {r.status_code}: {r.text}"
    except requests.exceptions.RequestException as e:
        return None, str(e)


def main():
    # 1. Проверяем квоту
    print("Проверяю квоту...")
    r = requests.post(
        "https://api.wordstat.yandex.net/v1/userInfo",
        headers=HEADERS, json={}, timeout=10,
    )
    info = r.json()["userInfo"]
    remaining = info["dailyLimitRemaining"]
    print(f"  Логин: {info['login']}")
    print(f"  Лимит: {info['dailyLimit']}/сутки, {info['limitPerSecond']}/сек")
    print(f"  Осталось: {remaining}")

    if remaining < 100:
        print(f"ОШИБКА: недостаточно квоты ({remaining} < 100). Стоп.")
        return

    # 2. Загружаем маршруты и генерируем фразы
    print(f"\nЗагружаю первые {MAX_ROUTES} маршрутов...")
    routes = load_routes(ROUTES_FILE, MAX_ROUTES)
    phrases = generate_phrases(routes, TEMPLATES)
    print(f"Сгенерировано {len(phrases)} фраз")

    # 3. Собираем данные
    results = []
    errors = []

    print(f"\nНачинаю сбор ({len(phrases)} запросов, пауза {PAUSE}с)...\n")
    start_time = time.time()

    for i, item in enumerate(phrases):
        phrase_text = item["phrase"]
        print(f"  [{i+1:3d}/{len(phrases)}] {phrase_text}", end=" ... ", flush=True)

        data, err = fetch_wordstat(phrase_text)

        if err:
            print(f"ОШИБКА: {err}")
            errors.append({"phrase": phrase_text, "error": err})
            if "429" in str(err):
                print("Квота исчерпана, останавливаюсь.")
                break
        else:
            total_count = data.get("totalCount", 0)
            top_requests = data.get("topRequests", [])
            associations = data.get("associations", [])
            print(f"totalCount={total_count}")

            result_row = {
                "city_from": item["city_from"],
                "city_to": item["city_to"],
                "page_url": item["page_url"],
                "template": item["template"],
                "phrase": phrase_text,
                "total_count": total_count,
            }
            # Добавляем топ-3 вложенных запроса
            for j in range(3):
                if j < len(top_requests):
                    result_row[f"top_{j+1}_phrase"] = top_requests[j].get("phrase", "")
                    result_row[f"top_{j+1}_count"] = top_requests[j].get("count", 0)
                else:
                    result_row[f"top_{j+1}_phrase"] = ""
                    result_row[f"top_{j+1}_count"] = 0

            results.append(result_row)

            # Сохраняем сырой JSON
            with open(OUTPUT_JSONL, "a", encoding="utf-8") as jf:
                raw = {**item, "response": data}
                jf.write(json.dumps(raw, ensure_ascii=False) + "\n")

        time.sleep(PAUSE)

    elapsed = time.time() - start_time

    # 4. Сохраняем CSV
    if results:
        fieldnames = [
            "city_from", "city_to", "page_url", "template", "phrase", "total_count",
            "top_1_phrase", "top_1_count", "top_2_phrase", "top_2_count",
            "top_3_phrase", "top_3_count",
        ]
        with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(results)

    # 5. Итоги
    print(f"\n{'='*60}")
    print(f"Готово!")
    print(f"  Успешно: {len(results)}/{len(phrases)}")
    print(f"  Ошибок:  {len(errors)}")
    print(f"  Время:   {elapsed:.1f} сек")
    print(f"  CSV:     {OUTPUT_CSV}")
    print(f"  JSONL:   {OUTPUT_JSONL}")

    if results:
        # Топ-10 по частотности
        sorted_results = sorted(results, key=lambda x: x["total_count"], reverse=True)
        print(f"\n  Топ-10 по частотности:")
        for r in sorted_results[:10]:
            print(f"    {r['total_count']:>6}  {r['phrase']}")

    # Проверяем остаток квоты
    r2 = requests.post(
        "https://api.wordstat.yandex.net/v1/userInfo",
        headers=HEADERS, json={}, timeout=10,
    )
    info2 = r2.json()["userInfo"]
    print(f"\n  Квота после сбора: {info2['dailyLimitRemaining']}/{info2['dailyLimit']}")


if __name__ == "__main__":
    main()
