"""Tarifas históricas y cambios de costo, servicio, moneda y vigencia."""

from datetime import date, timedelta
from sqlalchemy import text
from control_cargas import registrar_carga, transaccion_destino, ahora_negocio
from etl_catalogos import extraer_tarifas
from db_config import engine_destino, engine_origen, probar_conexiones
from etl_comun import FIN_FECHA, cadena, fecha, decimal, leer, sincronizar_catalogo


@registrar_carga("dim_tarifa", "DIFERENCIAL")
def diferencial_dim_tarifa(fecha_corte=None):
    corte = fecha(fecha_corte) if fecha_corte is not None else ahora_negocio().date()
    filas = extraer_tarifas(engine_origen)
    with transaccion_destino(engine_destino) as destino:
        destino.execute(text("LOCK TABLE dim_tarifa IN SHARE ROW EXCLUSIVE MODE"))
        comodin = destino.execute(text("""INSERT INTO dim_tarifa VALUES
            (-1,-1,'DESCONOCIDO',0,'N/A','1900-01-01','2999-12-31')
            ON CONFLICT (sk_tarifa) DO NOTHING""")).rowcount
        resumen = sincronizar_catalogo(destino, "dim_tarifa", "sk_tarifa", "nk_id_tarifa", filas,
            ["tipo_trafico", "costo_unidad", "moneda"], "fecha_inicio_vigencia",
            "fecha_fin_vigencia", corte, timedelta(days=1))
    resumen.update(origen=len(filas), comodines_insertados=comodin,
                   filas_insertadas=resumen["insertadas"] + resumen["versiones_nuevas"] + comodin,
                   filas_actualizadas=resumen["actualizadas"], filas_eliminadas=0)
    print(f"dim_tarifa: {resumen}")
    return resumen


if __name__ == "__main__":
    if probar_conexiones():
        diferencial_dim_tarifa()

