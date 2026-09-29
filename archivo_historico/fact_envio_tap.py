import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_fact_envio_tap():
    print("\n--- Iniciando proceso ETL (Carga Inicial) para fact_envio_tap ---")

    # EXTRACCIÓN
    print("-> 1. Extrayendo transacciones de la base 'Roaming'...")

    query_hechos = """
        SELECT 
            id_operador,
            COALESCE(fecha_envio_ftp, fecha_creacion, CURRENT_TIMESTAMP) AS fecha_envio,
            estado_envio,
            cantidad_cdrs_incluidos,
            monto_total_sdr,
            intento_transmision, -- Regresado a la ortografía original correcta
            1 AS cantidad_envios
        FROM byte_envio_tap_log;
    """
    df_hechos = pd.read_sql(query_hechos, con=engine_origen)
    print(f"   Se extrajeron {len(df_hechos)} transacciones.")

    print("-> 2. Descargando Llaves Subrogadas (SK) del Data Warehouse...")
    df_dim_operador = pd.read_sql(
        "SELECT sk_operador, nk_id_operador FROM dim_operador;", con=engine_destino
    )
    df_dim_estado = pd.read_sql(
        "SELECT sk_estado_envio, estado_envio FROM dim_estado_envio;",
        con=engine_destino,
    )

    # 2. TRANSFORMACIÓN Y CRUZAMIENTO

    print("-> 3. Ejecutando cruce de llaves (Lookups en memoria)...")

    # --- Limpieza de métricas numéricas ---
    df_hechos["cantidad_cdrs_incluidos"] = (
        df_hechos["cantidad_cdrs_incluidos"].fillna(0).astype(int)
    )
    df_hechos["monto_total_sdr"] = (
        df_hechos["monto_total_sdr"].fillna(0.0).astype(float)
    )
    df_hechos["intento_transmision"] = (
        df_hechos["intento_transmision"].fillna(1).astype(int)
    )

    # ---Lookup de Tiempo ---
    df_hechos["sk_fecha"] = pd.to_datetime(df_hechos["fecha_envio"]).dt.strftime(
        "%Y%m%d"
    )
    df_hechos["sk_fecha"] = df_hechos["sk_fecha"].fillna("19000101").astype(int)

    # ---Lookup de Operador ---
    df_hechos["id_operador"] = df_hechos["id_operador"].str.strip().str.upper()
    df_hechos = df_hechos.merge(
        df_dim_operador, left_on="id_operador", right_on="nk_id_operador", how="left"
    )

    # --- Lookup de Estado ---
    mapeo_estados = {
        "PEN": "PENDIENTE DE ENVÍO",
        "ENV": "ENVIADO EXITOSAMENTE",
        "ERR": "ERROR DE TRANSMISIÓN",
        "RECH": "RECHAZADO POR SYNIVERSE",
    }
    df_hechos["estado_envio_temp"] = (
        df_hechos["estado_envio"]
        .fillna("SIN ESTADO")
        .str.strip()
        .str.upper()
        .replace(mapeo_estados)
    )

    df_hechos = df_hechos.merge(
        df_dim_estado, left_on="estado_envio_temp", right_on="estado_envio", how="left"
    )

    # --- Control de Calidad de Llaves Subrogadas ---
    df_hechos["sk_operador"] = df_hechos["sk_operador"].fillna(-1).astype(int)
    df_hechos["sk_estado_envio"] = df_hechos["sk_estado_envio"].fillna(-1).astype(int)

    # Alineamos las columnas 
    columnas_finales = [
        "sk_fecha",
        "sk_operador",
        "sk_estado_envio",
        "cantidad_cdrs_incluidos",
        "monto_total_sdr",
        "intento_transmision",  
        "cantidad_envios",
    ]
    df_final = df_hechos[columnas_finales]


    #LIMPIEZA PREVIA Y CARGA
    print("-> 4. Limpiando tabla de hechos (Idempotencia)...")
    with engine_destino.begin() as conn:
        conn.execute(text("TRUNCATE TABLE fact_envio_tap RESTART IDENTITY CASCADE;"))

    print("-> 5. Cargando métricas cruzadas a 'DWRoamingMovistar'...")
    df_final.to_sql(
        name="fact_envio_tap", con=engine_destino, if_exists="append", index=False
    )

    print(
        f"¡Carga exitosa! Se insertaron {len(df_final)} métricas en fact_envio_tap.\n"
    )


if __name__ == "__main__":
    if probar_conexiones():
        cargar_fact_envio_tap()
    else:
        print("\n Proceso ETL abortado debido a problemas de conexión.")
