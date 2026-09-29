"""Ejecutar después de la carga inicial o para refrescar el DW existente."""

from db_config import probar_conexiones
from cargas_diferenciales.dim_operador_diferencial import diferencial_dim_operador
from cargas_diferenciales.dim_tarifa_diferencial import diferencial_dim_tarifa
from cargas_diferenciales.dim_tasacambio_diferencial import diferencial_dim_tasa_cambio
from cargas_diferenciales.fact_roaming_diferencial import diferencial_fact_roaming
from cargas_diferenciales.fact_enviotap_diferencial import diferencial_fact_envio_tap


def main():
    if not probar_conexiones():
        raise SystemExit("No se pudo conectar. No se ejecutó la carga.")
    for funcion in [diferencial_dim_operador, diferencial_dim_tarifa,
                    diferencial_dim_tasa_cambio, diferencial_fact_roaming,
                    diferencial_fact_envio_tap]:
        funcion()
    print("Carga completada. Ya puede actualizar el dashboard.")


if __name__ == "__main__":
    main()
