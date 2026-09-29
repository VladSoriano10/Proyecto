import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_dim_tarifa():
    print("\n--- Iniciando proceso ETL (Carga Inicial) para dim_tarifa ---")

    #EXTRACCIÓN
    print("-> Extrayendo datos de la base 'Roaming'...")
    
    query_extraccion = """
        SELECT 
            id_tarifa AS nk_id_tarifa,
            tipo_trafico,
            costo_unidad,
            moneda,
            fecha_inicio_vigencia,
            fecha_fin_vigencia
        FROM tarifas;
    """
    
    df_tarifa = pd.read_sql(query_extraccion, con=engine_origen)
    print(f"   Se extrajeron {len(df_tarifa)} registros origen.")

    # TRANSFORMACIÓN
    print("-> Aplicando limpieza, traducción comercial completa y preparación SCD2...")
    
    # Limpieza base de textos
    df_tarifa['tipo_trafico'] = df_tarifa['tipo_trafico'].fillna('N/A').str.strip().str.upper()
    df_tarifa['moneda'] = df_tarifa['moneda'].fillna('N/A').str.strip().str.upper()
    
    # iccionario de Traducción
    mapeo_trafico = {
        'GPRS': 'Datos Móviles',
        'PORTAL': 'Llamadas de Voz',
        'CAMEL': 'Servicios Inteligentes'
    }
    mapeo_moneda = {
        'EUR': 'Euros',
        'SDR': 'Derechos Especiales de Giro'
    }
    
    # Aplicamos los reemplazos
    df_tarifa['tipo_trafico'] = df_tarifa['tipo_trafico'].replace(mapeo_trafico)
    df_tarifa['moneda'] = df_tarifa['moneda'].replace(mapeo_moneda)
    
    # 3. Asegurar numéricos y manejo de fechas
    df_tarifa['costo_unidad'] = df_tarifa['costo_unidad'].fillna(0.0000)
    df_tarifa['fecha_inicio_vigencia'] = df_tarifa['fecha_inicio_vigencia'].fillna(pd.to_datetime('1900-01-01'))
    df_tarifa['fecha_fin_vigencia'] = df_tarifa['fecha_fin_vigencia'].fillna(pd.to_datetime('2999-12-31'))

    # LIMPIEZA PREVIA Y CARGA (Load)
    print("-> Limpiando registros anteriores y reseteando llaves (Idempotencia)...")
    
    # Ejecutamos el borrado seguro en PostgreSQL antes de insertar los nuevos datos
    with engine_destino.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dim_tarifa RESTART IDENTITY CASCADE;"))
    
    print("-> Cargando datos limpios a 'DWRoamingMovistar'...")
    
    df_tarifa.to_sql(
        name='dim_tarifa',
        con=engine_destino,
        if_exists='append',
        index=False
    )
    
    print(f"¡Carga exitosa! Se insertaron {len(df_tarifa)} registros en dim_tarifa.\n")

if __name__ == '__main__':
    if probar_conexiones():
        cargar_dim_tarifa()
    else:
        print("\n Proceso ETL abortado debido a problemas de conexión.")