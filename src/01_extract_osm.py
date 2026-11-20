import time
from pathlib import Path
import requests
import pandas as pd

# Автоматическое определение пути к папке data
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_CSV = DATA_DIR / "osm_infrastructure.csv"

# Центры пяти целевых районов Москвы
DISTRICTS = {
    "Измайлово": (55.7897, 37.7885),
    "Проспект Вернадского": (55.6705, 37.4950),
    "Таганский": (55.7410, 37.6650),
    "Алексеевский": (55.8150, 37.6530),
    "Люблино": (55.6766, 37.7618)
}

# Ориентировочные периоды массовой застройки районов (если в OSM не заполнен тег года)
DISTRICT_ERAS = {
    "Измайлово": "1950–1970-е (оценка)",
    "Проспект Вернадского": "1960–1980-е (оценка)",
    "Таганский": "1910–1970-е (оценка)",
    "Алексеевский": "1950–1980-е (оценка)",
    "Люблино": "1970–1990-е (оценка)"
}

RADIUS = 2500

# Зеркала Overpass API для обхода таймаутов и ограничений
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]


def build_query(lat, lon, radius):
    return f"""
    [out:json][timeout:60];
    (
      node["shop"~"supermarket|convenience"](around:{radius},{lat},{lon});
      way["shop"~"supermarket|convenience"](around:{radius},{lat},{lon});
      node["amenity"="pharmacy"](around:{radius},{lat},{lon});
      way["amenity"="pharmacy"](around:{radius},{lat},{lon});
      node["amenity"~"hospital|clinic"](around:{radius},{lat},{lon});
      way["amenity"~"hospital|clinic"](around:{radius},{lat},{lon});
      node["leisure"~"fitness_centre|sports_centre"](around:{radius},{lat},{lon});
      way["leisure"~"fitness_centre|sports_centre"](around:{radius},{lat},{lon});
    );
    out center;
    """


def detect_category(tags):
    if tags.get("amenity") == "pharmacy":
        return "Аптеки"
    if tags.get("amenity") in ["hospital", "clinic"]:
        return "Больницы"
    if tags.get("leisure") in ["fitness_centre", "sports_centre"]:
        return "Спортзалы"
    if tags.get("shop") in ["supermarket", "convenience"]:
        return "Магазины"
    return "Прочее"


def extract_year(tags, district):
    raw_year = (
        tags.get("start_date")
        or tags.get("building:year_built")
        or tags.get("year_built")
    )
    if raw_year:
        return str(raw_year)[:25]
    return DISTRICT_ERAS.get(district, "н/д")


def fetch_district_data(district_name, lat, lon):
    query = build_query(lat, lon, RADIUS)
    headers = {"User-Agent": "MIREA_GIS_System_Analysis/1.0"}

    for url in OVERPASS_URLS:
        try:
            print(f"[ETL] Выгрузка района '{district_name}' через {url}...")
            response = requests.post(
                url,
                data={"data": query},
                headers=headers,
                timeout=60
            )
            if response.status_code == 200:
                return response.json().get("elements", [])
            print(f"[Предупреждение] Код ответа {response.status_code} от {url}")
        except Exception as e:
            print(f"[Предупреждение] Ошибка зеркала {url}: {e}. Переключение...")
            time.sleep(2)
    return []


def main():
    all_records = []

    default_names = {
        "Магазины": "Продуктовый магазин",
        "Аптеки": "Аптечный пункт",
        "Больницы": "Медицинское учреждение",
        "Спортзалы": "Спортивный клуб"
    }

    for district, (lat, lon) in DISTRICTS.items():
        elements = fetch_district_data(district, lat, lon)

        for el in elements:
            tags = el.get("tags", {})
            category = detect_category(tags)
            if category == "Прочее":
                continue

            obj_lat = el.get("lat") or el.get("center", {}).get("lat")
            obj_lon = el.get("lon") or el.get("center", {}).get("lon")

            if not obj_lat or not obj_lon:
                continue

            name = tags.get("name", default_names.get(category, "Объект инфраструктуры"))

            all_records.append({
                "osm_id": el.get("id"),
                "name": name,
                "category": category,
                "district": district,
                "year_built": extract_year(tags, district),
                "lat": obj_lat,
                "lon": obj_lon
            })

        time.sleep(2)

    df = pd.DataFrame(all_records)
    if not df.empty:
        df.drop_duplicates(subset=["osm_id", "district"], inplace=True)
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
        print(f"[Успех] Сохранено {len(df)} объектов в файл: {OUTPUT_CSV}")
    else:
        print("[Ошибка] Не удалось получить данные ни с одного сервера. Проверьте интернет.")


if __name__ == "__main__":
    main()