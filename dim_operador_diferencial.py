from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def diferencial_dim_operador():
    print("\n--- Iniciando Carga INCREMENTAL (SCD Tipo 2) para dim_operador ---")

    # Fechas de control
    fecha_hoy = datetime.now().date()
    fecha_ayer = fecha_hoy - timedelta(days=1)
    fecha_fin_tiempos = pd.to_datetime('2999-12-31').date()

    # 1. EXTRACCIÓN 
    print("-> 1. Extrayendo datos actuales del origen y del Data Warehouse...")
    
    # A. Datos de hoy en el origen 
    query_origen = """
        SELECT 
            o.id_operador AS nk_id_operador,
            COALESCE(o.nombre_operador, 'OPERADOR DESCONOCIDO') AS nombre_operador,
            COALESCE(o.status, 'DESCONOCIDO') AS status,
            COALESCE(o.id_pais, 'N/D') AS nk_id_pais,
            COALESCE(p.nombre_pais, 'PAÍS DESCONOCIDO') AS nombre_pais,
            COALESCE(p.prefijo_telefonico, '000') AS prefijo_telefonico
        FROM operadores o
        LEFT JOIN pais p ON o.id_pais = p.id_pais;
    """
    df_origen = pd.read_sql(query_origen, con=engine_origen)
    # Estandarización rápida
    for col in df_origen.columns:
        if df_origen[col].dtype == 'object':
            df_origen[col] = df_origen[col].str.strip().str.upper()

    #  Registros ACTIVOS en el destino (Data Warehouse)
    query_destino = """
        SELECT 
            nk_id_operador, 
            status AS status_dw
        FROM dim_operador 
        WHERE fecha_fin_vigencia = '2999-12-31' 
        AND sk_operador != -1;
    """
    df_destino = pd.read_sql(query_destino, con=engine_destino)

    # TRANSFORMACIÓN ( SCD Tipo 2)
    print("-> 2. Detectando operadores nuevos y cambios de estado...")
    
    # Cruzamos origen con destino para comparar
    df_merge = pd.merge(
        df_origen, 
        df_destino, 
        on='nk_id_operador', 
        how='left'
    )

    # REGLA 1: Registros totalmente nuevos (No existen en el DW)
    df_nuevos = df_merge[df_merge['status_dw'].isna()].copy()
    
    # REGLA 2: Registros modificados (Existen, pero su status cambió)
    # Ejemplo: En el DW estaba 'ACTIVO' y hoy en el origen viene 'INACTIVO'
    df_cambios = df_merge[
        (df_merge['status_dw'].notna()) & 
        (df_merge['status'] != df_merge['status_dw'])
    ].copy()

    print(f"   - Se detectaron {len(df_nuevos)} operadores nuevos.")
    print(f"   - Se detectaron {len(df_cambios)} operadores con cambio de estado.")

    if len(df_nuevos) == 0 and len(df_cambios) == 0:
        print("-> 3. No hay cambios para procesar. El DW está actualizado.\n")
        return


    # 3. CARGA 
    with engine_destino.begin() as conn:
        
        # --- Cerrar los registros viejos (UPDATE) ---
        if not df_cambios.empty:
            print("-> 3A. Cerrando historial antiguo de los operadores modificados...")
            for index, row in df_cambios.iterrows():
                # Cerramos el registro anterior poniéndole fecha de caducidad (ayer)
                update_sql = text("""
                    UPDATE dim_operador 
                    SET fecha_fin_vigencia = :fecha_cierre 
                    WHERE nk_id_operador = :nk_id 
                    AND fecha_fin_vigencia = '2999-12-31'
                """)
                conn.execute(update_sql, {
                    "fecha_cierre": fecha_ayer, 
                    "nk_id": row['nk_id_operador']
                })

        # ---  Insertar lo nuevo  ---
        print("-> 3B. Insertando registros nuevos y las nuevas versiones históricas...")
        
        # Unimos los nuevos operadores con las "nuevas versiones" de los modificados
        df_a_insertar = pd.concat([df_nuevos, df_cambios]).copy()
        
        # Les asignamos las fechas de vigencia
        df_a_insertar['fecha_inicio_vigencia'] = fecha_hoy
        df_a_insertar['fecha_fin_vigencia'] = fecha_fin_tiempos

        # Seleccionamos solo las columnas de la tabla final
        columnas_finales = [
            'nk_id_operador', 'nombre_operador', 'status', 
            'nk_id_pais', 'nombre_pais', 'prefijo_telefonico', 
            'fecha_inicio_vigencia', 'fecha_fin_vigencia'
        ]
        df_final = df_a_insertar[columnas_finales]

        # Inserción masiva
        df_final.to_sql(
            name='dim_operador', 
            con=conn, # Usamos la misma conexión de la transacción
            if_exists='append', 
            index=False
        )

    print("¡Carga incremental finalizada con éxito! El historial (SCD Tipo 2) se ha preservado.\n")

if __name__ == '__main__':
    if probar_conexiones():
        diferencial_dim_operador()