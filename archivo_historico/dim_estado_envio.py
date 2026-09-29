import pandas as pd

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_dim_estado_envio():
    print("\n--- Iniciando proceso ETL para dim_estado_envio ---")


    # EXTRACCIÓN

    print("-> Extrayendo datos de la base 'Roaming'...")

    # Utilizamos DISTINCT para no saturar la memoria y traer solo los valores únicos
    query_estados = "SELECT DISTINCT estado_envio FROM byte_envio_tap_log;"
    df_estados = pd.read_sql(query_estados, con=engine_origen)

    # 2. TRANSFORMACIÓN 
    print("-> Aplicando reglas de limpieza y traducción comercial...")

    # Control de nulos y estandarización a mayúsculas
    df_estados["estado_envio"] = df_estados["estado_envio"].fillna("SIN ESTADO")
    df_estados["estado_envio"] = df_estados["estado_envio"].str.strip().str.upper()

    # Diccionario de Reemplazo
    mapeo_estados = {
        "PEN": "PENDIENTE DE ENVÍO",
        "ENV": "ENVIADO EXITOSAMENTE",
        "ERR": "ERROR DE TRANSMISIÓN",
        "RECH": "RECHAZADO POR SYNIVERSE",
    }

    # Aplicar el diccionario a los valores de la columna
    df_estados["estado_envio"] = df_estados["estado_envio"].replace(mapeo_estados)

    # Medida de seguridad si la tabla origen no tiene registros
    if df_estados.empty:
        df_estados = pd.DataFrame({"estado_envio": ["SIN ESTADO"]})


    # CARGA
    print("-> Cargando datos limpios a 'DWRoamingMovistar'...")

    df_estados.to_sql(
        name="dim_estado_envio", con=engine_destino, if_exists="append", index=False
    )

    print(
        f"¡Carga exitosa! Se insertaron {len(df_estados)} registros en dim_estado_envio.\n"
    )


if __name__ == "__main__":
    if probar_conexiones():
        cargar_dim_estado_envio()
    else:
        print("\n Proceso ETL abortado debido a problemas de conexión.")
