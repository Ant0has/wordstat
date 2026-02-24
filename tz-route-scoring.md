# ТЗ: Пайплайн скоринга маршрутов city2city через Yandex Search API

## Цель проекта

Построить автоматизированный Python-пайплайн, который для ~4 000 маршрутов межгородского такси (city2city.ru) собирает данные из Yandex Search API (Wordstat + Web Search), рассчитывает композитный скор по нескольким осям и сегментирует маршруты на категории: SEO-приоритет, Директ-приоритет, автопилот, игнорировать.

## Контекст бизнеса

- city2city.ru — агрегатор межгородского такси, ~4 093 маршрута между городами России
- Каждый маршрут = отдельная SEO-страница на сайте (формат `/moskva-kazan`, `/rostov-moskva`)
- Задача: понять, какие маршруты продвигать через SEO (органика), какие через Яндекс.Директ (платный трафик), какие оставить как есть
- Ключевые факторы решения: спрос (частотность), сила конкурентов в выдаче, география спроса, сезонность

## Входные данные

### Файл маршрутов (CSV)
Пользователь предоставит CSV-файл со столбцами (минимум):
```
slug,city_from,city_to,distance_km,priority
moskva-kazan,Москва,Казань,815,1
rostov-moskva,Ростов-на-Дону,Москва,1076,1
...
```

- `slug` — URL-slug маршрута на сайте
- `city_from`, `city_to` — названия городов
- `distance_km` — расстояние
- `priority` — текущий приоритет (1 = whitelist, 2 = graylist)

Если у пользователя есть дополнительные колонки (население городов, текущая позиция в Яндексе, данные из Метрики), они должны быть подхвачены и использованы.

### API-ключи
Пользователь предоставит:
- `YANDEX_CLOUD_API_KEY` — API-ключ сервисного аккаунта Yandex Cloud
- `YANDEX_CLOUD_FOLDER_ID` — ID каталога в Yandex Cloud

## Архитектура пайплайна

Пайплайн состоит из 5 модулей, выполняемых последовательно. Каждый модуль сохраняет промежуточные результаты в файл, чтобы можно было перезапустить с любого этапа (resume capability).

```
[1. Генерация запросов] → queries.csv
        ↓
[2. Wordstat: частотность] → wordstat_results.csv
        ↓
[3. Wordstat: регионы + динамика] → regions_results.csv, dynamics_results.csv
        ↓
[4. Web Search: SERP-анализ] → serp_results.csv
        ↓
[5. Скоринг + сегментация] → final_scoring.csv + отчёт
```

---

## Модуль 1: Генерация поисковых запросов

### Задача
Для каждого маршрута сформировать набор поисковых запросов.

### Логика
Для каждой пары (city_from, city_to) генерируются запросы:
```
такси {city_from} {city_to}
трансфер {city_from} {city_to}
межгород {city_from} {city_to}
```

Также генерируются обратные запросы (city_to → city_from), т.к. спрос часто асимметричен.

### Выход
Файл `queries.csv`:
```
slug,city_from,city_to,direction,query_type,query
moskva-kazan,Москва,Казань,forward,taxi,"такси Москва Казань"
moskva-kazan,Москва,Казань,forward,transfer,"трансфер Москва Казань"
moskva-kazan,Москва,Казань,reverse,taxi,"такси Казань Москва"
...
```

---

## Модуль 2: Wordstat — сбор частотности (GetTop)

### API endpoint
```
POST https://searchapi.api.cloud.yandex.net/v2/wordstat/top
```

### Заголовки
```
Authorization: Api-Key {YANDEX_CLOUD_API_KEY}
Content-Type: application/json
```

### Тело запроса
```json
{
  "folderId": "{YANDEX_CLOUD_FOLDER_ID}",
  "phrase": "такси Москва Казань"
}
```

### Что извлекаем из ответа
- `count` — частотность фразы (это аналог "показов в месяц" из Wordstat)
- Список `topResults` — связанные запросы с их частотностью (полезно для расширения семантики)

### Логика обработки
1. Для каждого маршрута отправляем GetTop для основного запроса "такси {city_from} {city_to}"
2. Суммируем частотность прямого и обратного направлений
3. Из связанных запросов (topResults) извлекаем дополнительные варианты поисковых фраз, которые люди используют для этого маршрута (например, "водитель Москва Казань", "попутчик Москва Казань")

