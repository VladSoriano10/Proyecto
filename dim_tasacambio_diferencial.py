from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def diferencial_dim_tasa_cambio():
    print("\n--- Iniciando Carga INCREMENTAL (SCD Tipo 2) para dim_tasa_cambio ---")

    # Fechas de control
    fecha_hoy = datetime.now().date()
    fecha_ayer = fecha_hoy - timedelta(days=1)
    fecha_fin_tiempos = pd.to_datetime('2999-12-31').date()

    # EXTRACCIÓN
    print("-> 1. Extrayendo datos actuales del origen y del Data Warehouse...")
    
    # Datos de hoy en el origen 
    query_origen = """
        SELECT DISTINCT ON (moneda_origen, moneda_destino)
            id_tasa AS nk_id_tasa,
            moneda_origen,
            moneda_destino,
            factor_cambio,
            fecha_desde,
            fecha_hasta
        FROM tasa_de_cambio
        ORDER BY moneda_origen, moneda_destino, fecha_desde DESC;
    """
    df_origen = pd.read_sql(query_origen, con=engine_origen)

    # Limpieza estándar y Cast
    df_origen['moneda_origen'] = df_origen['moneda_origen'].str.strip().str.upper()
    df_origen['moneda_destino'] = df_origen['moneda_destino'].str.strip().str.upper()
    df_origen['nk_id_tasa'] = df_origen['nk_id_tasa'].astype(int)
    df_origen['factor_cambio'] = df_origen['factor_cambio'].astype(float)

    # B. Registros ACTIVOS en el destino (Data Warehouse)
    query_destino = """
        SELECT 
            nk_id_tasa,
            factor_cambio AS factor_cambio_dw
        FROM dim_tasa_cambio 
        WHERE fecha_hasta = '2999-12-31' 
        AND sk_tasa != -1;
    """
    df_destino = pd.read_sql(query_destino, con=engine_destino)

    # Cast de Hierro Destino
    if not df_destino.empty:
        df_destino['nk_id_tasa'] = df_destino['nk_id_tasa'].astype(int)
        df_destino['factor_cambio_dw'] = df_destino['factor_cambio_dw'].astype(float)

    # TRANSFORMACIÓN (El motor del SCD Tipo 2)
    print("-> 2. Detectando nuevas monedas y fluctuaciones en la tasa de cambio...")
    
    df_merge = pd.merge(
        df_origen, 
        df_destino, 
        on='nk_id_tasa', 
        how='left'
    )

    # REGLA 1: Tasas de cambio totalmente nuevas
    df_nuevos = df_merge[df_merge['factor_cambio_dw'].isna()].copy()
    
    # REGLA 2: Tasas que fluctuaron (El factor de cambio cambió)
    # Redondeamos a 6 decimales por la alta sensibilidad financiera
    df_cambios = df_merge[
        (df_merge['factor_cambio_dw'].notna()) & 
        (df_merge['factor_cambio'].round(6) != df_merge['factor_cambio_dw'].round(6))
    ].copy()

    print(f"   - Se detectaron {len(df_nuevos)} nuevos pares de monedas.")
    print(f"   - Se detectaron {len(df_cambios)} tasas con fluctuación de valor.")

    if len(df_nuevos) == 0 and len(df_cambios) == 0:
        print("-> 3. No hay cambios para procesar. El DW está actualizado.\n")
        return

    # 3. CARGA 
    with engine_destino.begin() as conn:
        
        # --- Cerrar el historial viejo (UPDATE) ---
        if not df_cambios.empty:
            print("-> 3A. Cerrando la vigencia de las tasas de cambio anteriores...")
            for index, row in df_cambios.iterrows():
                update_sql = text("""
                    UPDATE dim_tasa_cambio 
                    SET fecha_hasta = :fecha_cierre 
                    WHERE nk_id_tasa = :nk_id 
                    AND fecha_hasta = '2999-12-31'
                """)
                conn.execute(update_sql, {
                    "fecha_cierre": fecha_ayer, 
                    "nk_id": int(row['nk_id_tasa'])
                })

        # ---  Insertar las nuevas tasas del día (INSERT) ---
        print("-> 3B. Insertando las tasas de cambio vigentes para hoy...")
        
        df_a_insertar = pd.concat([df_nuevos, df_cambios]).copy()
        
        # Inyectamos fechas de vigencia
        df_a_insertar['fecha_desde'] = fecha_hoy
        df_a_insertar['fecha_hasta'] = fecha_fin_tiempos

        # Mapeo de las columnas
        columnas_finales = [
            'nk_id_tasa', 'moneda_origen', 'moneda_destino', 'factor_cambio', 
            'fecha_desde', 'fecha_hasta'
        ]
        df_final = df_a_insertar[columnas_finales]

        df_final.to_sql(
            name='dim_tasa_cambio', 
            con=conn, 
            if_exists='append', 
            index=False
        )

    print("¡Carga incremental finalizada con éxito! El histórico financiero se ha preservado.\n")

if __name__ == '__main__':
    if probar_conexiones():
        diferencial_dim_tasa_cambio()