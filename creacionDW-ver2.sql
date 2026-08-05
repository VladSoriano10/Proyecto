
-- CREACIÓN DEL DATA WAREHOUSE 

-- DIMENSIONES

CREATE TABLE dim_tiempo (
    sk_fecha INT PRIMARY KEY,
    fecha DATE NOT NULL,
    anio INT NOT NULL,
    mes INT NOT NULL,
    dia INT NOT NULL,
    nombre_mes VARCHAR(20) NOT NULL,
    dia_semana VARCHAR(20) NOT NULL,
    trimestre INT NOT NULL,
    anio_mes INT NOT NULL,
    es_fin_semana BOOLEAN NOT NULL,
    es_fin_mes BOOLEAN NOT NULL
);

CREATE TABLE dim_operador (
    sk_operador SERIAL PRIMARY KEY,
    nk_id_operador VARCHAR(10) NOT NULL,
    nombre_operador VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    nk_id_pais VARCHAR(5) NOT NULL,
    nombre_pais VARCHAR(100) NOT NULL,
    prefijo_telefonico VARCHAR(10) NOT NULL,
    
    -- Nuevos campos para soportar el SCD Tipo 2
    fecha_inicio_vigencia DATE NOT NULL,
    fecha_fin_vigencia DATE NOT NULL
);

CREATE TABLE dim_tarifa (
    sk_tarifa SERIAL PRIMARY KEY,
    nk_id_tarifa INT NOT NULL,
    tipo_trafico VARCHAR(30) NOT NULL, -- Actúa como dimensión absorbida (GPRS, VOZ, CAMEL)
    costo_unidad DECIMAL(10,4) NOT NULL,
    moneda VARCHAR(3) NOT NULL,
    fecha_inicio_vigencia DATE NOT NULL,
    fecha_fin_vigencia DATE NOT NULL
);

CREATE TABLE dim_tasa_cambio (
    sk_tasa SERIAL PRIMARY KEY,
    nk_id_tasa INT NOT NULL,
    moneda_origen VARCHAR(3) NOT NULL,
    moneda_destino VARCHAR(3) NOT NULL,
    factor_cambio DECIMAL(12,6) NOT NULL,
    fecha_desde TIMESTAMP NOT NULL,
    fecha_hasta TIMESTAMP NOT NULL
);


-- TABLA DE HECHOS 1: PRODUCCIÓN Y TRÁFICO (fact_roaming)


CREATE TABLE fact_roaming (
    id_hecho BIGSERIAL PRIMARY KEY,
    sk_fecha INT NOT NULL REFERENCES dim_tiempo(sk_fecha),
    sk_operador INT NOT NULL REFERENCES dim_operador(sk_operador),
    sk_tarifa INT NOT NULL REFERENCES dim_tarifa(sk_tarifa),
    sk_tasa INT NOT NULL REFERENCES dim_tasa_cambio(sk_tasa), -- contexto financiero
    
    volumen_kb DECIMAL(12,2) NOT NULL,
    duracion_min DECIMAL(8,2) NOT NULL,
    monto_sdr DECIMAL(10,4) NOT NULL,
    monto_local_usd DECIMAL(10,4) NOT NULL,
    cantidad_eventos INT NOT NULL
);


-- TABLA DE HECHOS 2: ENVÍOS TAP (fact_envio_tap)

CREATE TABLE fact_envio_tap (
    id_hecho BIGSERIAL PRIMARY KEY,
    
    -- Role-Playing Dimensions (Múltiples referencias a dim_tiempo)
    sk_fecha_creacion INT NOT NULL REFERENCES dim_tiempo(sk_fecha),
    sk_fecha_envio INT NOT NULL REFERENCES dim_tiempo(sk_fecha),
    
    sk_operador INT NOT NULL REFERENCES dim_operador(sk_operador),
    
    -- Dimensión Degenerada
    estado_envio VARCHAR(30) NOT NULL, 
    
    cantidad_cdrs_incluidos INT NOT NULL,
    monto_total_sdr DECIMAL(12,4) NOT NULL,
    intento_transmision INT NOT NULL,
    cantidad_envios INT NOT NULL
);