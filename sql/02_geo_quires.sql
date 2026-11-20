-- 1. Поиск объектов в пешей доступности (радиус 800 м от центра района Измайлово)
-- с расчётом дистанции и примерного времени пути пешком (скорость 80 м/мин, коэф. маршрута 1.25)
SELECT
    ROW_NUMBER() OVER (ORDER BY ST_Distance(
        geom::geography,
        ST_SetSRID(ST_MakePoint(37.7885, 55.7897), 4326)::geography
    )) AS "№",
    category AS "Тип объекта",
    name AS "Название",
    year_built AS "Примерный год возведения",
    ROUND(ST_Distance(
        geom::geography,
        ST_SetSRID(ST_MakePoint(37.7885, 55.7897), 4326)::geography
    )::numeric, 0) AS "Расстояние (м)",
    GREATEST(1, CEIL((ST_Distance(
        geom::geography,
        ST_SetSRID(ST_MakePoint(37.7885, 55.7897), 4326)::geography
    ) * 1.25) / 80.0)) AS "Идти пешком (мин)"
FROM infrastructure
WHERE ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_MakePoint(37.7885, 55.7897), 4326)::geography,
    800
)
ORDER BY "Расстояние (м)" ASC;

-- 2. Сводная обеспеченность пяти исследуемых районов по категориям инфраструктуры
SELECT
    district AS "Район",
    category AS "Категория",
    COUNT(*) AS "Количество объектов"
FROM infrastructure
GROUP BY district, category
ORDER BY district, COUNT(*) DESC;

-- 3. Поиск ближайшего объекта каждой категории от заданной точки проживания
SELECT DISTINCT ON (category)
    category AS "Тип объекта",
    name AS "Ближайший объект",
    year_built AS "Год возведения",
    ROUND(ST_Distance(
        geom::geography,
        ST_SetSRID(ST_MakePoint(37.7885, 55.7897), 4326)::geography
    )::numeric, 0) AS "Расстояние (м)"
FROM infrastructure
ORDER BY category, geom::geography <-> ST_SetSRID(ST_MakePoint(37.7885, 55.7897), 4326)::geography;