### Rate limiting
- Wordstat в Preview — квоты ограничены. Необходимо:
  - Начать с 1 запроса в секунду
  - При получении 429 — exponential backoff (начинать с времени из заголовка Time to refill)
  - Сохранять прогресс после каждых 100 запросов
  - Логировать все ошибки

### Resume capability
- Перед запросом проверять, есть ли уже результат для данного query в wordstat_results.csv
- Если есть — пропускать

### Выход
Файл `wordstat_results.csv`:
```
slug,direction,query,frequency,related_queries_json
moskva-kazan,forward,"такси Москва Казань",12500,"[{""query"":""такси москва казань цена"",""count"":3200}, ...]"
moskva-kazan,reverse,"такси Казань Москва",4800,"[...]"
```

---

## Модуль 3: Wordstat — регионы и динамика

### 3a. GetRegionsDistribution
```
POST https://searchapi.api.cloud.yandex.net/v2/wordstat/regions
```

Тело:
```json
{
  "folderId": "{YANDEX_CLOUD_FOLDER_ID}",
  "phrase": "такси Москва Казань"
}
```

### Что извлекаем
- Массив `results[]` с полями: `region` (код региона), `count` (количество запросов), `share` (доля), `affinityIndex` (индекс аффинити — насколько регион "перегрет" по этому запросу)

### Зачем это нужно
- Если маршрут "Краснодар — Сочи" ищут из Москвы — это туристический трафик → Директ нужно настраивать на Москву, не на Краснодар
- affinityIndex > 100% = регион ищет этот маршрут чаще среднего → приоритетный геотаргетинг

### Логика
- Запрашиваем для ОСНОВНОГО запроса каждого маршрута (только "такси {from} {to}", без обратного — экономим квоту)
- Сохраняем топ-5 регионов по count

### 3b. GetDynamics (ОПЦИОНАЛЬНО — только для топ-500 маршрутов по частотности)
```
POST https://searchapi.api.cloud.yandex.net/v2/wordstat/dynamics
```

Тело:
```json
{
  "folderId": "{YANDEX_CLOUD_FOLDER_ID}",
  "phrase": "такси Москва Казань",
  "aggregation": "MONTH",
  "dateFrom": "2025-01-01",
  "dateTo": "2026-02-01"
}
```

### Что извлекаем
- Массив точек `{date, count}` — помесячная динамика частотности

### Зачем
- Выявление сезонности: курортные маршруты (Сочи, Крым) — лето, вахтовые (Тюмень, Сургут) — круглогодично
- Сезонные маршруты в Директе включаются/выключаются по сезону → экономия бюджета

### Выход
Файл `regions_results.csv`:
```
slug,query,region_1_code,region_1_name,region_1_count,region_1_affinity,...,region_5_code,region_5_name,region_5_count,region_5_affinity
```

Файл `dynamics_results.csv` (только для топ-500):
```
slug,query,month,count
moskva-kazan,"такси Москва Казань",2025-01,11200
moskva-kazan,"такси Москва Казань",2025-02,10800
...
```

---

## Модуль 4: Web Search — SERP-анализ

### Задача
Для каждого маршрута получить топ-10 выдачи Яндекса и оценить силу конкурентов.

### API endpoint (deferred mode — дешевле)
```
POST https://searchapi.api.cloud.yandex.net/v2/web/searchAsync
```

### Заголовки
```
Authorization: Api-Key {YANDEX_CLOUD_API_KEY}
Content-Type: application/json
```

### Тело запроса
```json
{
  "folderId": "{YANDEX_CLOUD_FOLDER_ID}",
  "query": {
    "searchType": "SEARCH_TYPE_RU",
    "queryText": "такси Москва Казань",
    "familyMode": "FAMILY_MODE_NONE",
    "page": 0
  },
  "sortSpec": {
    "sortMode": "SORT_MODE_BY_RELEVANCE",
    "sortOrder": "SORT_ORDER_DESC"
  },
  "groupSpec": {
    "groupMode": "GROUP_MODE_DEEP",
    "groupsOnPage": 10,
    "docsInGroup": 1
  },
  "maxPassages": 2,
  "region": "225",
  "responseFormat": "FORMAT_XML"
}
```

