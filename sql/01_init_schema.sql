-- Активация пространственного расширения PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Пересоздание таблицы объектов городской инфраструктуры
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

-- Пространственный индекс GiST (R-Tree) для быстрого поиска объектов в радиусе
CREATE INDEX idx_infrastructure_geom ON infrastructure USING GIST (geom);

-- Композитный индекс для фильтрации по районам и категориям
CREATE INDEX idx_infrastructure_district_cat ON infrastructure (district, category);
