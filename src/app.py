import math
from pathlib import Path
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

try:
    import psycopg2
except ImportError:
    psycopg2 = None

st.set_page_config(page_title="ГИС анализа городской инфраструктуры", layout="wide")

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_DATA_PATH = BASE_DIR / "data" / "osm_infrastructure.csv"

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 55432,
    "dbname": "city_gis",
    "user": "postgres",
    "password": "postgres",
    "connect_timeout": 2
}

DISTRICTS = {
    "Измайлово": (55.7897, 37.7885),
    "Проспект Вернадского": (55.6705, 37.4950),
    "Таганский": (55.7410, 37.6650),
    "Алексеевский": (55.8150, 37.6530),
    "Люблино": (55.6766, 37.7618)
}

DISTRICT_ERAS = {
    "Измайлово": "1950–1970-е (оценка)",
    "Проспект Вернадского": "1960–1980-е (оценка)",
    "Таганский": "1910–1970-е (оценка)",
    "Алексеевский": "1950–1980-е (оценка)",
    "Люблино": "1970–1990-е (оценка)"
}

CATEGORY_STYLES = {
    "Магазины": {"color": "blue", "icon": "shopping-cart"},
    "Аптеки": {"color": "green", "icon": "plus-sign"},
    "Больницы": {"color": "red", "icon": "heart"},
    "Спортзалы": {"color": "orange", "icon": "fire"}
}


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@st.cache_data
def load_csv_fallback():
    if not CSV_DATA_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(CSV_DATA_PATH)
    if "year_built" not in df.columns:
        df["year_built"] = df["district"].map(DISTRICT_ERAS).fillna("н/д")
    return df


def get_nearby_objects(lat, lon, radius, categories):
    if not categories:
        return pd.DataFrame()

    # 1. Попытка запроса к локальной БД PostGIS
    if psycopg2 is not None:
        query = """
            SELECT name, category, district, year_built, lat, lon,
                   ROUND(ST_Distance(
                       geom::geography,
                       ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                   )::numeric, 0) AS distance_m
            FROM infrastructure
            WHERE category = ANY(%s)
              AND ST_DWithin(
                  geom::geography,
                  ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                  %s
              )
            ORDER BY distance_m ASC;
        """
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute(query, (lon, lat, categories, lon, lat, radius))
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
            conn.close()
            df = pd.DataFrame(rows, columns=cols)
            if not df.empty:
                df["distance_m"] = df["distance_m"].astype(float)
                df["walk_min"] = df["distance_m"].apply(lambda d: max(1, math.ceil((d * 1.25) / 80.0)))
            return df
        except Exception:
            pass

    # 2. Резервный облачный режим (чтение из data/osm_infrastructure.csv)
    df_all = load_csv_fallback()
    if df_all.empty:
        st.error("Файл data/osm_infrastructure.csv не найден в репозитории.")
        return pd.DataFrame()

    df = df_all[df_all["category"].isin(categories)].copy()
    df["distance_m"] = df.apply(lambda r: round(haversine_m(lat, lon, float(r["lat"]), float(r["lon"]))), axis=1)
    df = df[df["distance_m"] <= radius].sort_values("distance_m").reset_index(drop=True)
    if not df.empty:
        df["walk_min"] = df["distance_m"].apply(lambda d: max(1, math.ceil((float(d) * 1.25) / 80.0)))
    return df


st.sidebar.header("Параметры анализа")
selected_district = st.sidebar.selectbox("Выберите район Москвы:", options=list(DISTRICTS.keys()))
selected_categories = st.sidebar.multiselect(
    "Типы объектов:",
    options=["Магазины", "Аптеки", "Больницы", "Спортзалы"],
    default=["Магазины", "Аптеки", "Больницы", "Спортзалы"]
)
walk_radius = st.sidebar.slider("Радиус пешей доступности (м):", 200, 1500, 800, 100)

if "current_district" not in st.session_state or st.session_state.current_district != selected_district:
    st.session_state.current_district = selected_district
    st.session_state.center_lat, st.session_state.center_lon = DISTRICTS[selected_district]

st.title("Геоинформационная система анализа городской инфраструктуры")
st.markdown(f"**Район:** {selected_district} | Кликните по любой точке на карте, чтобы обновить список справа.")

df_objects = get_nearby_objects(
    st.session_state.center_lat,
    st.session_state.center_lon,
    walk_radius,
    selected_categories
)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Всего в зоне", len(df_objects))
m2.metric("Магазины", len(df_objects[df_objects["category"] == "Магазины"]) if not df_objects.empty else 0)
m3.metric("Аптеки", len(df_objects[df_objects["category"] == "Аптеки"]) if not df_objects.empty else 0)
m4.metric("Больницы", len(df_objects[df_objects["category"] == "Больницы"]) if not df_objects.empty else 0)
m5.metric("Спортзалы", len(df_objects[df_objects["category"] == "Спортзалы"]) if not df_objects.empty else 0)

col_map, col_list = st.columns([1.3, 1.2])

with col_map:
    m = folium.Map(
        location=[st.session_state.center_lat, st.session_state.center_lon],
        zoom_start=14
    )

    folium.Circle(
        location=[st.session_state.center_lat, st.session_state.center_lon],
        radius=walk_radius,
        color="#1f77b4",
        weight=2,
        fill=True,
        fill_opacity=0.15
    ).add_to(m)

    folium.Marker(
        location=[st.session_state.center_lat, st.session_state.center_lon],
        popup="Выбранная точка",
        icon=folium.Icon(color="black", icon="home")
    ).add_to(m)

    if not df_objects.empty:
        for idx, row in df_objects.iterrows():
            style = CATEGORY_STYLES.get(row["category"], {"color": "gray", "icon": "info-sign"})
            num = idx + 1
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=(
                    f"<b>№{num}. {row['name']}</b><br>"
                    f"Тип: {row['category']}<br>"
                    f"Год возведения: {row['year_built']}<br>"
                    f"Пешком: ~{int(row['walk_min'])} мин ({int(row['distance_m'])} м)"
                ),
                tooltip=f"№{num} {row['name']} (~{int(row['walk_min'])} мин)",
                icon=folium.Icon(color=style["color"], icon=style["icon"])
            ).add_to(m)

    map_data = st_folium(m, width=700, height=560, returned_objects=["last_clicked"])

    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]
        if (clicked_lat, clicked_lon) != (st.session_state.center_lat, st.session_state.center_lon):
            st.session_state.center_lat = clicked_lat
            st.session_state.center_lon = clicked_lon
            st.rerun()

with col_list:
    st.subheader(f"Объекты в пешей доступности ({len(df_objects)})")
    if not df_objects.empty:
        view_df = pd.DataFrame({
            "№": range(1, len(df_objects) + 1),
            "Тип объекта": df_objects["category"],
            "Название": df_objects["name"],
            "Год возведения": df_objects["year_built"],
            "Идти пешком": df_objects.apply(
                lambda r: f"~{int(r['walk_min'])} мин ({int(r['distance_m'])} м)",
                axis=1
            )
        })
        st.dataframe(view_df, use_container_width=True, hide_index=True, height=520)
    else:
        st.info("В этом радиусе объектов нет. Кликните в другую точку или увеличьте радиус слева.")
