"""Consultas únicas para las cargas iniciales y diferenciales de hechos."""
from db_config import engine_origen, engine_destino
from etl_comun import reconciliar_fact

CONSULTA_ORIGEN_ROAMING = """
    SELECT upper(trim(id_operador)) AS nk_id_operador,
        coalesce(id_tarifa_aplicada,-1) AS nk_id_tarifa,
        fecha_hora_conexion AS fecha_transaccion,
        coalesce(total_volumen_kb,0) AS volumen_kb, 0 AS duracion_min,
        coalesce(monto_sdr,0) AS monto_sdr, coalesce(monto_local_usd,0) AS monto_local_usd,
        0 AS cantidad_eventos, factor_cambio_aplicado
    FROM byte_gprs_sv
    UNION ALL
    SELECT upper(trim(id_operador)), coalesce(id_tarifa_aplicada,-1), fecha_hora_llamada,
        0, coalesce(duracion_facturada_min,0), coalesce(monto_sdr,0),
        coalesce(monto_local_usd,0), 0, NULL::numeric FROM byte_portal_sv
    UNION ALL
    SELECT upper(trim(id_operador)), coalesce(id_tarifa_aplicada,-1), fecha_hora_evento,
        0, 0, coalesce(monto_sdr,0), coalesce(monto_local_usd,0), 1,
        NULL::numeric FROM byte_camel_sv
"""
DDL_TEMPORAL_ROAMING = """
    nk_id_operador varchar(10), nk_id_tarifa integer, fecha_transaccion timestamp NOT NULL,
    volumen_kb numeric(12,2), duracion_min numeric(8,2), monto_sdr numeric(10,4),
    monto_local_usd numeric(10,4), cantidad_eventos integer, factor_cambio_aplicado numeric(12,6)
"""
CONSULTA_CANDIDATOS_ROAMING = """
    SELECT to_char(s.fecha_transaccion,'YYYYMMDD')::integer AS sk_fecha,
        coalesce(o.sk_operador,-1) AS sk_operador, coalesce(t.sk_tarifa,-1) AS sk_tarifa,
        coalesce(r.sk_tasa,-1) AS sk_tasa, s.volumen_kb, s.duracion_min,
        s.monto_sdr, s.monto_local_usd, s.cantidad_eventos
    FROM _etl_origen s
    LEFT JOIN LATERAL (
        SELECT sk_operador FROM dim_operador
        WHERE nk_id_operador=s.nk_id_operador AND sk_operador<>-1
          AND s.fecha_transaccion::date BETWEEN fecha_inicio_vigencia AND fecha_fin_vigencia
        ORDER BY fecha_inicio_vigencia DESC, sk_operador DESC LIMIT 1
    ) o ON true
    LEFT JOIN LATERAL (
        SELECT sk_tarifa FROM dim_tarifa
        WHERE nk_id_tarifa=s.nk_id_tarifa AND sk_tarifa<>-1
          AND s.fecha_transaccion::date BETWEEN fecha_inicio_vigencia AND fecha_fin_vigencia
        ORDER BY fecha_inicio_vigencia DESC, sk_tarifa DESC LIMIT 1
    ) t ON true
    LEFT JOIN LATERAL (
        SELECT sk_tasa FROM dim_tasa_cambio
        WHERE moneda_origen='SDR' AND moneda_destino='USD' AND sk_tasa<>-1
          AND s.fecha_transaccion BETWEEN fecha_desde AND fecha_hasta
          AND (s.factor_cambio_aplicado IS NULL OR factor_cambio=s.factor_cambio_aplicado)
        ORDER BY fecha_desde DESC, sk_tasa DESC LIMIT 1
    ) r ON true
"""

def procesar_fact_roaming(modo):
    return reconciliar_fact(engine_origen, engine_destino, "fact_roaming", CONSULTA_ORIGEN_ROAMING,
        DDL_TEMPORAL_ROAMING, CONSULTA_CANDIDATOS_ROAMING,
        ["sk_fecha", "sk_operador", "sk_tarifa", "sk_tasa", "volumen_kb", "duracion_min",
         "monto_sdr", "monto_local_usd", "cantidad_eventos"], "sk_fecha", ["sk_fecha"],
        ["volumen_kb", "duracion_min", "monto_sdr", "monto_local_usd", "cantidad_eventos"], modo=modo)

CONSULTA_ORIGEN_TAP = """
    SELECT upper(trim(id_operador)) AS nk_id_operador,
        coalesce(nullif(upper(trim(estado_envio)),''),'DESCONOCIDO') AS estado_envio,
        coalesce(cantidad_cdrs_incluidos,0) AS cantidad_cdrs_incluidos,
        coalesce(monto_total_sdr,0) AS monto_total_sdr,
        coalesce(intento_transmision,1) AS intento_transmision,
        fecha_creacion, fecha_envio_ftp, 1 AS cantidad_envios FROM byte_envio_tap_log
"""
DDL_TEMPORAL_TAP = """
    nk_id_operador varchar(10), estado_envio varchar(30), cantidad_cdrs_incluidos integer,
    monto_total_sdr numeric(12,4), intento_transmision integer,
    fecha_creacion timestamp NOT NULL, fecha_envio_ftp timestamp, cantidad_envios integer
"""
CONSULTA_CANDIDATOS_TAP = """
    SELECT to_char(s.fecha_creacion,'YYYYMMDD')::integer AS sk_fecha_creacion,
        coalesce(to_char(s.fecha_envio_ftp,'YYYYMMDD')::integer,-1) AS sk_fecha_envio,
        coalesce(o.sk_operador,-1) AS sk_operador, s.estado_envio,
        s.cantidad_cdrs_incluidos, s.monto_total_sdr, s.intento_transmision, s.cantidad_envios
    FROM _etl_origen s
    LEFT JOIN LATERAL (
        SELECT sk_operador FROM dim_operador
        WHERE nk_id_operador=s.nk_id_operador AND sk_operador<>-1
          AND s.fecha_creacion::date BETWEEN fecha_inicio_vigencia AND fecha_fin_vigencia
        ORDER BY fecha_inicio_vigencia DESC, sk_operador DESC LIMIT 1
    ) o ON true
"""

def procesar_fact_tap(modo):
    return reconciliar_fact(engine_origen, engine_destino, "fact_envio_tap", CONSULTA_ORIGEN_TAP,
        DDL_TEMPORAL_TAP, CONSULTA_CANDIDATOS_TAP,
        ["sk_fecha_creacion", "sk_fecha_envio", "sk_operador", "estado_envio",
         "cantidad_cdrs_incluidos", "monto_total_sdr", "intento_transmision", "cantidad_envios"],
        "sk_fecha_creacion", ["sk_fecha_creacion", "sk_fecha_envio"],
        ["cantidad_cdrs_incluidos", "monto_total_sdr", "intento_transmision", "cantidad_envios"], modo=modo)