### Как работает deferred mode
1. Отправляешь POST → получаешь `operationId`
2. Через ≥5 минут делаешь GET на `https://operation.api.cloud.yandex.net/operations/{operationId}`
3. Если `done: true` → в `response` лежит результат

### Парсинг XML-ответа
Из каждого результата в выдаче извлекаем:
```python
for group in xml.findall('.//group'):
    domain = group.find('.//domain').text          # домен сайта
    url = group.find('.//url').text                 # полный URL
    title = group.find('.//title').text             # заголовок
    # passages/snippets
```

Также из общих тегов:
```python
total_found = xml.find('.//found[@priority="phrase"]').text  # общее кол-во результатов
```

### Скоринг конкурентности (автоматический)

Для каждого маршрута на основе топ-10 рассчитываем:

```python
# Список известных федеральных конкурентов
FEDERAL_COMPETITORS = [
    'kiwitaxi.ru', 'intui.travel', 'gettransfer.com', 
    'i-way.ru', 'unitiki.com', 'blablacar.ru',
    'kiwi.taxi', 'gobus.online', 'transfer-way.ru'
]

# 1. Количество федеральных агрегаторов в топ-10
federal_count = sum(1 for r in results if r['domain'] in FEDERAL_COMPETITORS)

# 2. Есть ли у конкурентов выделенная страница под маршрут
# (URL содержит оба города или slug маршрута)
dedicated_pages = sum(1 for r in results 
    if city_from_translit in r['url'] and city_to_translit in r['url'])

# 3. Доля "слабых" локальных сайтов (таксисты одного города)
# Эвристика: домен содержит название одного города или "taxi-{город}"
local_count = sum(1 for r in results 
    if r['domain'] not in FEDERAL_COMPETITORS 
    and ('taxi' in r['domain'] or 'transfer' in r['domain']))

# 4. Наличие city2city в топ-10
city2city_position = next(
    (r['position'] for r in results if 'city2city' in r['domain']), 
    None  # None = не в топ-10
)

# 5. Общее количество результатов (из тега <found>)
total_results = int(xml.find('.//found[@priority="phrase"]').text)
```

### Расширение: DR/DA конкурентов (опционально)
Если пользователь предоставит API-ключ от Ahrefs, Moz или подобного сервиса — добавить запрос DR для каждого домена из топ-10. Без этого используем proxy-метрики (federal_count, dedicated_pages).

### Rate limiting
- Deferred requests: до 35 000/час, до 10 rps
- Отправляем батчами по 100 запросов, ждём 5+ минут, забираем результаты
- При 429 — backoff

### Выход
Файл `serp_results.csv`:
```
slug,query,total_results,federal_count,dedicated_pages,local_count,city2city_position,top10_domains_json
moskva-kazan,"такси Москва Казань",1250000,4,6,2,7,"[{""domain"":""kiwitaxi.ru"",""url"":""..."",""position"":1}, ...]"
```

---

## Модуль 5: Скоринг и сегментация

### Входные данные
Объединяем все промежуточные файлы в единую таблицу по slug маршрута.

### Расчёт осей (нормализация в [0, 1])

```python
import numpy as np

# Ось 1: СПРОС (demand_score)
# Суммарная частотность прямого + обратного направления
df['total_frequency'] = df['freq_forward'] + df['freq_reverse']
# Min-max нормализация с логарифмом (частотность имеет степенное распределение)
df['demand_score'] = normalize_log(df['total_frequency'])

# Ось 2: КОНКУРЕНТНАЯ СИЛА ВЫДАЧИ (competition_score)
# Чем выше — тем СИЛЬНЕЕ конкуренты (сложнее пробиться)
df['competition_score'] = normalize(
    0.4 * df['federal_count'] / 10 +          # доля федералов в топ-10
    0.3 * df['dedicated_pages'] / 10 +         # доля выделенных страниц
    0.2 * np.log1p(df['total_results']) / max + # общий объём результатов
    0.1 * (1 - df['local_count'] / 10)         # мало локалов = сильная конкуренция
)

# Ось 3: ТЕКУЩАЯ ПОЗИЦИЯ city2city (position_score)
# Чем выше скор — тем ближе к топу (легче дожать)
df['position_score'] = df['city2city_position'].apply(
    lambda x: 1.0 if x and x <= 3 
    else 0.7 if x and x <= 10 
    else 0.4 if x and x <= 20 
    else 0.1 if x and x <= 50 
    else 0.0  # не в топ-50
)

# Ось 4: СЛАБОСТЬ КОНКУРЕНТОВ (weakness_score) — ИНВЕРСИЯ competition_score
df['weakness_score'] = 1 - df['competition_score']
```

