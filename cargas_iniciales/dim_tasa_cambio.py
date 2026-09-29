import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_dim_tasa_cambio():
    print("\n--- Iniciando proceso ETL (Carga Inicial) para dim_tasa_cambio ---")


    # EXTRACCIÓN

    print("-> 1. Extrayendo el catálogo histórico de monedas de la base 'Roaming'...")
    
    query = """
        SELECT 
            id_tasa AS nk_id_tasa,
            moneda_origen,
            moneda_destino,
            factor_cambio,
            fecha_desde,
            fecha_hasta
        FROM tasa_de_cambio;
    """
    df_tasa = pd.read_sql(query, con=engine_origen)
    print(f"   Se extrajeron {len(df_tasa)} tasas de cambio del origen.")


    # TRANSFORMACIÓN Y LIMPIEZA

    print("-> 2. Estandarizando monedas y aplicando cierre histórico (SCD Tipo 2)...")

    # --- Limpieza de Monedas ---
    df_tasa['moneda_origen'] = df_tasa['moneda_origen'].fillna('N/D').str.strip().str.upper()
    
    # La base origen tiene 'USD' como default, pero nos aseguramos por si vienen nulos
    df_tasa['moneda_destino'] = df_tasa['moneda_destino'].fillna('USD').str.strip().str.upper()

    # --- Aseguramiento Matemático ---
    df_tasa['factor_cambio'] = df_tasa['factor_cambio'].astype(float)

    # --- SCD Tipo 2 (Reemplazo de la fecha_hasta nula) ---
    df_tasa['fecha_desde'] = pd.to_datetime(df_tasa['fecha_desde'])
    df_tasa['fecha_hasta'] = pd.to_datetime(df_tasa['fecha_hasta'])

    # El registro activo tendrá el 'fin de los tiempos' en lugar de NULL
    df_tasa['fecha_hasta'] = df_tasa['fecha_hasta'].fillna(pd.to_datetime('2999-12-31'))

    # Adaptación a formato DATE de PostgreSQL (eliminando horas/minutos si existieran)
    df_tasa['fecha_desde'] = df_tasa['fecha_desde'].dt.date
    df_tasa['fecha_hasta'] = df_tasa['fecha_hasta'].dt.date

    # Mapeo exacto
    columnas_finales = [
        'nk_id_tasa',
        'moneda_origen',
        'moneda_destino',
        'factor_cambio',
        'fecha_desde',
        'fecha_hasta'
    ]
    df_final = df_tasa[columnas_finales]

    # CARGA 
    print("-> 3. Limpiando tabla dim_tasa_cambio (CASCADE)...")
    with engine_destino.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dim_tasa_cambio RESTART IDENTITY CASCADE;"))
        
    print("-> 4. Cargando historial financiero a 'DWRoamingMovistar'...")
    df_final.to_sql(
        name='dim_tasa_cambio', 
        con=engine_destino, 
        if_exists='append', 
        index=False
    )
    # Insertar el registro comodín (-1) para el manejo de nulos en la Fact Table
    print("-> 5. Insertando registro comodín (-1)...")
    with engine_destino.begin() as conn:
        conn.execute(text("""
            INSERT INTO dim_tasa_cambio (
                sk_tasa, nk_id_tasa, moneda_origen, moneda_destino, factor_cambio, fecha_desde, fecha_hasta
            ) VALUES (
                -1, -1, 'N/A', 'N/A', 1.000000, '1900-01-01', '2999-12-31'
            ) ON CONFLICT (sk_tasa) DO NOTHING;
        """))
    print(f"¡Carga exitosa! Se insertaron {len(df_final)} tasas históricas en dim_tasa_cambio.\n")

if __name__ == '__main__':
    if probar_conexiones():
        cargar_dim_tasa_cambio()
    else:
        print("\n Proceso ETL abortado debido a problemas de conexión.")