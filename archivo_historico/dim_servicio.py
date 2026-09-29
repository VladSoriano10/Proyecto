import pandas as pd

from db_config import engine_destino, probar_conexiones


def cargar_dim_servicio():
    print("\n--- Iniciando proceso ETL para dim_servicio ---")

    # EXTRACCIÓN Y TRANSFORMACIÓN SIMULTÁNEA

    print("-> Generando registros base para dim_servicio...")

    # Traducimos las siglas técnicas a términos de Inteligencia de Negocios.
    datos_servicio = {
        "tipo_servicio": [
            "GPRS - Datos Móviles", 
            "PORTAL - Voz", 
            "CAMEL - Eventos",  
        ]
    }

    df_servicio = pd.DataFrame(datos_servicio)

    #CARGA (Load)
    print("-> Cargando datos a 'DWRoamingMovistar'...")

    df_servicio.to_sql(
        name="dim_servicio", con=engine_destino, if_exists="append", index=False
    )

    print(
        f"¡Carga exitosa! Se insertaron {len(df_servicio)} registros en dim_servicio.\n"
    )


if __name__ == "__main__":
    if probar_conexiones():
        cargar_dim_servicio()
    else:
        print("\n Proceso ETL abortado debido a problemas de conexión.")
