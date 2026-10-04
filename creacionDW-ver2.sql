-- CREACIÓN DEL DATA WAREHOUSE
-- Ejecutar en la base de datos DESTINO.
-- Después ejecutar: dim_tiempo llenado.sql

BEGIN;

SET LOCAL search_path TO public;

-- ============================================================
-- DIMENSIONES
-- ============================================================

CREATE TABLE public.dim_tiempo (
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

CREATE TABLE public.dim_operador (
    sk_operador SERIAL PRIMARY KEY,
    nk_id_operador VARCHAR(10) NOT NULL,
    nombre_operador VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    nk_id_pais VARCHAR(5) NOT NULL,
    nombre_pais VARCHAR(100) NOT NULL,
    prefijo_telefonico VARCHAR(10) NOT NULL,

    -- Vigencias para conservar versiones del operador.
    fecha_inicio_vigencia DATE NOT NULL,
    fecha_fin_vigencia DATE NOT NULL
);

CREATE TABLE public.dim_tarifa (
    sk_tarifa SERIAL PRIMARY KEY,
    nk_id_tarifa INT NOT NULL,

    -- Tipo de tráfico asociado a la tarifa.
    tipo_trafico VARCHAR(30) NOT NULL,

    costo_unidad DECIMAL(10,4) NOT NULL,
    moneda VARCHAR(3) NOT NULL,
    fecha_inicio_vigencia DATE NOT NULL,
    fecha_fin_vigencia DATE NOT NULL
);

CREATE TABLE public.dim_tasa_cambio (
    sk_tasa SERIAL PRIMARY KEY,
    nk_id_tasa INT NOT NULL,
    moneda_origen VARCHAR(3) NOT NULL,
    moneda_destino VARCHAR(3) NOT NULL,
    factor_cambio DECIMAL(12,6) NOT NULL,
    fecha_desde TIMESTAMP NOT NULL,
    fecha_hasta TIMESTAMP NOT NULL
);

-- ============================================================
-- TABLA DE HECHOS: TRÁFICO TARIFICADO
-- ============================================================

CREATE TABLE public.fact_roaming (
    id_hecho BIGSERIAL PRIMARY KEY,

    sk_fecha INT NOT NULL
        REFERENCES public.dim_tiempo(sk_fecha),

    sk_operador INT NOT NULL
        REFERENCES public.dim_operador(sk_operador),

    sk_tarifa INT NOT NULL
        REFERENCES public.dim_tarifa(sk_tarifa),

    sk_tasa INT NOT NULL
        REFERENCES public.dim_tasa_cambio(sk_tasa),

    volumen_kb DECIMAL(12,2) NOT NULL,
    duracion_min DECIMAL(8,2) NOT NULL,
    monto_sdr DECIMAL(10,4) NOT NULL,
    monto_local_usd DECIMAL(10,4) NOT NULL,
    cantidad_eventos INT NOT NULL
);

-- TABLA DE HECHOS: ENVÍOS TAP

CREATE TABLE public.fact_envio_tap (
    id_hecho BIGSERIAL PRIMARY KEY,

    sk_fecha_creacion INT NOT NULL
        REFERENCES public.dim_tiempo(sk_fecha),

    sk_fecha_envio INT NOT NULL
        REFERENCES public.dim_tiempo(sk_fecha),

    sk_operador INT NOT NULL
        REFERENCES public.dim_operador(sk_operador),

    -- Estado del envío conservado como atributo descriptivo del hecho.
    estado_envio VARCHAR(30) NOT NULL,

    cantidad_cdrs_incluidos INT NOT NULL,
    monto_total_sdr DECIMAL(12,4) NOT NULL,
    intento_transmision INT NOT NULL,
    cantidad_envios INT NOT NULL
);

-- CONTROL DE EJECUCIONES DEL ETL

CREATE TABLE IF NOT EXISTS public.control_cargas (
    id_control BIGSERIAL PRIMARY KEY,

    id_ejecucion UUID NOT NULL,

    tipo_carga VARCHAR(15) NOT NULL
        CHECK (
            tipo_carga IN ('INICIAL', 'DIFERENCIAL')
        ),

    proceso VARCHAR(80) NOT NULL,
    tabla_destino VARCHAR(63),

    fecha_inicio TIMESTAMPTZ NOT NULL
        DEFAULT clock_timestamp(),

    fecha_fin TIMESTAMPTZ,
    duracion_segundos NUMERIC(14,3),

    estado VARCHAR(20) NOT NULL
        CHECK (
            estado IN (
                'EN_CURSO',
                'EXITOSO',
                'SIN_CAMBIOS',
                'ERROR',
                'REVERTIDO',
                'OMITIDO'
            )
        ),

    registros_leidos BIGINT,
    filas_insertadas BIGINT NOT NULL DEFAULT 0,
    filas_actualizadas BIGINT NOT NULL DEFAULT 0,
    filas_eliminadas BIGINT NOT NULL DEFAULT 0,
    versiones_nuevas BIGINT NOT NULL DEFAULT 0,
    dias_reemplazados BIGINT NOT NULL DEFAULT 0,

    detalle JSONB NOT NULL DEFAULT '{}'::jsonb,
    mensaje TEXT,

    CONSTRAINT control_cargas_proceso_unico
        UNIQUE (id_ejecucion, proceso),

    CONSTRAINT control_cargas_contadores_validos
        CHECK (
            (registros_leidos IS NULL OR registros_leidos >= 0)
            AND filas_insertadas >= 0
            AND filas_actualizadas >= 0
            AND filas_eliminadas >= 0
            AND versiones_nuevas >= 0
            AND dias_reemplazados >= 0
        )
);

CREATE INDEX IF NOT EXISTS control_cargas_fecha_idx
    ON public.control_cargas (fecha_inicio DESC);

-- DOCUMENTACIÓN DEL CONTROL DE CARGAS

COMMENT ON TABLE public.control_cargas IS
    'Una fila LOTE y una por proceso ETL. Historial de ejecuciones, no parámetros ni historial de estados TAP.';

COMMENT ON COLUMN public.control_cargas.id_ejecucion IS
    'Identificador compartido por el lote y sus procesos. No relacionar esta tabla con las facts en Power BI.';

COMMENT ON COLUMN public.control_cargas.tabla_destino IS
    'NULL identifica el resumen del lote; las demás filas identifican cada tabla procesada.';

COMMENT ON COLUMN public.control_cargas.filas_insertadas IS
    'Escrituras confirmadas, incluyendo versiones SCD y comodines; en facts puede incluir reposición de filas existentes.';

COMMENT ON COLUMN public.control_cargas.filas_actualizadas IS
    'Filas existentes modificadas, incluyendo cierres de vigencia SCD.';

COMMENT ON COLUMN public.control_cargas.filas_eliminadas IS
    'Filas eliminadas durante una reconstrucción o reemplazo por fecha; no implica consumos anulados.';

COMMENT ON COLUMN public.control_cargas.detalle IS
    'Resumen técnico, claves desconocidas y parámetros de corte. REVERTIDO conserva intentos en JSON y contadores confirmados cero.';

COMMENT ON COLUMN public.control_cargas.estado IS
    'EN_CURSO no certifica éxito. Una interrupción abrupta puede dejar ese estado; revisar antes de repetir.';

COMMIT;