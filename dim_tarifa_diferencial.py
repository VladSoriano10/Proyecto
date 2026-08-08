from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def diferencial_dim_tarifa():
    print("\n--- Iniciando Carga INCREMENTAL (SCD Tipo 2) para dim_tarifa ---")

    # Fechas de control
    fecha_hoy = datetime.now().date()
    fecha_ayer = fecha_hoy - timedelta(days=1)
    fecha_fin_tiempos = pd.to_datetime('2999-12-31').date()


    # EXTRACCIÓN 
    print("-> 1. Extrayendo datos actuales del origen y del Data Warehouse...")
    
    # A. Datos de hoy en el origen 
    query_origen = """
        SELECT 
            id_tarifa AS nk_id_tarifa,
            tipo_trafico,
            costo_unidad,
            moneda
        FROM tarifas;
    """
    df_origen = pd.read_sql(query_origen, con=engine_origen)

    # Transformaciones de negocio (IDÉNTICAS a la carga inicial)
    mapeo_servicios = {
        'GPRS': 'GPRS - DATOS MÓVILES',
        'PORTAL': 'PORTAL - VOZ',
        'CAMEL': 'CAMEL - EVENTOS'
    }
    df_origen['tipo_trafico'] = df_origen['tipo_trafico'].str.strip().str.upper().replace(mapeo_servicios)
    df_origen['moneda'] = df_origen['moneda'].fillna('USD').str.strip().str.upper()
    
    # ¡CAST! Aseguramos tipos de datos estrictos
    df_origen['nk_id_tarifa'] = df_origen['nk_id_tarifa'].astype(int)
    df_origen['costo_unidad'] = df_origen['costo_unidad'].astype(float)

    # Registros ACTIVOS en el destino (Data Warehouse)
    query_destino = """
        SELECT 
            nk_id_tarifa, 
            costo_unidad AS costo_unidad_dw,
            tipo_trafico AS tipo_trafico_dw
        FROM dim_tarifa 
        WHERE fecha_fin_vigencia = '2999-12-31' 
        AND sk_tarifa != -1;
    """
    df_destino = pd.read_sql(query_destino, con=engine_destino)

    # ¡CAST! Forzamos tipos si el DW tiene datos
    if not df_destino.empty:
        df_destino['nk_id_tarifa'] = df_destino['nk_id_tarifa'].astype(int)
        df_destino['costo_unidad_dw'] = df_destino['costo_unidad_dw'].astype(float)
        df_destino['tipo_trafico_dw'] = df_destino['tipo_trafico_dw'].str.strip().str.upper()

    # 2. TRANSFORMACIÓN (El motor del SCD Tipo 2)
    print("-> 2. Detectando tarifas nuevas y cambios de precio...")
    
    # CRUZAMOS LAS TABLAS 
    df_merge = pd.merge(
        df_origen, 
        df_destino, 
        on='nk_id_tarifa', 
        how='left'
    )

    # REGLA 1: Tarifas totalmente nuevas 
    df_nuevos = df_merge[df_merge['costo_unidad_dw'].isna()].copy()
    
    # REGLA 2: Tarifas modificadas (El costo o el tipo de tráfico cambió)
    # Redondeamos a 4 decimales para eliminar falsos positivos de precisión flotante
    df_cambios = df_merge[
        (df_merge['costo_unidad_dw'].notna()) & 
        (
            (df_merge['costo_unidad'].round(4) != df_merge['costo_unidad_dw'].round(4)) |
            (df_merge['tipo_trafico'] != df_merge['tipo_trafico_dw'])
        )
    ].copy()

    print(f"   - Se detectaron {len(df_nuevos)} tarifas nuevas.")
    print(f"   - Se detectaron {len(df_cambios)} tarifas con cambio de precio/servicio.")

    if len(df_nuevos) == 0 and len(df_cambios) == 0:
        print("-> 3. No hay cambios para procesar. El DW está actualizado.\n")
        return

    #  CARGA 
    with engine_destino.begin() as conn:
        
        # ---  Cerrar los registros viejos (UPDATE) ---
        if not df_cambios.empty:
            print("-> 3A. Cerrando historial antiguo de las tarifas modificadas...")
            for index, row in df_cambios.iterrows():
                update_sql = text("""
                    UPDATE dim_tarifa 
                    SET fecha_fin_vigencia = :fecha_cierre 
                    WHERE nk_id_tarifa = :nk_id 
                    AND fecha_fin_vigencia = '2999-12-31'
                """)
                conn.execute(update_sql, {
                    "fecha_cierre": fecha_ayer, 
                    "nk_id": int(row['nk_id_tarifa'])
                })

        # --- Insertar lo nuevo  ---
        print("-> 3B. Insertando nuevas tarifas y el nuevo historial de precios...")
        
        df_a_insertar = pd.concat([df_nuevos, df_cambios]).copy()
        
        # Inyectamos las fechas generadas
        df_a_insertar['fecha_inicio_vigencia'] = fecha_hoy
        df_a_insertar['fecha_fin_vigencia'] = fecha_fin_tiempos

        # Mapeo exacto de las columnas de la BD
        columnas_finales = [
            'nk_id_tarifa', 'tipo_trafico', 'costo_unidad', 'moneda', 
            'fecha_inicio_vigencia', 'fecha_fin_vigencia'
        ]
        df_final = df_a_insertar[columnas_finales]

        df_final.to_sql(
            name='dim_tarifa', 
            con=conn, 
            if_exists='append', 
            index=False
        )

    print("¡Carga incremental finalizada con éxito! El historial de precios (SCD Tipo 2) se ha preservado.\n")

if __name__ == '__main__':
    if probar_conexiones():
        diferencial_dim_tarifa()