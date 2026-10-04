"""Carga diferencial con las reglas temporales compartidas."""
from control_cargas import registrar_carga
from etl_hechos import procesar_fact_tap

@registrar_carga("fact_envio_tap", "DIFERENCIAL")
def diferencial_fact_envio_tap():
    return procesar_fact_tap("DIFERENCIAL")

if __name__ == "__main__":
    diferencial_fact_envio_tap()
