"""
Полный сбор частотности всех маршрутов city2city через API Яндекс Вордстат.
- Resume: пропускает уже собранные фразы (progress.json)
- Останавливается при исчерпании квоты (HTTP 429 или dailyLimitRemaining == 0)
- Сохраняет прогресс после каждого запроса
- Ctrl+C — корректное завершение с сохранением
"""
import csv
import json
import os
import signal
import sys
import time
import requests

TOKEN = "y0__xDj0orvARifkT4gx43HwhYwteKH-Acx1sjvWulgE9dFI7Ibxc5QIiJ10w"
API_URL = "https://api.wordstat.yandex.net/v1/topRequests"
USERINFO_URL = "https://api.wordstat.yandex.net/v1/userInfo"

BASE_DIR = r"C:\Users\furse\Downloads\wordstatapi"
ROUTES_FILE = os.path.join(BASE_DIR, "routes_city2city.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "wordstat_results.csv")
OUTPUT_JSONL = os.path.join(BASE_DIR, "wordstat_raw.jsonl")
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")

TEMPLATES = [
    "такси {city_from} {city_to}",
    "трансфер {city_from} {city_to}",
    "межгород {city_from} {city_to}",
    "такси {city_from} {city_to} цена",
]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

PAUSE = 0.15  # ~7 rps (лимит API: 10 rps)
QUOTA_RESERVE = 5  # остановиться за 5 единиц до нуля

# Флаг для корректного завершения по Ctrl+C
stop_requested = False


def signal_handler(sig, frame):
    global stop_requested
    print("\n\nCtrl+C: завершаю после текущего запроса...")
    stop_requested = True


signal.signal(signal.SIGINT, signal_handler)


def get_quota():
    r = requests.post(USERINFO_URL, headers=HEADERS, json={}, timeout=10)
    r.raise_for_status()
    return r.json()["userInfo"]


def load_routes(path):
    routes = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            routes.append({
                "city_from": row["city_from"],
                "city_to": row["city_to"],
                "page_url": row["page_url"],
            })
    return routes


def generate_all_phrases(routes, templates):
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


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"collected": [], "errors": [], "total_collected": 0, "total_errors": 0}


def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def append_csv(row, file_path):
    fieldnames = [
        "city_from", "city_to", "page_url", "template", "phrase", "total_count",
        "top_1_phrase", "top_1_count", "top_2_phrase", "top_2_count",
        "top_3_phrase", "top_3_count",
    ]
    write_header = not os.path.exists(file_path) or os.path.getsize(file_path) == 0
    with open(file_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def append_jsonl(data, file_path):
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def fetch_wordstat(phrase_text, retries=3):
    payload = {"phrase": phrase_text, "numPhrases": 10}
    for attempt in range(retries):
        try:
            r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=15)
            if r.status_code == 200:
                return r.json(), None
            elif r.status_code == 429:
                return None, f"429_QUOTA:{r.text}"
            elif r.status_code == 503:
                wait = 30 * (attempt + 1)
                print(f" 503, жду {wait}с...", end="", flush=True)
                time.sleep(wait)
                continue
            else:
                return None, f"HTTP {r.status_code}: {r.text}"
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                time.sleep(5)
                continue
            return None, str(e)
    return None, "Max retries exceeded"