### Сегментация (матрица решений)

```python
def classify_route(row):
    demand = row['demand_score']
    weakness = row['weakness_score']
    position = row['position_score']
    
    # Пороги (настраиваемые)
    HIGH_DEMAND = 0.5    # верхние 50% по спросу
    WEAK_COMP = 0.5      # верхние 50% по слабости конкурентов
    CLOSE_POSITION = 0.4 # уже в топ-20
    
    if demand >= HIGH_DEMAND:
        if weakness >= WEAK_COMP:
            if position >= CLOSE_POSITION:
                return 'SEO_GOLD'       # Высокий спрос + слабые конкуренты + мы близко → быстрая победа SEO
            else:
                return 'SEO_INVEST'     # Высокий спрос + слабые конкуренты + мы далеко → инвестировать в SEO
        else:  # сильные конкуренты
            if position >= CLOSE_POSITION:
                return 'SEO_DEFEND'     # Высокий спрос + сильные конкуренты + мы в топе → защищать позицию
            else:
                return 'DIRECT_ONLY'    # Высокий спрос + сильные конкуренты + мы далеко → только Директ
    elif demand >= 0.2:  # средний спрос
        if weakness >= WEAK_COMP:
            return 'SEO_AUTOPILOT'      # Средний спрос + слабые конкуренты → контентная оптимизация
        else:
            return 'DIRECT_TEST'        # Средний спрос + сильные конкуренты → тестовый бюджет Директа
    else:
        return 'IGNORE'                 # Низкий спрос → не тратить ресурсы

df['segment'] = df.apply(classify_route, axis=1)
```

### Описание сегментов

| Сегмент | Действие | Приоритет |
|---------|----------|-----------|
| `SEO_GOLD` | Внешнее SEO (ссылки, публикации), доработка контента страницы. Самый дешёвый трафик — мы уже близко, конкуренты слабые | 🔴 КРИТИЧЕСКИЙ |
| `SEO_INVEST` | Полный цикл SEO: уникальный контент, внешние ссылки, перелинковка. Параллельно можно запустить Директ для моментального трафика | 🟠 ВЫСОКИЙ |
| `SEO_DEFEND` | Мониторинг позиций, поддержка контента, точечное наращивание ссылок. Не снижать усилия | 🟡 СРЕДНИЙ |
| `DIRECT_ONLY` | Только Яндекс.Директ. SEO-продвижение против сильных конкурентов слишком долго/дорого. Важно: проверить CPC перед запуском | 🟠 ВЫСОКИЙ |
| `SEO_AUTOPILOT` | Достаточно контентной оптимизации (уникализация текста, FAQ). Без внешнего SEO | 🟢 НИЗКИЙ |
| `DIRECT_TEST` | Малый тестовый бюджет в Директе → оценка CPL → решение по факту | 🟡 СРЕДНИЙ |
| `IGNORE` | Страница существует для индексации, но активных усилий не требует | ⚪ НЕТ |

### Дополнительные метрики для отчёта

