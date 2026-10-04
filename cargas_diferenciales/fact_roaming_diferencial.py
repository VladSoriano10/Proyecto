"""Carga diferencial con las reglas temporales compartidas."""
from control_cargas import registrar_carga
from etl_hechos import procesar_fact_roaming

@registrar_carga("fact_roaming", "DIFERENCIAL")
def diferencial_fact_roaming():
    return procesar_fact_roaming("DIFERENCIAL")

if __name__ == "__main__":
    diferencial_fact_roaming()
