import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def diferencial_fact_envio_tap():
    print("\n--- Iniciando Carga INCREMENTAL para fact_envio_tap ---")


    # LEER LA MARCA DE AGUA (sk_fecha_creacion)

    print("-> 1. Buscando la última fecha de envío cargada en el Data Warehouse...")
    
    # Usamos sk_fecha_creacion como nuestra marca de agua
    query_hwm = """
        SELECT COALESCE(MAX(sk_fecha_creacion), 19000101) 
        FROM fact_envio_tap;
    """
    with engine_destino.connect() as conn:
        ultima_sk_fecha = conn.execute(text(query_hwm)).scalar()
        
    print(f"   Última fecha registrada (sk_fecha_creacion): {ultima_sk_fecha}")


    # EXTRACCIÓN DE NUEVOS ENVÍOS TAP

    print("-> 2. Extrayendo nuevos registros de logs de envío TAP...")
    
    # Extraemos de la tabla byte_envio_tap_log
    query_origen = f"""
        SELECT 
            id_operador AS nk_id_operador,
            COALESCE(estado_envio, 'DESCONOCIDO') AS estado_envio,
            COALESCE(cantidad_cdrs_incluidos, 0) AS cantidad_cdrs_incluidos,
            COALESCE(monto_total_sdr, 0) AS monto_total_sdr,
            COALESCE(intento_transmision, 1) AS intento_transmision,
            fecha_creacion,
            fecha_envio_ftp,
            1 AS cantidad_envios -- Métrica estática para contar cuántos archivos se enviaron
        FROM byte_envio_tap_log
        WHERE TO_CHAR(fecha_creacion, 'YYYYMMDD')::INT > {ultima_sk_fecha};
    """
    df_hechos = pd.read_sql(query_origen, con=engine_origen)

    if df_hechos.empty:
        print("-> 3. No hay envíos TAP nuevos. El DW está al día.\n")
        return

    print(f"   Se extrajeron {len(df_hechos)} nuevos registros de envío TAP.")

    # Convertimos fechas a Date (para comparar en el lookup)
    df_hechos['fecha_comparacion'] = pd.to_datetime(df_hechos['fecha_creacion']).dt.date
    
    # Generamos las dos SK de tiempo (Role-Playing)
    df_hechos['sk_fecha_creacion'] = pd.to_datetime(df_hechos['fecha_creacion']).dt.strftime('%Y%m%d').astype(int)
    
    # Para fecha_envio_ftp, puede que sea NULA (si el envío falló). Si es nula, ponemos el comodín -1.
    df_hechos['sk_fecha_envio'] = pd.to_datetime(df_hechos['fecha_envio_ftp']).dt.strftime('%Y%m%d')
    df_hechos['sk_fecha_envio'] = df_hechos['sk_fecha_envio'].fillna(-1).astype(int)

    # BÚSQUEDA DE LLAVES SUBROGADAS (SCD2 Lookup para Operador)
    print("-> 3. Cruzando llaves subrogadas (Operador)...")

    # --- LOOKUP: DIM_OPERADOR ---
    df_dim_op = pd.read_sql("SELECT sk_operador, nk_id_operador, fecha_inicio_vigencia, fecha_fin_vigencia FROM dim_operador", engine_destino)
    
    df_hechos = df_hechos.merge(df_dim_op, on='nk_id_operador', how='left')
    
    # Filtramos la vigencia usando la fecha de creación del TAP
    mascara_op = (df_hechos['fecha_comparacion'] >= df_hechos['fecha_inicio_vigencia']) & (df_hechos['fecha_comparacion'] <= df_hechos['fecha_fin_vigencia'])
    df_hechos.loc[~mascara_op, 'sk_operador'] = -1
    
    # Llenamos nulos con el comodín y forzamos a entero
    df_hechos['sk_operador'] = df_hechos['sk_operador'].fillna(-1).astype(int)

    # 4. CARGA AL DATA WAREHOUSE
    print("-> 4. Insertando registros en fact_envio_tap...")

    # Mapeo exacto basado en el DDL
    columnas_finales = [
        'sk_fecha_creacion', 'sk_fecha_envio', 'sk_operador', 'estado_envio',
        'cantidad_cdrs_incluidos', 'monto_total_sdr', 'intento_transmision', 'cantidad_envios'
    ]
    df_final = df_hechos[columnas_finales]

    df_final.to_sql(name='fact_envio_tap', con=engine_destino, if_exists='append', index=False)

    print(f"¡Carga incremental finalizada! Se insertaron {len(df_final)} registros de TAP.\n")

if __name__ == '__main__':
    if probar_conexiones():
        diferencial_fact_envio_tap()