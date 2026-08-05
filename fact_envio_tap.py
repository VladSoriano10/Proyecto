import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_fact_envio_tap():
    print("\n--- Iniciando proceso ETL (Carga Inicial) para fact_envio_tap ---")

    # EXTRACCIÓN
    print("-> 1. Extrayendo log de envíos TAP de la base 'Roaming'...")
    
    query_hechos = """
        SELECT 
            fecha_creacion,
            fecha_envio_ftp,
            id_operador,
            estado_envio,
            COALESCE(cantidad_cdrs_incluidos, 0) AS cantidad_cdrs_incluidos,
            COALESCE(monto_total_sdr, 0) AS monto_total_sdr,
            COALESCE(intento_transmision, 0) AS intento_transmision
        FROM byte_envio_tap_log;
    """
    
    df_hechos = pd.read_sql(query_hechos, con=engine_origen)
    print(f"   Se extrajeron {len(df_hechos)} registros de envíos TAP.")

    # DESCARGA DE DIMENSIONES (Lookups)
    print("-> 2. Descargando Llaves Subrogadas (SK) del Data Warehouse...")
    df_dim_operador = pd.read_sql("SELECT sk_operador, nk_id_operador FROM dim_operador;", con=engine_destino)

    # TRANSFORMACIÓN Y CRUZAMIENTO
    print("-> 3. Aplicando Role-Playing Dimensions y Dimensión Degenerada...")

    # --- Tipos de Datos Numéricos ---
    df_hechos['cantidad_cdrs_incluidos'] = df_hechos['cantidad_cdrs_incluidos'].astype(int)
    df_hechos['monto_total_sdr'] = df_hechos['monto_total_sdr'].astype(float)
    df_hechos['intento_transmision'] = df_hechos['intento_transmision'].astype(int)
    
    # Métrica base para facilitar el recuento de envíos
    df_hechos['cantidad_envios'] = 1

    # --- Dimensión Degenerada (Estado de Envío) ---
    df_hechos['estado_envio'] = df_hechos['estado_envio'].fillna('DESCONOCIDO').str.strip().str.upper()

    # --- Role-Playing Dimension de Tiempo (sk_fecha_creacion y sk_fecha_envio) ---
    # Procesamiento sk_fecha_creacion (asumimos que siempre viene llena, pero nos protegemos)
    df_hechos['fecha_creacion_dt'] = pd.to_datetime(df_hechos['fecha_creacion'])
    df_hechos['sk_fecha_creacion'] = df_hechos['fecha_creacion_dt'].dt.strftime('%Y%m%d').fillna('-1').astype(int)

    # Procesamiento sk_fecha_envio (puede venir nula si aún no se envía)
    df_hechos['fecha_envio_dt'] = pd.to_datetime(df_hechos['fecha_envio_ftp'])
    df_hechos['sk_fecha_envio'] = df_hechos['fecha_envio_dt'].dt.strftime('%Y%m%d').fillna('-1').astype(int)

    # --- Lookup de Operador ---
    df_hechos['id_operador'] = df_hechos['id_operador'].str.strip().str.upper()
    df_hechos = df_hechos.merge(
        df_dim_operador, 
        left_on='id_operador', 
        right_on='nk_id_operador', 
        how='left'
    )
    # Protegemos contra nulos asignando el ID del Registro Desconocido
    df_hechos['sk_operador'] = df_hechos['sk_operador'].fillna(-1).astype(int)

    # Mapeo exacto de columnas para el INSERT
    columnas_finales = [
        'sk_fecha_creacion',
        'sk_fecha_envio',
        'sk_operador',
        'estado_envio',
        'cantidad_cdrs_incluidos',
        'monto_total_sdr',
        'intento_transmision',
        'cantidad_envios'
    ]
    df_final = df_hechos[columnas_finales]


    # CARGA

    print("-> 4. Limpiando tabla fact_envio_tap (Idempotencia)...")
    with engine_destino.begin() as conn:
        conn.execute(text("TRUNCATE TABLE fact_envio_tap RESTART IDENTITY CASCADE;"))
        
    print("-> 5. Cargando registros de clearing a 'DWRoamingMovistar'...")
    df_final.to_sql(
        name='fact_envio_tap', 
        con=engine_destino, 
        if_exists='append', 
        index=False
    )
    
    print(f"¡Carga exitosa! Se insertaron {len(df_final)} lotes de envío en fact_envio_tap.\n")

if __name__ == '__main__':
    if probar_conexiones():
        cargar_fact_envio_tap()
    else:
        print("\n Proceso ETL abortado debido a problemas de conexión.")