```python
# Индекс сезонности (из dynamics_results, для топ-500)
# coefficient of variation: std / mean — чем выше, тем сезоннее
df['seasonality_index'] = df['dynamics_std'] / df['dynamics_mean']

# Асимметрия спроса: насколько прямое направление популярнее обратного
df['demand_asymmetry'] = df['freq_forward'] / (df['freq_forward'] + df['freq_reverse'])

# Аномалия спроса (если есть данные о населении)
# Отклонение реального спроса от гравитационной модели
if 'population_from' in df.columns and 'population_to' in df.columns:
    df['gravity_expected'] = (df['population_from'] * df['population_to']) / df['distance_km'] ** 1.5
    df['gravity_expected_norm'] = normalize_log(df['gravity_expected'])
    df['demand_anomaly'] = df['demand_score'] - df['gravity_expected_norm']
    # demand_anomaly > 0.3 → аномально высокий спрос (вахта? медтуризм? паломничество?)
    # demand_anomaly < -0.3 → аномально низкий спрос (люди ищут по-другому?)

# Географическая концентрация спроса (из regions_results)
# Если >50% запросов из одного региона — узкий геотаргетинг в Директе
df['geo_concentration'] = df['region_1_share']  # доля топ-1 региона

# Рекомендация геотаргетинга для Директа
df['direct_geo_target'] = df.apply(
    lambda r: r['region_1_name'] if r['geo_concentration'] > 0.5 else 'Вся Россия', 
    axis=1
)
```

### Выходные файлы

#### 1. `final_scoring.csv` — полная таблица
Все маршруты со всеми метриками и сегментом. Колонки:
```
slug, city_from, city_to, distance_km, priority,
freq_forward, freq_reverse, total_frequency, demand_score,
federal_count, dedicated_pages, local_count, total_results, competition_score, weakness_score,
city2city_position, position_score,
segment, segment_description,
seasonality_index, demand_asymmetry, demand_anomaly,
top_region, geo_concentration, direct_geo_target,
related_queries (топ-5 связанных запросов из Wordstat)
```

#### 2. `segment_summary.csv` — сводка по сегментам
```
segment, count, avg_frequency, avg_competition, example_routes (топ-5 по частотности)
SEO_GOLD, 127, 8500, 0.25, "москва-спб, москва-казань, ..."
DIRECT_ONLY, 89, 12000, 0.78, "москва-сочи, москва-краснодар, ..."
...
```

#### 3. `report.md` — человекочитаемый отчёт
Markdown-файл с:
- Общая статистика: сколько маршрутов в каждом сегменте
- Топ-20 маршрутов для SEO (сегменты SEO_GOLD + SEO_INVEST)
- Топ-20 маршрутов для Директа (сегмент DIRECT_ONLY)
- Маршруты с аномальным спросом (demand_anomaly > 0.3)
- Сезонные маршруты (seasonality_index > 0.5)
- Рекомендации по приоритетам

---

## Технические требования

### Структура проекта
```
city2city-route-scoring/
├── config.py                 # API ключи, константы, пороги
├── main.py                   # Точка входа, оркестрация модулей
├── modules/
│   ├── query_generator.py    # Модуль 1: генерация запросов
│   ├── wordstat_frequency.py # Модуль 2: частотность
│   ├── wordstat_regions.py   # Модуль 3a: регионы
│   ├── wordstat_dynamics.py  # Модуль 3b: динамика
│   ├── serp_analyzer.py      # Модуль 4: SERP-анализ
│   └── scoring.py            # Модуль 5: скоринг и сегментация
├── utils/
│   ├── api_client.py         # HTTP-клиент с rate limiting, retry, logging
│   ├── xml_parser.py         # Парсинг XML-ответов Yandex Search API
│   └── normalizers.py        # Функции нормализации
├── data/
│   ├── input/                # Входные CSV от пользователя
│   └── output/               # Все выходные файлы
├── requirements.txt
└── README.md
```

### Зависимости (Python 3.10+)
```
requests
pandas
numpy
lxml              # для парсинга XML
tqdm              # прогресс-бар
```

### config.py
```python
# API
YANDEX_CLOUD_API_KEY = "..."          # Пользователь подставляет
YANDEX_CLOUD_FOLDER_ID = "..."        # Пользователь подставляет

# Endpoints
WORDSTAT_TOP_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/top"
WORDSTAT_REGIONS_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/regions"
WORDSTAT_DYNAMICS_URL = "https://searchapi.api.cloud.yandex.net/v2/wordstat/dynamics"
SEARCH_ASYNC_URL = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
OPERATIONS_URL = "https://operation.api.cloud.yandex.net/operations/"

# Rate limits
WORDSTAT_RPS = 1                       # запросов в секунду к Wordstat
SEARCH_RPS = 10                        # запросов в секунду к Search (deferred)
BACKOFF_BASE = 2                       # базовая задержка при 429 (секунды)
BACKOFF_MAX = 60                       # максимальная задержка
BATCH_SAVE_EVERY = 100                 # сохранять прогресс каждые N запросов

# Scoring thresholds (пороги для сегментации, настраиваемые)
HIGH_DEMAND_THRESHOLD = 0.5
WEAK_COMPETITION_THRESHOLD = 0.5
CLOSE_POSITION_THRESHOLD = 0.4
MEDIUM_DEMAND_THRESHOLD = 0.2

# Конкуренты
FEDERAL_COMPETITORS = [
    'kiwitaxi.ru', 'intui.travel', 'gettransfer.com',
    'i-way.ru', 'unitiki.com', 'blablacar.ru',
    'kiwi.taxi', 'gobus.online', 'transfer-way.ru',
    'instamotion.ru', 'poputti.com'
]

# Динамика: запрашивать только для топ-N маршрутов по частотности
DYNAMICS_TOP_N = 500
```

