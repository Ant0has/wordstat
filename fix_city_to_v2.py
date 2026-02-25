"""Fix all 208 routes with empty city_to by extracting from slug + DB + manual mapping."""
import csv, re

BASE = r"C:\Users\furse\Downloads\wordstatapi"

# ===== STEP 1: Build slug->city from DB =====
slug_to_city = {}
with open(f"{BASE}/all_routes_db.tsv", "r", encoding="utf-8-sig") as f:
    for line in f:
        parts = line.strip().split("\t")
        if len(parts) >= 2:
            slug = parts[0]
            halves = parts[1].split("Россия,")
            if len(halves) >= 2:
                ct = halves[1].strip().split(",")[0].strip()
                cf = halves[0].strip().split(",")[0].strip()
                if ct and cf:
                    cf_slug = slug.split("-")[0]
                    rest = slug[len(cf_slug)+1:] if len(cf_slug)+1 < len(slug) else ""
                    if rest:
                        clean = re.sub(r"-\d+$", "", rest)
                        if clean and clean not in slug_to_city:
                            slug_to_city[clean] = ct

print(f"DB slug mappings: {len(slug_to_city)}")

# ===== STEP 2: Manual mappings =====
manual = {
    "beloreck": "Белорецк", "tagil": "Нижний Тагил", "nab_chelny": "Набережные Челны",
    "nizhniy_novgorod": "Нижний Новгород", "yoskar_ola": "Йошкар-Ола",
    "rostov-na-don": "Ростов-на-Дону", "neftekams": "Нефтекамск", "oktjabrskij": "Октябрьский",
    "borovichi": "Боровичи", "lipetsk": "Липецк", "piter": "Санкт-Петербург",
    "ryazan": "Рязань", "tula": "Тула", "tver": "Тверь", "vladimir": "Владимир",
    "voronezh": "Воронеж", "yaroslavl": "Ярославль",
    # svo-taxi routes
    "svo-taxi-donetsk-gorlovka": "Горловка", "svo-taxi-donetsk-lugansk": "Луганск",
    "svo-taxi-donetsk-mineralnye-vody-aeroport": "Минеральные Воды",
    "svo-taxi-donetsk-novopetrovka": "Новопетровка", "svo-taxi-donetsk-starobeshevo": "Старобешево",
    "svo-taxi-donetsk-yurevka": "Юрьевка",
    "svo-taxi-moskva-gorlovka": "Горловка", "svo-taxi-moskva-mariupol": "Мариуполь",
    "svo-taxi-krasnodar-donetsk": "Донецк", "svo-taxi-krasnodar-lugansk": "Луганск",
    "svo-taxi-krasnodar-mariupol": "Мариуполь", "svo-taxi-krasnodar-melitopol": "Мелитополь",
    "svo-taxi-ivanovo-lugansk": "Луганск", "svo-taxi-sochi-aeroport-donetsk": "Донецк",
    "svo-taxi-sankt-peterburg-stahanov": "Стаханов",
    "svo-taxi-millerovo-donetsk": "Донецк", "svo-taxi-millerovo-lugansk": "Луганск",
    "svo-taxi-mineralnye-vody-aeroport-donetsk": "Донецк",
    "svo-taxi-snezhnoe-moskva": "Москва", "svo-taxi-snezhnoe-rostov-na-donu": "Ростов-на-Дону",
    "svo-taxi-gorlovka-moskva": "Москва", "svo-taxi-gorlovka-rostov-na-donu": "Ростов-на-Дону",
    "svo-taxi-stahanov-krasnyy-luch": "Красный Луч", "svo-taxi-stahanov-lugansk": "Луганск",
    "svo-taxi-stahanov-rostov-na-donu": "Ростов-на-Дону",
    "svo-taxi-krasnyy-luch-antratsit": "Антрацит", "svo-taxi-krasnyy-luch-lugansk": "Луганск",
    "svo-taxi-krasnyy-luch-mariupol": "Мариуполь", "svo-taxi-krasnyy-luch-rostov-na-donu": "Ростов-на-Дону",
    "svo-taxi-kremennaya-lugansk": "Луганск", "svo-taxi-rubezhnoe-lugansk": "Луганск",
    "svo-taxi-severodonetsk-lugansk": "Луганск", "svo-taxi-starobelsk-lugansk": "Луганск",
    "svo-taxi-lutugino-lugansk": "Луганск", "svo-taxi-izvarino-lugansk": "Луганск",
    "svo-taxi-rovenki-lugansk": "Луганск", "svo-taxi-rovenki-rossosh": "Россошь",
    "svo-taxi-shebekino-belgorod": "Белгород",
    "svo-taxi-boguchar-bryansk": "Брянск", "svo-taxi-boguchar-rossosh": "Россошь",
    "svo-taxi-boguchar-saratov": "Саратов",
    "svo-taxi-lugansk-alchevsk": "Алчевск", "svo-taxi-lugansk-antratsit": "Антрацит",
    "svo-taxi-lugansk-izvarino": "Изварино", "svo-taxi-lugansk-krasnyy-luch": "Красный Луч",
    "svo-taxi-lugansk-lutugino": "Лутугино", "svo-taxi-lugansk-rovenki": "Ровеньки",
    "svo-taxi-lugansk-severodonetsk": "Северодонецк", "svo-taxi-lugansk-stahanov": "Стаханов",
    "svo-taxi-lugansk-starobelsk": "Старобельск",
    "svo-taxi-rossosh-belgorod": "Белгород", "svo-taxi-rossosh-bryansk": "Брянск",
    "svo-taxi-rossosh-kursk": "Курск", "svo-taxi-rossosh-nizhniy-novgorod": "Нижний Новгород",
    "svo-taxi-rossosh-rovenki": "Ровеньки", "svo-taxi-rossosh-severodonetsk": "Северодонецк",
    "svo-taxi-rossosh-smolensk": "Смоленск", "svo-taxi-rossosh-starobelsk": "Старобельск",
    "svo-taxi-rossosh-voronezh": "Воронеж",
    "svo-taxi-rostov-na-donu-antratsit": "Антрацит", "svo-taxi-rostov-na-donu-energodar": "Энергодар",
    "svo-taxi-rostov-na-donu-gorlovka": "Горловка", "svo-taxi-rostov-na-donu-kazachi-lageri": "Казачьи Лагери",
    "svo-taxi-rostov-na-donu-melitopol": "Мелитополь", "svo-taxi-rostov-na-donu-novosibirsk": "Новосибирск",
    "svo-taxi-rostov-na-donu-severodonetsk": "Северодонецк", "svo-taxi-rostov-na-donu-snezhnoe": "Снежное",
    "svo-taxi-rostov-na-donu-stahanov": "Стаханов", "svo-taxi-rostov-na-donu-starobeshevo": "Старобешево",
    "svo-taxi-rostov-na-donu-tokmak": "Токмак",
    "svo-taxi-kpp-valuyki-rossosh": "Россошь", "svo-taxi-kpp-uspenka-donetsk": "Донецк",
    "svo-taxi-mariupol-kpp-vesyolo-voznesenka": "Весёло-Вознесенка",
    "svo-taxi-mariupol-yurevka": "Юрьевка",
    "svo-taxi-melitopol-dneprorudnoe": "Днепрорудное", "svo-taxi-melitopol-energodar": "Энергодар",
    "svo-taxi-kamenka-nizhniy-novgorod": "Нижний Новгород", "svo-taxi-kamenka-novosibirsk": "Новосибирск",
    "svo-taxi-kamenka-smolensk": "Смоленск",
    "svo-taxi-novopetrovka-donetsk": "Донецк", "svo-taxi-yurevka-donetsk": "Донецк",
    "svo-taxi-alchevsk-lugansk": "Луганск", "svo-taxi-bryanka-lugansk": "Луганск",
    "svo-taxi-starobelsk-2": "Старобельск",
    "svo-taxi-svatovo-lugansk": "Луганск",
    "svo-taxi-tokmak-melitopol": "Мелитополь",
    # Самара двойные prefix
    "samara-buguruslan": "Бугуруслан", "samara-cheboksary": "Чебоксары",
    # Прочие
    "valuyki-belgorod": "Белгород", "valuyki-voronezh": "Воронеж",
    "svatovo-belgorod": "Белгород", "svatovo-kazan": "Казань",
    "tokmak-rostov-na-don": "Ростов-на-Дону", "tokmak-samara": "Самара", "tokmak-simferopol": "Симферополь",
    "urazovo-belgorod": "Белгород",
    "rostov-astrahan": "Астрахань", "rostov-eisk": "Ейск",
    "tumen-chelyabinsk": "Челябинск", "tumen-hanty-mansiysk": "Ханты-Мансийск",
    "tumen-ekaterinburg": "Екатеринбург",
}
slug_to_city.update(manual)

