"""Carga inicial con las reglas temporales compartidas."""
from control_cargas import registrar_carga
from etl_hechos import procesar_fact_roaming

@registrar_carga("fact_roaming", "INICIAL")
def cargar_fact_roaming():
    return procesar_fact_roaming("INICIAL")

if __name__ == "__main__":
    cargar_fact_roaming()
