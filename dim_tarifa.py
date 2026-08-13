import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_dim_tarifa():
    print("\n--- Iniciando proceso ETL (Carga Inicial) para dim_tarifa ---")

    # EXTRACCIÓN

    print("-> 1. Extrayendo datos de la tabla 'tarifas'...")
    query = """
        SELECT 
            id_tarifa AS nk_id_tarifa,
            tipo_trafico,
            costo_unidad,
            moneda,
            fecha_inicio_vigencia,
            fecha_fin_vigencia
        FROM tarifas;
    """
    df_tarifa = pd.read_sql(query, con=engine_origen)
    print(f"   Se extrajeron {len(df_tarifa)} tarifas del origen.")


    # TRANSFORMACIÓN

    print("-> 2. Aplicando estandarización y reglas SCD Tipo 2...")

    # ---  Absorción del Catálogo de Servicios ---
    # Traducimos el tráfico al lenguaje de negocio
    mapeo_servicios = {
        "GPRS": "GPRS - DATOS MÓVILES",
        "PORTAL": "PORTAL - VOZ",
        "CAMEL": "CAMEL - EVENTOS",
    }
    # Limpiamos espacios, pasamos a mayúsculas y aplicamos la traducción
    df_tarifa["tipo_trafico"] = (
        df_tarifa["tipo_trafico"].str.strip().str.upper().replace(mapeo_servicios)
    )

    # Limpiamos la moneda y protegemos contra nulos asumiendo 'USD' por defecto si viniera vacío
    df_tarifa["moneda"] = df_tarifa["moneda"].fillna("USD").str.strip().str.upper()

    # --- Aseguramiento de Tipos Numéricos ---
    df_tarifa["costo_unidad"] = df_tarifa["costo_unidad"].astype(float)

    # --- Aplicación de Fechas (SCD Tipo 2) ---
    # Convertimos a formato datetime
    df_tarifa["fecha_inicio_vigencia"] = pd.to_datetime(
        df_tarifa["fecha_inicio_vigencia"]
    )
    df_tarifa["fecha_fin_vigencia"] = pd.to_datetime(df_tarifa["fecha_fin_vigencia"])

    # Rellenamos los vacíos con la fecha 'fin de los tiempos'
    df_tarifa["fecha_fin_vigencia"] = df_tarifa["fecha_fin_vigencia"].fillna(
        pd.to_datetime("2999-12-31")
    )

    # Extraemos solo la porción de fecha (YYYY-MM-DD) para encajar con el tipo DATE de PostgreSQL
    df_tarifa["fecha_inicio_vigencia"] = df_tarifa["fecha_inicio_vigencia"].dt.date
    df_tarifa["fecha_fin_vigencia"] = df_tarifa["fecha_fin_vigencia"].dt.date

    # Mapeo de las columnas en el orden del DDL
    columnas_finales = [
        "nk_id_tarifa",
        "tipo_trafico",
        "costo_unidad",
        "moneda",
        "fecha_inicio_vigencia",
        "fecha_fin_vigencia",
    ]
    df_final = df_tarifa[columnas_finales]


    # CARGA (Idempotencia)

    print("-> 3. Limpiando tabla dim_tarifa...")
    with engine_destino.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dim_tarifa RESTART IDENTITY CASCADE;"))

    print("-> 4. Insertando nuevos registros en 'DWRoamingMovistar'...")
    df_final.to_sql(
        name="dim_tarifa", con=engine_destino, if_exists="append", index=False
    )

    # Insertar el registro comodín (-1) para el manejo de nulos en la Fact Table
    print("-> 5. Insertando registro comodín (-1)...")
    with engine_destino.begin() as conn:
        conn.execute(text("""
            INSERT INTO dim_tarifa (
                sk_tarifa, nk_id_tarifa, tipo_trafico, costo_unidad, 
                moneda, fecha_inicio_vigencia, fecha_fin_vigencia
            ) VALUES (
                -1, -1, 'N/A', 0.0, 
                'N/A', '1900-01-01', '2999-12-31'
            ) ON CONFLICT (sk_tarifa) DO NOTHING;
        """))
    print(
        f"¡Carga exitosa! Se insertaron {len(df_final)} tarifas en dim_tarifa.\n"
    )


if __name__ == "__main__":
    if probar_conexiones():
        cargar_dim_tarifa()
    else:
        print("\nProceso ETL abortado debido a problemas de conexión.")
