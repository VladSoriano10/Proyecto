"""Carga inicial de dim_tarifa; usa la misma limpieza que el diferencial."""
from db_config import engine_origen, engine_destino
from control_cargas import registrar_carga
from etl_catalogos import extraer_tarifas, cargar_catalogo_inicial

@registrar_carga("dim_tarifa", "INICIAL")
def cargar_dim_tarifa():
    filas = extraer_tarifas(engine_origen)
    return cargar_catalogo_inicial(engine_destino, "dim_tarifa", filas)

if __name__ == "__main__":
    cargar_dim_tarifa()
