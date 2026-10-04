"""Carga inicial de dim_tasa_cambio; usa la misma limpieza que el diferencial."""
from db_config import engine_origen, engine_destino
from control_cargas import registrar_carga
from etl_catalogos import extraer_tasas, cargar_catalogo_inicial

@registrar_carga("dim_tasa_cambio", "INICIAL")
def cargar_dim_tasa_cambio():
    filas = extraer_tasas(engine_origen)
    return cargar_catalogo_inicial(engine_destino, "dim_tasa_cambio", filas)

if __name__ == "__main__":
    cargar_dim_tasa_cambio()
