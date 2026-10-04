"""SCD tipo 2 de operador; resolución diaria, compatible con el DDL actual."""

from datetime import date, timedelta
from sqlalchemy import text
from control_cargas import registrar_carga, transaccion_destino, ahora_negocio
from etl_catalogos import extraer_operadores
from db_config import engine_destino, engine_origen, probar_conexiones
from etl_comun import (FIN_FECHA, cadena, fecha, leer, insertar,
                                  actualizar, unicos, verificar_vigencias)


@registrar_carga("dim_operador", "DIFERENCIAL")
def diferencial_dim_operador(fecha_corte=None):
    corte = fecha(fecha_corte) if fecha_corte is not None else ahora_negocio().date()
    filas = extraer_operadores(engine_origen)
    atributos = [c for c in filas[0] if c not in ("nk_id_operador", "fecha_inicio_vigencia", "fecha_fin_vigencia")] if filas else []
    resumen = {"insertadas": 0, "versiones_nuevas": 0, "correcciones_mismo_dia": 0, "actualizadas": 0}
    with transaccion_destino(engine_destino) as destino:
        destino.execute(text("LOCK TABLE dim_operador IN SHARE ROW EXCLUSIVE MODE"))
        comodin = destino.execute(text("""INSERT INTO dim_operador VALUES
            (-1,'N/A','DESCONOCIDO','N/A','N/A','DESCONOCIDO','N/A','1900-01-01','2999-12-31')
            ON CONFLICT (sk_operador) DO NOTHING""")).rowcount
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
                resumen["actualizadas"] += 1
            else:
                if ultima["fecha_fin_vigencia"] >= corte:
                    actualizar(destino, "dim_operador", "sk_operador", ultima["sk_operador"],
                               {"fecha_fin_vigencia": corte - timedelta(days=1)})
                    resumen["actualizadas"] += 1
                insertar(destino, "dim_operador", [dict(nueva,
                    fecha_inicio_vigencia=corte, fecha_fin_vigencia=FIN_FECHA)])
                resumen["versiones_nuevas"] += 1
        verificar_vigencias(leer(destino, "SELECT * FROM dim_operador WHERE sk_operador<>-1"),
            "nk_id_operador", "fecha_inicio_vigencia", "fecha_fin_vigencia")
    resumen.update(origen=len(filas), comodines_insertados=comodin,
                   filas_insertadas=resumen["insertadas"] + resumen["versiones_nuevas"] + comodin,
                   filas_actualizadas=resumen["actualizadas"], filas_eliminadas=0)
    print(f"dim_operador: {resumen}")
    return resumen


if __name__ == "__main__":
    if probar_conexiones():
        diferencial_dim_operador()

