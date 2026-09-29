-- CREACIÓN DE LA BASE DE DATOS DEL DATA WAREHOUSE

--DIMENSIONES 


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
    status VARCHAR(10) NOT NULL,
    nk_id_pais VARCHAR(5) NOT NULL,
    nombre_pais VARCHAR(100) NOT NULL,
    prefijo_telefonico VARCHAR(10) NOT NULL
);


CREATE TABLE dim_tarifa (
    sk_tarifa SERIAL PRIMARY KEY,
    nk_id_tarifa INT NOT NULL,
    tipo_trafico VARCHAR(10) NOT NULL,
    costo_unidad DECIMAL(10,4) NOT NULL,
    moneda VARCHAR(3) NOT NULL,
    fecha_inicio_vigencia DATE NOT NULL,
    fecha_fin_vigencia DATE NOT NULL
);

CREATE TABLE dim_servicio (
    sk_servicio SERIAL PRIMARY KEY,
    tipo_servicio VARCHAR(20) NOT NULL
);


CREATE TABLE dim_estado_envio (
    sk_estado_envio SERIAL PRIMARY KEY,
    estado_envio VARCHAR(20) NOT NULL
);


-- TABLA DE HECHOS fact_roaming

CREATE TABLE fact_roaming (
    id_hecho BIGSERIAL PRIMARY KEY,
    sk_fecha INT NOT NULL REFERENCES dim_tiempo(sk_fecha),
    sk_operador INT NOT NULL REFERENCES dim_operador(sk_operador),
    sk_tarifa INT NOT NULL REFERENCES dim_tarifa(sk_tarifa),
    sk_servicio INT NOT NULL REFERENCES dim_servicio(sk_servicio),
    
    volumen_kb DECIMAL(12,2) NOT NULL,
    duracion_min DECIMAL(8,2) NOT NULL,
    monto_sdr DECIMAL(10,4) NOT NULL,
    monto_local_usd DECIMAL(10,4) NOT NULL,
    cantidad_eventos INT NOT NULL
);


-- TABLA DE HECHOS fact_envio_tap


CREATE TABLE fact_envio_tap (
    id_hecho BIGSERIAL PRIMARY KEY,
    sk_fecha INT NOT NULL REFERENCES dim_tiempo(sk_fecha),
    sk_operador INT NOT NULL REFERENCES dim_operador(sk_operador),
    sk_estado_envio INT NOT NULL REFERENCES dim_estado_envio(sk_estado_envio),
    
    cantidad_cdrs_incluidos INT NOT NULL,
    monto_total_sdr DECIMAL(12,4) NOT NULL,
    intento_transmision INT NOT NULL,
    cantidad_envios INT NOT NULL
);