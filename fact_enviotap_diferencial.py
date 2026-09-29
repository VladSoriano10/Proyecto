"""Reconciliación del estado actual de cada TAP, incluidos cambios posteriores."""

from db_config import engine_destino, engine_origen, probar_conexiones
from etl_diferencial_utils import reconciliar_fact


CONSULTA_ORIGEN = """
    SELECT upper(trim(id_operador)) AS nk_id_operador,
        coalesce(nullif(upper(trim(estado_envio)),''),'DESCONOCIDO') AS estado_envio,
        coalesce(cantidad_cdrs_incluidos,0) AS cantidad_cdrs_incluidos,
        coalesce(monto_total_sdr,0) AS monto_total_sdr,
        coalesce(intento_transmision,1) AS intento_transmision,
        fecha_creacion, fecha_envio_ftp, 1 AS cantidad_envios FROM byte_envio_tap_log
"""

DDL_TEMPORAL = """
    nk_id_operador varchar(10), estado_envio varchar(30), cantidad_cdrs_incluidos integer,
    monto_total_sdr numeric(12,4), intento_transmision integer,
    fecha_creacion timestamp NOT NULL, fecha_envio_ftp timestamp, cantidad_envios integer
"""

CONSULTA_CANDIDATOS = """
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


def diferencial_fact_envio_tap():
    return reconciliar_fact(engine_origen, engine_destino, "fact_envio_tap", CONSULTA_ORIGEN,
        DDL_TEMPORAL, CONSULTA_CANDIDATOS,
        ["sk_fecha_creacion", "sk_fecha_envio", "sk_operador", "estado_envio",
         "cantidad_cdrs_incluidos", "monto_total_sdr", "intento_transmision", "cantidad_envios"],
        "sk_fecha_creacion", ["sk_fecha_creacion", "sk_fecha_envio"],
        ["cantidad_cdrs_incluidos", "monto_total_sdr", "intento_transmision", "cantidad_envios"])


if __name__ == "__main__":
    if probar_conexiones():
        diferencial_fact_envio_tap()
