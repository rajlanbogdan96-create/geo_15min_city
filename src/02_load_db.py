from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_DATA_PATH = BASE_DIR / "data" / "osm_infrastructure.csv"

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 55432,
    "dbname": "city_gis",
    "user": "postgres",
    "password": "postgres"
}

DISTRICT_ERAS = {
    "Измайлово": "1950–1970-е (оценка)",
    "Проспект Вернадского": "1960–1980-е (оценка)",
    "Таганский": "1910–1970-е (оценка)",
    "Алексеевский": "1950–1980-е (оценка)",
    "Люблино": "1970–1990-е (оценка)"
}

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;
DROP TABLE IF EXISTS infrastructure;
CREATE TABLE infrastructure (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL,
    district VARCHAR(100) NOT NULL,
    year_built VARCHAR(60) NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326)
);
CREATE INDEX idx_infrastructure_geom ON infrastructure USING GIST (geom);
CREATE INDEX idx_infrastructure_district_cat ON infrastructure (district, category);
"""


def main():
    if not CSV_DATA_PATH.exists():
        print(f"[Ошибка] Файл {CSV_DATA_PATH} не найден. Сначала выполните: python src/01_extract_osm.py")
        return

    df = pd.read_csv(CSV_DATA_PATH)
    if "year_built" not in df.columns:
        df["year_built"] = df["district"].map(DISTRICT_ERAS).fillna("н/д")

    records = df[
        ["osm_id", "name", "category", "district", "year_built", "lat", "lon"]
    ].values.tolist()

    formatted_records = [
        (
            int(r[0]),
            str(r[1])[:250],
            str(r[2]),
            str(r[3]),
            str(r[4])[:55],
            float(r[5]),
            float(r[6]),
            float(r[6]),
            float(r[5])
        )
        for r in records
    ]

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            execute_values(
                cur,
                """
                INSERT INTO infrastructure (osm_id, name, category, district, year_built, lat, lon, geom)
                VALUES %s
                """,
                formatted_records,
                template="(%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))"
            )
            cur.execute("SELECT COUNT(*) FROM infrastructure;")
            total = cur.fetchone()[0]
        conn.commit()
        print(f"[Успех] База готова. В PostGIS загружено {total} объектов.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()