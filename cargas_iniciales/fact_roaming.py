import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_fact_roaming():
    print("\n--- Iniciando proceso ETL (Carga Inicial) para fact_roaming ---")

    # 1. EXTRACCIÓN 
    print("-> 1. Extrayendo y consolidando tráfico (GPRS, PORTAL, CAMEL)...")
    
    query_hechos = """
        SELECT 
            id_operador,
            id_tarifa_aplicada AS id_tarifa,
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

    # 2. DESCARGA DE DIMENSIONES (Lookups)
    print("-> 2. Descargando Llaves Subrogadas (SK) del Data Warehouse...")
    
    df_dim_operador = pd.read_sql("SELECT sk_operador, nk_id_operador FROM dim_operador;", con=engine_destino)
    df_dim_tarifa = pd.read_sql("SELECT sk_tarifa, nk_id_tarifa FROM dim_tarifa;", con=engine_destino)
    
    # [CORRECCIÓN CRÍTICA APLICADA]: Solo traemos el historial de la moneda SDR para evitar cruces con Bitcoin o Euros
    df_dim_tasa = pd.read_sql("SELECT sk_tasa, fecha_desde FROM dim_tasa_cambio WHERE moneda_origen = 'SDR';", con=engine_destino)


    # 3. TRANSFORMACIÓN Y CRUZAMIENTO
    print("-> 3. Ejecutando cruces masivos y asignando llaves comodín (-1)...")

    # --- Tipos de Datos Numéricos ---
    df_hechos['volumen_kb'] = df_hechos['volumen_kb'].astype(float)
    df_hechos['duracion_min'] = df_hechos['duracion_min'].astype(float)
    df_hechos['monto_sdr'] = df_hechos['monto_sdr'].astype(float)
    df_hechos['monto_local_usd'] = df_hechos['monto_local_usd'].astype(float)
    df_hechos['cantidad_eventos'] = df_hechos['cantidad_eventos'].astype(int)

    # --- Lookup de Tiempo ---
    df_hechos['fecha_dt'] = pd.to_datetime(df_hechos['fecha_transaccion'])
    df_hechos['sk_fecha'] = df_hechos['fecha_dt'].dt.strftime('%Y%m%d').fillna('-1').astype(int)

    # --- Lookup de Operador ---
    df_hechos['id_operador'] = df_hechos['id_operador'].astype(str).str.strip().str.upper()
    df_hechos = df_hechos.merge(
        df_dim_operador, 
        left_on='id_operador', 
        right_on='nk_id_operador', 
        how='left'
    )
    df_hechos['sk_operador'] = df_hechos['sk_operador'].fillna(-1).astype(int)

    # --- Lookup de Tarifa ---
    df_hechos['id_tarifa'] = df_hechos['id_tarifa'].fillna(-1).astype(int)
    df_hechos = df_hechos.merge(
        df_dim_tarifa,
        left_on='id_tarifa',
        right_on='nk_id_tarifa',
        how='left'
    )
    df_hechos['sk_tarifa'] = df_hechos['sk_tarifa'].fillna(-1).astype(int)

    # --- Lookup Temporal (Tasa de Cambio) ---
    # Convertimos fechas y ordenamos estrictamente los DataFrames para que el merge_asof funcione
    df_dim_tasa['fecha_desde'] = pd.to_datetime(df_dim_tasa['fecha_desde'])
    
    df_hechos = df_hechos.sort_values('fecha_dt')
    df_dim_tasa = df_dim_tasa.sort_values('fecha_desde')

    # merge_asof busca hacia atrás la tasa SDR que estaba vigente en el momento exacto de la transacción
    df_hechos = pd.merge_asof(
        df_hechos,
        df_dim_tasa[['sk_tasa', 'fecha_desde']],
        left_on='fecha_dt',
        right_on='fecha_desde',
        direction='backward'
    )
    df_hechos['sk_tasa'] = df_hechos['sk_tasa'].fillna(-1).astype(int)

    # Mapeo exacto de columnas para el INSERT en DWRoamingMovistar
    columnas_finales = [
        'sk_fecha',
        'sk_operador',
        'sk_tarifa',
        'sk_tasa',
        'volumen_kb',
        'duracion_min',
        'monto_sdr',
        'monto_local_usd',
        'cantidad_eventos'
    ]
    df_final = df_hechos[columnas_finales]


    # 4. CARGA AL DATA WAREHOUSE
    print("-> 4. Limpiando tabla fact_roaming (Idempotencia)...")
    with engine_destino.begin() as conn:
        conn.execute(text("TRUNCATE TABLE fact_roaming RESTART IDENTITY CASCADE;"))
        
    print("-> 5. Cargando facturación masiva a 'DWRoamingMovistar'...")
    df_final.to_sql(
        name='fact_roaming', 
        con=engine_destino, 
        if_exists='append', 
        index=False
    )
    
    print(f"¡Carga exitosa! Se insertaron {len(df_final)} consumos en fact_roaming.\n")

if __name__ == '__main__':
    if probar_conexiones():
        cargar_fact_roaming()
    else:
        print("\nProceso ETL abortado debido a problemas de conexión.")