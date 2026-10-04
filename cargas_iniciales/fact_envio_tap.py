"""Carga inicial con las reglas temporales compartidas."""
from control_cargas import registrar_carga
from etl_hechos import procesar_fact_tap

@registrar_carga("fact_envio_tap", "INICIAL")
def cargar_fact_envio_tap():
    return procesar_fact_tap("INICIAL")

if __name__ == "__main__":
    cargar_fact_envio_tap()
