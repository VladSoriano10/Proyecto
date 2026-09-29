import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_fact_roaming():
    print("\n--- Iniciando proceso ETL (Carga Inicial) para fact_roaming ---")

    #EXTRACCIÓN (Consolidación Multitabla)
    print("-> 1. Extrayendo y consolidando tráfico (GPRS, PORTAL, CAMEL)...")

    # Unimos las 3 tablas alineando sus columnas a la estructura del DW
    query_hechos = """
        SELECT 
            id_operador,
            id_tarifa_aplicada AS id_tarifa,
            'GPRS' AS codigo_servicio,
            fecha_hora_conexion AS fecha_transaccion,
            COALESCE(total_volumen_kb, 0) AS volumen_kb,
            0 AS duracion_min,
            COALESCE(monto_sdr, 0) AS monto_sdr,
            COALESCE(monto_local_usd, 0) AS monto_local_usd,
            0 AS cantidad_eventos
        FROM byte_gprs_sv
        
        UNION ALL
        
        SELECT 
            id_operador,
            id_tarifa_aplicada AS id_tarifa,
            'PORTAL' AS codigo_servicio,
            fecha_hora_llamada AS fecha_transaccion,
            0 AS volumen_kb,
            COALESCE(duracion_facturada_min, 0) AS duracion_min,
            COALESCE(monto_sdr, 0) AS monto_sdr,
            COALESCE(monto_local_usd, 0) AS monto_local_usd,
            0 AS cantidad_eventos
        FROM byte_portal_sv
        
        UNION ALL
        
        SELECT 
            id_operador,
            id_tarifa_aplicada AS id_tarifa,
            'CAMEL' AS codigo_servicio,
            fecha_hora_evento AS fecha_transaccion,
            0 AS volumen_kb,
            0 AS duracion_min,
            COALESCE(monto_sdr, 0) AS monto_sdr,
            COALESCE(monto_local_usd, 0) AS monto_local_usd,
            1 AS cantidad_eventos
        FROM byte_camel_sv;
    """

    df_hechos = pd.read_sql(query_hechos, con=engine_origen)
    print(f"   Se extrajeron {len(df_hechos)} registros consolidados de tráfico.")

    print("-> 2. Descargando Llaves Subrogadas (SK) de las Dimensiones...")
    df_dim_operador = pd.read_sql(
        "SELECT sk_operador, nk_id_operador FROM dim_operador;", con=engine_destino
    )
    df_dim_tarifa = pd.read_sql(
        "SELECT sk_tarifa, nk_id_tarifa FROM dim_tarifa;", con=engine_destino
    )
    df_dim_servicio = pd.read_sql(
        "SELECT sk_servicio, tipo_servicio FROM dim_servicio;", con=engine_destino
    )

    # 2. TRANSFORMACIÓN Y CRUZAMIENTO 

    print("-> 3. Ejecutando cruces masivos en memoria...")

    # --- Asegurar Tipos de Datos de las Métricas ---
    df_hechos["volumen_kb"] = df_hechos["volumen_kb"].astype(float)
    df_hechos["duracion_min"] = df_hechos["duracion_min"].astype(float)
    df_hechos["monto_sdr"] = df_hechos["monto_sdr"].astype(float)
    df_hechos["monto_local_usd"] = df_hechos["monto_local_usd"].astype(float)
    df_hechos["cantidad_eventos"] = df_hechos["cantidad_eventos"].astype(int)

    # ---Lookup de Tiempo ---
    df_hechos["sk_fecha"] = pd.to_datetime(df_hechos["fecha_transaccion"]).dt.strftime(
        "%Y%m%d"
    )
    df_hechos["sk_fecha"] = df_hechos["sk_fecha"].fillna("19000101").astype(int)

    # --- Lookup de Operador ---
    df_hechos["id_operador"] = df_hechos["id_operador"].str.strip().str.upper()
    df_hechos = df_hechos.merge(
        df_dim_operador, left_on="id_operador", right_on="nk_id_operador", how="left"
    )

    # ---Lookup de Tarifa ---
    df_hechos["id_tarifa"] = df_hechos["id_tarifa"].fillna(-1).astype(int)
    df_hechos = df_hechos.merge(
        df_dim_tarifa, left_on="id_tarifa", right_on="nk_id_tarifa", how="left"
    )

    # --- Lookup de Servicio ---
    mapeo_servicios = {
        "GPRS": "GPRS - DATOS MÓVILES",
        "PORTAL": "PORTAL - VOZ",
        "CAMEL": "CAMEL - EVENTOS",
    }
    df_hechos["servicio_temp"] = df_hechos["codigo_servicio"].replace(mapeo_servicios)

    # Para asegurar el cruce, convertimos los textos de la dimensión a mayúsculas en el momento
    df_dim_servicio["tipo_servicio_upper"] = (
        df_dim_servicio["tipo_servicio"].str.strip().str.upper()
    )

    df_hechos = df_hechos.merge(
        df_dim_servicio,
        left_on="servicio_temp",
        right_on="tipo_servicio_upper",
        how="left",
    )

    # --- Control de Calidad 
    df_hechos["sk_operador"] = df_hechos["sk_operador"].fillna(-1).astype(int)
    df_hechos["sk_tarifa"] = df_hechos["sk_tarifa"].fillna(-1).astype(int)
    df_hechos["sk_servicio"] = df_hechos["sk_servicio"].fillna(-1).astype(int)

    # Mapeo de columnas para el INSERT
    columnas_finales = [
        "sk_fecha",
        "sk_operador",
        "sk_tarifa",
        "sk_servicio",
        "volumen_kb",
        "duracion_min",
        "monto_sdr",
        "monto_local_usd",
        "cantidad_eventos",
    ]
    df_final = df_hechos[columnas_finales]

    # LIMPIEZA PREVIA Y CARGA
    print("-> 4. Limpiando tabla fact_roaming (Idempotencia)...")
    with engine_destino.begin() as conn:
        conn.execute(text("TRUNCATE TABLE fact_roaming RESTART IDENTITY CASCADE;"))

    print("-> 5. Cargando facturación masiva a 'DWRoamingMovistar'...")
    df_final.to_sql(
        name="fact_roaming", con=engine_destino, if_exists="append", index=False
    )

    print(
        f"¡Carga estelar exitosa! Se cruzaron e insertaron {len(df_final)} consumos en fact_roaming.\n"
    )


if __name__ == "__main__":
    if probar_conexiones():
        cargar_fact_roaming()
    else:
        print("\nProceso ETL abortado debido a problemas de conexión.")
