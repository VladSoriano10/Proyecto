"""Tarifas históricas y cambios de costo, servicio, moneda y vigencia."""

from datetime import date, timedelta
from sqlalchemy import text
from db_config import engine_destino, engine_origen, probar_conexiones
from etl_diferencial_utils import FIN_FECHA, cadena, fecha, decimal, leer, sincronizar_catalogo


def diferencial_dim_tarifa(fecha_corte=None):
    corte = fecha(fecha_corte) if fecha_corte is not None else date.today()
    with engine_origen.connect() as origen:
        filas = leer(origen, """SELECT id_tarifa AS nk_id_tarifa, tipo_trafico,
            costo_unidad, moneda, fecha_inicio_vigencia, fecha_fin_vigencia FROM tarifas""")
    servicios = {"GPRS": "GPRS - DATOS MÓVILES", "PORTAL": "PORTAL - VOZ", "CAMEL": "CAMEL - EVENTOS"}
    for fila in filas:
        fila["nk_id_tarifa"] = int(fila["nk_id_tarifa"])
        servicio = cadena(fila["tipo_trafico"], "DESCONOCIDO")
        fila["tipo_trafico"] = servicios.get(servicio, servicio)
        fila["costo_unidad"] = decimal(fila["costo_unidad"], 4)
        fila["moneda"] = cadena(fila["moneda"], "USD")
        fila["fecha_inicio_vigencia"] = fecha(fila["fecha_inicio_vigencia"])
        fila["fecha_fin_vigencia"] = fecha(fila["fecha_fin_vigencia"]) if fila["fecha_fin_vigencia"] else FIN_FECHA
    with engine_destino.begin() as destino:
        destino.execute(text("LOCK TABLE dim_tarifa IN SHARE ROW EXCLUSIVE MODE"))
        destino.execute(text("""INSERT INTO dim_tarifa VALUES
            (-1,-1,'DESCONOCIDO',0,'N/A','1900-01-01','2999-12-31')
            ON CONFLICT (sk_tarifa) DO NOTHING"""))
        resumen = sincronizar_catalogo(destino, "dim_tarifa", "sk_tarifa", "nk_id_tarifa", filas,
            ["tipo_trafico", "costo_unidad", "moneda"], "fecha_inicio_vigencia",
            "fecha_fin_vigencia", corte, timedelta(days=1))
    print(f"dim_tarifa: {resumen}")
    return resumen


if __name__ == "__main__":
    if probar_conexiones():
        diferencial_dim_tarifa()
