"""Carga inicial de dim_operador; usa la misma limpieza que el diferencial."""
from db_config import engine_origen, engine_destino
from control_cargas import registrar_carga
from etl_catalogos import extraer_operadores, cargar_catalogo_inicial

@registrar_carga("dim_operador", "INICIAL")
def cargar_dim_operador():
    filas = extraer_operadores(engine_origen)
    return cargar_catalogo_inicial(engine_destino, "dim_operador", filas)

if __name__ == "__main__":
    cargar_dim_operador()
