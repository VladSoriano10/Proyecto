"""Sincroniza TODO el catálogo de tasas y conserva la precisión temporal."""

from datetime import datetime, timedelta
from sqlalchemy import text
from db_config import engine_destino, engine_origen, probar_conexiones
from .etl_diferencial_utils import FIN_INSTANTE, cadena, instante, decimal, leer, sincronizar_catalogo


def diferencial_dim_tasa_cambio(momento_corte=None):
    corte = instante(momento_corte) if momento_corte is not None else datetime.now()
    with engine_origen.connect() as origen:
        filas = leer(origen, """SELECT id_tasa AS nk_id_tasa, moneda_origen,
            moneda_destino, factor_cambio, fecha_desde, fecha_hasta FROM tasa_de_cambio""")
    grupos = {}
    for fila in filas:
        fila["nk_id_tasa"] = int(fila["nk_id_tasa"])
        fila["moneda_origen"] = cadena(fila["moneda_origen"], "N/D")
        fila["moneda_destino"] = cadena(fila["moneda_destino"], "USD")
        fila["factor_cambio"] = decimal(fila["factor_cambio"], 6)
        fila["fecha_desde"] = instante(fila["fecha_desde"])
        fila["fecha_hasta"] = instante(fila["fecha_hasta"]) if fila["fecha_hasta"] else FIN_INSTANTE
        grupos.setdefault((fila["moneda_origen"], fila["moneda_destino"]), []).append(fila)
    # Una tasa nueva del mismo par sustituye a la anterior desde su fecha de
    # vigencia, aunque su id_tasa sea diferente. Se conserva un cierre explícito
    # anterior si existe; no se rellenan huecos que el origen no justifica.
    for par, tasas in grupos.items():
        tasas.sort(key=lambda fila: fila["fecha_desde"])
        for anterior, siguiente in zip(tasas, tasas[1:]):
            if anterior["fecha_desde"] == siguiente["fecha_desde"]:
                raise ValueError(f"Dos tasas de {par} empiezan en el mismo instante; resuelva la ambigüedad.")
            anterior["fecha_hasta"] = min(anterior["fecha_hasta"], siguiente["fecha_desde"] - timedelta(microseconds=1))
    with engine_destino.begin() as destino:
        destino.execute(text("LOCK TABLE dim_tasa_cambio IN SHARE ROW EXCLUSIVE MODE"))
        destino.execute(text("""INSERT INTO dim_tasa_cambio VALUES
            (-1,-1,'N/A','N/A',1,'1900-01-01','2999-12-31')
            ON CONFLICT (sk_tasa) DO NOTHING"""))
        resumen = sincronizar_catalogo(destino, "dim_tasa_cambio", "sk_tasa", "nk_id_tasa", filas,
            ["moneda_origen", "moneda_destino", "factor_cambio"],
            "fecha_desde", "fecha_hasta", corte, timedelta(microseconds=1))
    print(f"dim_tasa_cambio: {resumen}")
    return resumen


if __name__ == "__main__":
    if probar_conexiones():
        diferencial_dim_tasa_cambio()
