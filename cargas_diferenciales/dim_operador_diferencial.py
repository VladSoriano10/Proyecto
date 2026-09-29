"""SCD tipo 2 de operador; resolución diaria, compatible con el DDL actual."""

from datetime import date, timedelta
from sqlalchemy import text
from db_config import engine_destino, engine_origen, probar_conexiones
from .etl_diferencial_utils import (FIN_FECHA, cadena, fecha, leer, insertar,
                                  actualizar, unicos, verificar_vigencias)


def diferencial_dim_operador(fecha_corte=None):
    corte = fecha(fecha_corte) if fecha_corte is not None else date.today()
    with engine_origen.connect() as origen:
        filas = leer(origen, """SELECT o.id_operador AS nk_id_operador,
            o.nombre_operador, o.status, o.id_pais AS nk_id_pais,
            p.nombre_pais, p.prefijo_telefonico
            FROM operadores o LEFT JOIN pais p ON p.id_pais=o.id_pais""")
    defaults = {"nk_id_operador": "", "nombre_operador": "OPERADOR DESCONOCIDO",
                "status": "DESCONOCIDO", "nk_id_pais": "N/D",
                "nombre_pais": "PAÍS DESCONOCIDO", "prefijo_telefonico": "000"}
    filas = [{col: cadena(f[col], defecto) for col, defecto in defaults.items()} for f in filas]
    atributos = [col for col in defaults if col != "nk_id_operador"]
    resumen = {"insertadas": 0, "versiones_nuevas": 0, "correcciones_mismo_dia": 0}
    with engine_destino.begin() as destino:
        destino.execute(text("LOCK TABLE dim_operador IN SHARE ROW EXCLUSIVE MODE"))
        destino.execute(text("""INSERT INTO dim_operador VALUES
            (-1,'N/A','DESCONOCIDO','N/A','N/A','DESCONOCIDO','N/A','1900-01-01','2999-12-31')
            ON CONFLICT (sk_operador) DO NOTHING"""))
        historiales = verificar_vigencias(leer(destino, "SELECT * FROM dim_operador WHERE sk_operador<>-1"),
            "nk_id_operador", "fecha_inicio_vigencia", "fecha_fin_vigencia")
        for llave, nueva in unicos(filas, "nk_id_operador").items():
            versiones = historiales.get(llave, [])
            if not versiones:
                # Misma convención que la carga inicial: historia previa desconocida.
                insertar(destino, "dim_operador", [dict(nueva,
                    fecha_inicio_vigencia=date(1900, 1, 1), fecha_fin_vigencia=FIN_FECHA)])
                resumen["insertadas"] += 1
                continue
            ultima = versiones[-1]
            if corte < ultima["fecha_inicio_vigencia"]:
                raise ValueError(f"Fecha de corte anterior al historial del operador {llave}.")
            cambios = {col: nueva[col] for col in atributos if nueva[col] != ultima[col]}
            if not cambios:
                continue
            if ultima["fecha_inicio_vigencia"] == corte:
                actualizar(destino, "dim_operador", "sk_operador", ultima["sk_operador"], cambios)
                resumen["correcciones_mismo_dia"] += 1
            else:
                if ultima["fecha_fin_vigencia"] >= corte:
                    actualizar(destino, "dim_operador", "sk_operador", ultima["sk_operador"],
                               {"fecha_fin_vigencia": corte - timedelta(days=1)})
                insertar(destino, "dim_operador", [dict(nueva,
                    fecha_inicio_vigencia=corte, fecha_fin_vigencia=FIN_FECHA)])
                resumen["versiones_nuevas"] += 1
        verificar_vigencias(leer(destino, "SELECT * FROM dim_operador WHERE sk_operador<>-1"),
            "nk_id_operador", "fecha_inicio_vigencia", "fecha_fin_vigencia")
    print(f"dim_operador: {resumen}")
    return resumen


if __name__ == "__main__":
    if probar_conexiones():
        diferencial_dim_operador()
