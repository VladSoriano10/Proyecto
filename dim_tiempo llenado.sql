-- CARGA INICIAL: DIMENSIÓN TIEMPO (2020 a 2030)

INSERT INTO dim_tiempo (
    sk_fecha, 
    fecha, 
    anio, 
    mes, 
    dia, 
    nombre_mes, 
    dia_semana, 
    trimestre, 
    anio_mes, 
    es_fin_semana, 
    es_fin_mes
)
SELECT 
    -- Llave (YYYYMMDD)
    CAST(TO_CHAR(fecha_generada, 'YYYYMMDD') AS INT) AS sk_fecha,
    
    --Fecha natural
    fecha_generada::DATE AS fecha,
    
    --Año, Mes, Día
    EXTRACT(YEAR FROM fecha_generada)::INT AS anio,
    EXTRACT(MONTH FROM fecha_generada)::INT AS mes,
    EXTRACT(DAY FROM fecha_generada)::INT AS dia,
    
    --Nombre del Mes
    CASE EXTRACT(MONTH FROM fecha_generada)
        WHEN 1 THEN 'Enero' WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo'
        WHEN 4 THEN 'Abril' WHEN 5 THEN 'Mayo' WHEN 6 THEN 'Junio'
        WHEN 7 THEN 'Julio' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Septiembre'
        WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' WHEN 12 THEN 'Diciembre'
    END AS nombre_mes,
    
    --Nombre del Día de la semana
    CASE EXTRACT(ISODOW FROM fecha_generada)
        WHEN 1 THEN 'Lunes' WHEN 2 THEN 'Martes' WHEN 3 THEN 'Miércoles'
        WHEN 4 THEN 'Jueves' WHEN 5 THEN 'Viernes' WHEN 6 THEN 'Sábado'
        WHEN 7 THEN 'Domingo'
    END AS dia_semana,
    
    -- Trimestre
    EXTRACT(QUARTER FROM fecha_generada)::INT AS trimestre,
    
    -- 7. Año-Mes (YYYYMM) para ordenamiento
    CAST(TO_CHAR(fecha_generada, 'YYYYMM') AS INT) AS anio_mes,
    
    --Bandera de Fin de Semana (Sábado = 6, Domingo = 7)
    CASE 
        WHEN EXTRACT(ISODOW FROM fecha_generada) IN (6, 7) THEN TRUE 
        ELSE FALSE 
    END AS es_fin_semana,
    
    -- Bandera de Fin de Mes
    CASE 
        WHEN fecha_generada::DATE = (DATE_TRUNC('month', fecha_generada) + INTERVAL '1 month - 1 day')::DATE THEN TRUE 
        ELSE FALSE 
    END AS es_fin_mes

FROM (
    -- Genera una fila por cada día en el rango
    SELECT generate_series(
        '2020-01-01'::DATE, 
        '2030-12-31'::DATE, 
        '1 day'::INTERVAL
    ) AS fecha_generada
) AS generador;

INSERT INTO dim_tiempo (
    sk_fecha, 
    fecha, 
    anio, 
    mes, 
    dia, 
    nombre_mes, 
    dia_semana, 
    trimestre, 
    anio_mes, 
    es_fin_semana, 
    es_fin_mes
) VALUES (
    -1, 
    '1900-01-01', 
    1900, 
    1, 
    1, 
    'DESCONOCIDO', 
    'DESCONOCIDO', 
    0, 
    190001, 
    false, 
    false
);


SELECT * FROM dim_tiempo LIMIT 15;