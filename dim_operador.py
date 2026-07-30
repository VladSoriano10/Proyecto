
import pandas as pd

from db_config import engine_destino, engine_origen, probar_conexiones


def cargar_dim_operador():
    print("\n--- Iniciando proceso ETL para dim_operador ---")


    # EXTRACCIÓN 

    print("-> Extrayendo datos de la base 'Roaming'...")

    query_extraccion = """
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

    df_operador = pd.read_sql(query_extraccion, con=engine_origen)
    print(f"   Se extrajeron {len(df_operador)} registros origen.")

    # 2. TRANSFORMACIÓN (Transform)
    print("-> Aplicando reglas de limpieza y transformación...")

    # Manejo de Nulos 
    df_operador["nombre_operador"] = df_operador["nombre_operador"].fillna(
        "Desconocido"
    )
    df_operador["status"] = df_operador["status"].fillna("INACTIVO")
    df_operador["nombre_pais"] = df_operador["nombre_pais"].fillna("Desconocido")
    df_operador["prefijo_telefonico"] = df_operador["prefijo_telefonico"].fillna("N/A")

    # Estandarización de Texto
    df_operador["nk_id_operador"] = (
        df_operador["nk_id_operador"].str.strip().str.upper()
    )
    df_operador["nk_id_pais"] = df_operador["nk_id_pais"].str.strip().str.upper()
    df_operador["status"] = df_operador["status"].str.strip().str.upper()

    # CARGA 
    print("-> Cargando datos limpios a 'DWRoamingMovistar'...")

    df_operador.to_sql(
        name="dim_operador", con=engine_destino, if_exists="append", index=False
    )

    print("¡Carga exitosa! Proceso ETL de dim_operador finalizado. \n")


if __name__ == "__main__":
    if probar_conexiones():
        cargar_dim_operador()
    else:
        print("\n Proceso ETL abortado debido a problemas de conexión.")