def main():
    global stop_requested

    # 1. Проверяем квоту
    print("Проверяю квоту...")
    info = get_quota()
    remaining = info["dailyLimitRemaining"]
    print(f"  Логин: {info['login']}")
    print(f"  Лимит: {info['dailyLimit']}/сутки, {info['limitPerSecond']}/сек")
    print(f"  Осталось сегодня: {remaining}")

    if remaining <= QUOTA_RESERVE:
        print(f"Квота почти исчерпана ({remaining} <= {QUOTA_RESERVE}). Запустите завтра.")
        return

    # 2. Загружаем маршруты и генерируем ВСЕ фразы
    print("\nЗагружаю маршруты...")
    routes = load_routes(ROUTES_FILE)
    all_phrases = generate_all_phrases(routes, TEMPLATES)
    print(f"Всего маршрутов: {len(routes)}")
    print(f"Всего фраз: {len(all_phrases)}")

    # 3. Загружаем прогресс
    progress = load_progress()
    collected_set = set(progress["collected"])
    print(f"Уже собрано: {len(collected_set)}")

    # Фильтруем — только несобранные
    remaining_phrases = [p for p in all_phrases if p["phrase"] not in collected_set]
    print(f"Осталось собрать: {len(remaining_phrases)}")

    # Сколько можем собрать сегодня
    can_collect = min(len(remaining_phrases), remaining - QUOTA_RESERVE)
    print(f"Можем собрать сейчас: {can_collect} (квота: {remaining}, резерв: {QUOTA_RESERVE})")

    if can_collect <= 0:
        print("Нечего собирать или нет квоты. Стоп.")
        return

    # 4. Сбор
    print(f"\nНачинаю сбор ({can_collect} запросов, пауза {PAUSE}с)...\n")
    start_time = time.time()
    session_ok = 0
    session_err = 0

    for i, item in enumerate(remaining_phrases[:can_collect]):
        if stop_requested:
            print("\nОстановлено пользователем.")
            break

        phrase_text = item["phrase"]
        global_pos = len(collected_set) + session_ok + session_err + 1
        print(f"  [{global_pos:5d}/{len(all_phrases)}] {phrase_text}", end=" ... ", flush=True)

        data, err = fetch_wordstat(phrase_text)

        if err:
            if "429_QUOTA" in str(err):
                print("КВОТА ИСЧЕРПАНА. Стоп.")
                break
            print(f"ERR: {err}")
            progress["errors"].append({"phrase": phrase_text, "error": err})
            progress["total_errors"] += 1
            session_err += 1
        else:
            total_count = data.get("totalCount", 0)
            top_requests = data.get("topRequests", [])
            print(f"totalCount={total_count}")

            # CSV строка
            row = {
                "city_from": item["city_from"],
                "city_to": item["city_to"],
                "page_url": item["page_url"],
                "template": item["template"],
                "phrase": phrase_text,
                "total_count": total_count,
            }
            for j in range(3):
                if j < len(top_requests):
                    row[f"top_{j+1}_phrase"] = top_requests[j].get("phrase", "")
                    row[f"top_{j+1}_count"] = top_requests[j].get("count", 0)
                else:
                    row[f"top_{j+1}_phrase"] = ""
                    row[f"top_{j+1}_count"] = 0

            append_csv(row, OUTPUT_CSV)
            append_jsonl({**item, "response": data}, OUTPUT_JSONL)

            progress["collected"].append(phrase_text)
            progress["total_collected"] += 1
            session_ok += 1

        # Сохраняем прогресс каждые 10 запросов
        if (session_ok + session_err) % 10 == 0:
            save_progress(progress)

        time.sleep(PAUSE)

    # Финальное сохранение прогресса
    save_progress(progress)
    elapsed = time.time() - start_time

    # 5. Итоги
    print(f"\n{'='*60}")
    print(f"Сессия завершена!")
    print(f"  За эту сессию: {session_ok} успешных, {session_err} ошибок")
    print(f"  Время сессии: {elapsed:.1f} сек ({elapsed/60:.1f} мин)")
    print(f"  Всего собрано: {progress['total_collected']}/{len(all_phrases)}")
    print(f"  Осталось: {len(all_phrases) - progress['total_collected']}")
    print(f"  CSV: {OUTPUT_CSV}")
    print(f"  JSONL: {OUTPUT_JSONL}")
    print(f"  Прогресс: {PROGRESS_FILE}")

    # Проверяем остаток квоты
    try:
        info2 = get_quota()
        print(f"  Квота: {info2['dailyLimitRemaining']}/{info2['dailyLimit']}")
    except Exception:
        pass

    pct = progress['total_collected'] / len(all_phrases) * 100
    print(f"\n  Прогресс: {pct:.1f}% — запустите скрипт снова завтра для продолжения.")


if __name__ == "__main__":
    main()
