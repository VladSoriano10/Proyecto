import pandas as pd
from sqlalchemy import text

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_dim_operador():
    print("\n--- Iniciando proceso ETL (Carga Inicial) para dim_operador ---")

    
    # EXTRACCIÓN    
    print("-> 1. Extrayendo operadores y países de la base 'Roaming'...")

    # Extraemos la data ya cruzada desde el motor transaccional
    query = """
        SELECT 
            o.id_operador AS nk_id_operador,
            o.nombre_operador,
            o.status,
            o.id_pais AS nk_id_pais,
            p.nombre_pais,
            p.prefijo_telefonico
        FROM operadores o
        LEFT JOIN pais p ON o.id_pais = p.id_pais;
    """
    df_operador = pd.read_sql(query, con=engine_origen)
    print(f"   Se extrajeron {len(df_operador)} operadores del origen.")


    # TRANSFORMACIÓN Y LIMPIEZA

    print("-> 2. Estandarizando textos y aplicando SCD Tipo 2 (Forward-Looking)...")

    # --- Limpieza de Textos contra Nulos ---
    df_operador["nk_id_operador"] = (
        df_operador["nk_id_operador"].str.strip().str.upper()
    )
    df_operador["nombre_operador"] = (
        df_operador["nombre_operador"]
        .fillna("OPERADOR DESCONOCIDO")
        .str.strip()
        .str.upper()
    )
    df_operador["status"] = (
        df_operador["status"].fillna("DESCONOCIDO").str.strip().str.upper()
    )

    df_operador["nk_id_pais"] = (
        df_operador["nk_id_pais"].fillna("N/D").str.strip().str.upper()
    )
    df_operador["nombre_pais"] = (
        df_operador["nombre_pais"].fillna("PAÍS DESCONOCIDO").str.strip().str.upper()
    )
    df_operador["prefijo_telefonico"] = (
        df_operador["prefijo_telefonico"].fillna("000").str.strip()
    )

    # --- SCD Tipo 2 (Inyección de fechas artificiales) ---
    # Como el origen no tiene historia, iniciamos el contador histórico desde el "inicio de los tiempos"
    # y lo dejamos abierto hasta el año 2999.
    df_operador["fecha_inicio_vigencia"] = pd.to_datetime("1900-01-01").date()
    df_operador["fecha_fin_vigencia"] = pd.to_datetime("2999-12-31").date()

    # Mapeo de las columnas para alinear con el nuevo DDL
    columnas_finales = [
        "nk_id_operador",
        "nombre_operador",
        "status",
        "nk_id_pais",
        "nombre_pais",
        "prefijo_telefonico",
        "fecha_inicio_vigencia",
        "fecha_fin_vigencia",
    ]
    df_final = df_operador[columnas_finales]

    # CARGA PREVIA Y EJECUCIÓN (Idempotencia)

    print("-> 3. Limpiando tabla dim_operador (CASCADE)...")
    with engine_destino.begin() as conn:
        conn.execute(text("TRUNCATE TABLE dim_operador RESTART IDENTITY CASCADE;"))

    print("-> 4. Cargando el catálogo maestro de operadores a 'DWRoamingMovistar'...")
    df_final.to_sql(
        name="dim_operador", con=engine_destino, if_exists="append", index=False
    )

    print(f"¡Carga exitosa! Se insertaron {len(df_final)} registros en dim_operador.\n")


if __name__ == "__main__":
    if probar_conexiones():
        cargar_dim_operador()
    else:
        print("\n Proceso ETL abortado debido a problemas de conexión.")
