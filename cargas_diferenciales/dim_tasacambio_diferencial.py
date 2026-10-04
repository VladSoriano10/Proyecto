"""Sincroniza TODO el catálogo de tasas y conserva la precisión temporal."""

from datetime import datetime, timedelta
from sqlalchemy import text
from control_cargas import registrar_carga, transaccion_destino, ahora_negocio
from etl_catalogos import extraer_tasas
from db_config import engine_destino, engine_origen, probar_conexiones
from etl_comun import FIN_INSTANTE, cadena, instante, decimal, leer, sincronizar_catalogo


@registrar_carga("dim_tasa_cambio", "DIFERENCIAL")
def diferencial_dim_tasa_cambio(momento_corte=None):
    corte = instante(momento_corte) if momento_corte is not None else ahora_negocio()
    filas = extraer_tasas(engine_origen)
    with transaccion_destino(engine_destino) as destino:
        destino.execute(text("LOCK TABLE dim_tasa_cambio IN SHARE ROW EXCLUSIVE MODE"))
        comodin = destino.execute(text("""INSERT INTO dim_tasa_cambio VALUES
            (-1,-1,'N/A','N/A',1,'1900-01-01','2999-12-31')
            ON CONFLICT (sk_tasa) DO NOTHING""")).rowcount
        resumen = sincronizar_catalogo(destino, "dim_tasa_cambio", "sk_tasa", "nk_id_tasa", filas,
            ["moneda_origen", "moneda_destino", "factor_cambio"],
            "fecha_desde", "fecha_hasta", corte, timedelta(microseconds=1))
    resumen.update(origen=len(filas), comodines_insertados=comodin,
                   filas_insertadas=resumen["insertadas"] + resumen["versiones_nuevas"] + comodin,
                   filas_actualizadas=resumen["actualizadas"], filas_eliminadas=0)
    print(f"dim_tasa_cambio: {resumen}")
    return resumen


if __name__ == "__main__":
    if probar_conexiones():
        diferencial_dim_tasa_cambio()

