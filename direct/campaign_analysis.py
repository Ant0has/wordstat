import csv
import re
import math
from collections import defaultdict

BASE = r'C:\Users\furse\Downloads\wordstatapi'

# Federal districts mapping
FEDERAL_DISTRICTS = {
    'ЦФО': ['Москва','Московская область','Тула','Тульская','Калуга','Калужская','Рязань','Рязанская','Владимир','Владимирская','Иваново','Ивановская','Ярославль','Ярославская','Кострома','Костромская','Тверь','Тверская','Смоленск','Смоленская','Брянск','Брянская','Орёл','Орёл','Орловская','Курск','Курская','Белгород','Белгородская','Липецк','Липецкая','Воронеж','Воронежская','Тамбов','Тамбовская'],
    'СЗФО': ['Санкт-Петербург','Ленинградская','Мурманск','Мурманская','Архангельск','Архангельская','Вологда','Вологодская','Калининград','Калининградская','Псков','Псковская','Новгород','Новгородская','Сыктывкар','Коми','Петрозаводск','Карелия'],
    'ЮФО': ['Ростов','Ростовская','Краснодар','Краснодарский','Волгоград','Волгоградская','Астрахань','Астраханская','Севастополь','Крым','Симферополь','Элиста','Калмыкия','Адыгея','Майкоп'],
    'СКФО': ['Ставрополь','Ставропольский','Махачкала','Дагестан','Грозный','Чечня','Нальчик','Кабардино','Владикавказ','Осетия','Черкесск','Карачаево','Магас','Ингушетия'],
    'ПФО': ['Казань','Татарстан','Нижний Новгород','Нижегородская','Самара','Самарская','Уфа','Башкортостан','Пермь','Пермский','Саратов','Саратовская','Оренбург','Оренбургская','Ижевск','Удмуртия','Ульяновск','Ульяновская','Пенза','Пензенская','Киров','Кировская','Чебоксары','Чувашия','Йошкар-Ола','Марий Эл','Саранск','Мордовия'],
    'УФО': ['Екатеринбург','Свердловская','Челябинск','Челябинская','Тюмень','Тюменская','Курган','Курганская','ХМАО','ЯНАО','Сургут','Нижневартовск'],
    'СФО': ['Новосибирск','Новосибирская','Красноярск','Красноярский','Омск','Омская','Барнаул','Алтайский','Кемерово','Кемеровская','Иркутск','Иркутская','Томск','Томская','Горно-Алтайск','Алтай','Абакан','Хакасия','Тыва','Кызыл'],
    'ДФО': ['Владивосток','Приморский','Хабаровск','Хабаровский','Благовещенск','Амурская','Южно-Сахалинск','Сахалинская','Якутск','Саха','Петропавловск','Камчатка','Магадан','Магаданская','Чита','Забайкальский','Улан-Удэ','Бурятия','Биробиджан','ЕАО'],
    'ДОНЕЦК': ['Донецк','ДНР','ЛНР','Луганск','Запорожье','Херсон'],
}

def detect_district(city):
    city_lower = city.lower()
    for district, keywords in FEDERAL_DISTRICTS.items():
        for kw in keywords:
            if kw.lower() in city_lower:
                return district
    return 'Другое'

# Load Direct routes
routes = []
with open(f'{BASE}/direct_all_clean.csv', encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter=';'):
        dist_val = r['distance'].strip()
        routes.append({
            'url': r['url'],
            'city1': r['gorod1'],
            'city2': r['gorod2'],
            'distance': int(dist_val) if dist_val else 0,
            'price': int(r['price']),
            'freq': int(r['freq']),
            'segment': r['segment'],
            'source': r['source'],
            'district': detect_district(r['gorod1']),
        })

print(f'Total routes: {len(routes)}')

# 1. By Federal District
print('\n=== BY FEDERAL DISTRICT ===')
by_dist = defaultdict(lambda: {'n':0,'freq':0,'prices':[]})
for r in routes:
    d = by_dist[r['district']]
    d['n'] += 1
    d['freq'] += r['freq']
    d['prices'].append(r['price'])

for district in sorted(by_dist, key=lambda x: by_dist[x]['freq'], reverse=True):
    d = by_dist[district]
    avg_p = sum(d['prices']) // len(d['prices'])
    print(f'  {district}: {d["n"]} routes, freq={d["freq"]:,}, avg_price={avg_p:,}')

# 2. By distance range
print('\n=== BY DISTANCE RANGE ===')
dist_ranges = [(0,100,'short'),(100,300,'medium'),(300,700,'long'),(700,1500,'very_long'),(1500,2200,'ultra')]
for lo, hi, label in dist_ranges:
    grp = [r for r in routes if lo <= r['distance'] < hi]
    if grp:
        total_freq = sum(r['freq'] for r in grp)
        avg_price = sum(r['price'] for r in grp) // len(grp)
        print(f'  {lo}-{hi}km ({label}): {len(grp)} routes, freq={total_freq:,}, avg_price={avg_price:,}')

# 3. By segment
print('\n=== BY SEGMENT ===')
by_seg = defaultdict(lambda: {'n':0,'freq':0})
for r in routes:
    by_seg[r['segment']]['n'] += 1
    by_seg[r['segment']]['freq'] += r['freq']

for s in sorted(by_seg, key=lambda x: by_seg[x]['freq'], reverse=True):
    print(f'  {s}: {by_seg[s]["n"]} routes, freq={by_seg[s]["freq"]:,}')

# 4. Low impressions risk analysis
print('\n=== LOW IMPRESSIONS RISK ===')
freq_buckets = [(0,5),(5,10),(10,50),(50,200),(200,99999)]
for lo, hi in freq_buckets:
    grp = [r for r in routes if lo <= r['freq'] < hi]
    if grp:
        pct = len(grp) / len(routes) * 100
        print(f'  freq {lo}-{hi}: {len(grp)} routes ({pct:.1f}%)')

# 5. Recommended campaign structure
print('\n=== RECOMMENDED CAMPAIGN STRUCTURE ===')

campaigns = defaultdict(list)
for r in routes:
    dist_bucket = 'short' if r['distance'] < 200 else 'medium' if r['distance'] < 500 else 'long'
    key = f"{r['district']}_{dist_bucket}"
    campaigns[key].append(r)

print(f'Potential campaign groups: {len(campaigns)}')
for key in sorted(campaigns, key=lambda x: sum(r["freq"] for r in campaigns[x]), reverse=True)[:20]:
    grp = campaigns[key]
    total_freq = sum(r['freq'] for r in grp)
    print(f'  {key}: {len(grp)} routes, freq={total_freq:,}')

# 6. Keywords per route analysis
total_keywords = len(routes) * 3
low_risk = sum(1 for r in routes if r['freq'] < 10)
print(f'\n=== KEYWORD ANALYSIS ===')
print(f'Total keywords (3 per route): {total_keywords}')
print(f'Routes with freq < 10 (risk "мало показов"): {low_risk} ({low_risk/len(routes)*100:.1f}%)')
print(f'Routes with freq >= 10 (safe): {len(routes)-low_risk}')