### utils/api_client.py — критические требования
```python
"""
HTTP-клиент для Yandex Cloud API.

Требования:
1. Единый метод для всех запросов с автоматическим retry
2. При HTTP 429 — читать заголовок Retry-After или x-deny-reason, 
   делать exponential backoff
3. При HTTP 503 — ждать и повторять
4. Логирование каждого запроса: timestamp, endpoint, status, latency
5. Подсчёт потраченной квоты (total requests sent)
6. Rate limiting: не превышать заданный RPS (time.sleep между запросами)
"""
```

### Обработка ошибок
- Все API-ошибки логируются в `data/output/errors.log`
- При ошибке конкретного маршрута — пропускаем, помечаем как `error` в результатах
- Скрипт не падает при единичных ошибках API
- В конце выводит статистику: сколько успешно, сколько ошибок, сколько пропущено

### Запуск
```bash
# Полный прогон
python main.py --input data/input/routes.csv

# С определённого модуля (resume)
python main.py --input data/input/routes.csv --start-from serp

# Только скоринг (если данные уже собраны)
python main.py --scoring-only

# С кастомными порогами
python main.py --input data/input/routes.csv --high-demand 0.6 --weak-competition 0.4
```

---

## Важные нюансы для реализации

### 1. Транслитерация городов
Для проверки "выделенных страниц" в SERP нужна транслитерация названий городов:
```python
# Москва → moskva, Ростов-на-Дону → rostov-na-donu
# Использовать transliterate или собственную таблицу
```

### 2. Deferred requests — workflow
```python
# 1. Отправить батч запросов (до 100)
operation_ids = []
for query in batch:
    resp = api.post(SEARCH_ASYNC_URL, body)
    operation_ids.append(resp['id'])

# 2. Подождать минимум 5 минут
time.sleep(300)

# 3. Забрать результаты
for op_id in operation_ids:
    result = api.get(f"{OPERATIONS_URL}{op_id}")
    if result['done']:
        parse_and_save(result['response'])
    else:
        # Подождать ещё и повторить
        retry_queue.append(op_id)
```

### 3. Wordstat может не знать фразу
Если Wordstat возвращает 0 или ошибку для фразы — это нормально. Маршрут получает frequency=0 и попадает в сегмент IGNORE.

### 4. XML-парсинг SERP
Ответ Web Search API в XML-формате. Основные теги:
```xml
<yandexsearch>
  <response>
    <found priority="phrase">1234567</found>
    <results>
      <grouping>
        <group>
          <doc>
            <url>https://kiwitaxi.ru/...</url>
            <domain>kiwitaxi.ru</domain>
            <title>Такси Москва Казань</title>
            <passages>
              <passage>Закажите трансфер...</passage>
            </passages>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>
```

### 5. Масштаб и время выполнения
- ~4 000 маршрутов × 1 запрос Wordstat/сек = ~67 минут на Wordstat
- ~4 000 deferred search requests = отправка за 7 минут, ожидание 5-10 минут, сбор за 7 минут
- Регионы: ещё ~67 минут
- Итого: ~2.5-3 часа на полный прогон
- С resume capability — можно разбить на несколько сессий

### 6. Стоимость
- Wordstat: бесплатно (Preview)
- Web Search deferred: ~4 000 запросов × $0.25/1000 = $1
- Итого: ~$1 (~100₽) за полный анализ 4 000 маршрутов