# ===== STEP 3: Load and fix =====
orig_rows = []
with open(f"{BASE}/routes_city2city.csv", "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    for row in reader:
        orig_rows.append(row)

cf_prefixes = sorted([
    "cheljabinsk","donetsk","ekaterinburg","energodar","enisejsk","kazan",
    "moskva","rostov-na-donu","ufa","lugansk","mariupol","melitopol",
    "samara",
], key=len, reverse=True)

fixed = 0
still = []
for r in orig_rows:
    if not r["city_to"].strip():
        slug = r["page_url"].replace("https://city2city.ru/", "").strip("/")
        found = False

        # Try full slug in manual first
        if slug in manual:
            r["city_to"] = manual[slug]
            fixed += 1
            continue

        # Try prefix match
        for prefix in cf_prefixes:
            if slug.startswith(prefix + "-"):
                dest = slug[len(prefix)+1:]
                dest_clean = re.sub(r"-\d+$", "", dest)
                if dest in slug_to_city:
                    r["city_to"] = slug_to_city[dest]
                    fixed += 1
                    found = True
                    break
                elif dest_clean in slug_to_city:
                    r["city_to"] = slug_to_city[dest_clean]
                    fixed += 1
                    found = True
                    break
                elif dest in manual:
                    r["city_to"] = manual[dest]
                    fixed += 1
                    found = True
                    break

        if not found:
            still.append((slug, r["city_from"]))

print(f"Fixed: {fixed} / 208")
print(f"Still empty: {len(still)}")
for s, cf in still:
    print(f"  {cf:30s} [{s}]")

# ===== STEP 4: Write =====
outpath = f"{BASE}/routes_city2city_fixed2.csv"
with open(outpath, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(orig_rows)

filled = sum(1 for r in orig_rows if r["city_to"].strip())
print(f"\nWrote: {outpath}")
print(f"Total: {len(orig_rows)}, with city_to: {filled}, empty: {len(orig_rows)-filled}")
