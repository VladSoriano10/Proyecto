"""Funciones compartidas por los cinco diferenciales de Roaming.
Las facts se reconcilian por día porque no
almacenan la llave del registro de origen. El origen debe conservar TODO
el historial que corresponde al DW. No ejecutar contra una extracción parcial.
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from control_cargas import transaccion_destino, conteo_previo

FIN_FECHA = date(2999, 12, 31)
FIN_INSTANTE = datetime(2999, 12, 31)


def fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def instante(valor):
    if isinstance(valor, datetime):
        resultado = valor
    elif isinstance(valor, date):
        resultado = datetime.combine(valor, datetime.min.time())
    else:
        resultado = datetime.fromisoformat(str(valor))
    if resultado.tzinfo is not None:
        raise ValueError("El DDL usa TIMESTAMP sin zona; normalice la zona antes de cargar.")
    return resultado


def cadena(valor, defecto=""):
    resultado = "" if valor is None else str(valor).strip().upper()
    return resultado or defecto


def decimal(valor, posiciones):
    return Decimal(str(valor)).quantize(Decimal(1).scaleb(-posiciones), rounding=ROUND_HALF_UP)


def leer(conexion, consulta):
    return [dict(fila) for fila in conexion.execute(text(consulta)).mappings().all()]


def unicos(filas, columna):
    resultado = {}
    for fila in filas:
        llave = fila[columna]
        if llave is None or llave == "" or llave in resultado:
            raise ValueError(f"Llave natural vacía o repetida después de limpiar {columna}: {llave!r}")
        resultado[llave] = fila
    return resultado


def insertar(conexion, tabla, filas, columnas=None):
    """INSERT parametrizado en lotes; conserva Decimal, DATE y TIMESTAMP."""
    if not filas:
        return
    columnas = columnas or list(filas[0])
    for inicio in range(0, len(filas), 500):
        lote = filas[inicio:inicio + 500]
        parametros, valores = {}, []
        for i, fila in enumerate(lote):
            nombres = []
            for j, columna in enumerate(columnas):
                nombre = f"p{i}_{j}"
                parametros[nombre] = fila[columna]
                nombres.append(":" + nombre)
            valores.append("(" + ",".join(nombres) + ")")
        # Tabla y columnas son constantes internas del código, nunca datos externos.
        conexion.execute(text(
            f"INSERT INTO {tabla} ({','.join(columnas)}) VALUES {','.join(valores)}"
        ), parametros)


def actualizar(conexion, tabla, pk, identificador, cambios):
    if cambios:
        parametros = dict(cambios, _pk=identificador)
        asignaciones = ",".join(f"{columna}=:{columna}" for columna in cambios)
        conexion.execute(text(f"UPDATE {tabla} SET {asignaciones} WHERE {pk}=:_pk"), parametros)


def verificar_vigencias(filas, nk, inicio, fin):
    grupos = {}
    for fila in filas:
        if fila[nk] in (-1, "N/A"):
            continue
        grupos.setdefault(fila[nk], []).append(fila)
    for llave, versiones in grupos.items():
        versiones.sort(key=lambda fila: fila[inicio])
        anterior = None
        for fila in versiones:
            if fila[inicio] > fila[fin] or (anterior is not None and anterior >= fila[inicio]):
                raise ValueError(f"Vigencias inválidas o superpuestas para {nk}={llave!r}.")
            anterior = fila[fin]
    return grupos


def sincronizar_catalogo(conexion, tabla, pk, nk, filas, atributos,
                         inicio, fin, corte, paso):
    """SCD2 por llave del catálogo, respetando su vigencia de negocio.

Una modificación observada durante la vigencia abre una versión. Una
corrección de una fila ya vencida/futura actualiza esa versión, sin inventar
una tarifa/tasa activa hoy. La resolución temporal la fija el DDL.
"""
    modificadas = set()
    originales = leer(conexion, f"SELECT * FROM {tabla} WHERE {pk} <> -1")
    historial = verificar_vigencias(originales, nk, inicio, fin)
    resumen = {"insertadas": 0, "versiones_nuevas": 0, "actualizadas": 0}
    for llave, nueva in unicos(filas, nk).items():
        if nueva[inicio] > nueva[fin]:
            raise ValueError(f"Vigencia invertida en el origen: {tabla}, {llave}.")
        versiones = historial.get(llave, [])
        if not versiones:
            insertar(conexion, tabla, [nueva])
            resumen["insertadas"] += 1
            continue
        primera, ultima = versiones[0], versiones[-1]
        # Si existen varias versiones, no se permite recortar retroactivamente
        # la vigencia de negocio atravesando versiones ya registradas.
        if len(versiones) > 1 and (nueva[inicio] > primera[fin] or nueva[fin] < ultima[inicio]):
            raise ValueError(f"Cambio retroactivo de vigencia requiere revisión: {tabla}, {llave}.")
        if primera[inicio] != nueva[inicio]:
            actualizar(conexion, tabla, pk, primera[pk], {inicio: nueva[inicio]})
            modificadas.add(primera[pk])
            primera[inicio] = nueva[inicio]
        distintos = any(ultima[columna] != nueva[columna] for columna in atributos)
        # Las vigencias explícitas del origen siempre se respetan, incluso al cerrar.
        cambios = {fin: nueva[fin]} if ultima[fin] != nueva[fin] else {}
        if distintos and ultima[inicio] < corte <= nueva[fin]:
            actualizar(conexion, tabla, pk, ultima[pk], {fin: corte - paso})
            modificadas.add(ultima[pk])
            nueva_version = dict(nueva, **{inicio: corte})
            insertar(conexion, tabla, [nueva_version])
            resumen["versiones_nuevas"] += 1
        else:
            if distintos:
                cambios.update({columna: nueva[columna] for columna in atributos})
            if cambios:
                actualizar(conexion, tabla, pk, ultima[pk], cambios)
                modificadas.add(ultima[pk])
    verificar_vigencias(leer(conexion, f"SELECT * FROM {tabla} WHERE {pk} <> -1"), nk, inicio, fin)
    resumen["actualizadas"] = len(modificadas)
    return resumen


def reconciliar_fact(engine_origen, engine_destino, tabla, consulta_origen,
                     ddl_temporal, consulta_candidatos, columnas, columna_fecha,
                     fechas_fk, medidas, modo="DIFERENCIAL"):
    """Compara todas las columnas y su multiplicidad con EXCEPT ALL.

Solo reemplaza los días diferentes. Conserva repeticiones legítimas del
origen. DELETE e INSERT pertenecen a la misma transacción: ante cualquier
error el DW conserva sus filas previas. id_hecho cambia en días reemplazados.
    """
    with transaccion_destino(engine_destino) as destino:
        destino.execute(text(f"LOCK TABLE {tabla} IN SHARE ROW EXCLUSIVE MODE"))
        dimensiones = "dim_operador, dim_tiempo"
        if tabla == "fact_roaming":
            dimensiones += ", dim_tarifa, dim_tasa_cambio"
        destino.execute(text(f"LOCK TABLE {dimensiones} IN SHARE MODE"))
        destino.execute(text("DROP TABLE IF EXISTS pg_temp._etl_fechas, pg_temp._etl_candidatos, pg_temp._etl_origen"))
        destino.execute(text(f"CREATE TEMP TABLE _etl_origen ({ddl_temporal}) ON COMMIT DROP"))
        cantidad = 0
        with engine_origen.connect() as origen:
            resultado = origen.execute(text(consulta_origen)).mappings()
            while True:
                lote = [dict(fila) for fila in resultado.fetchmany(2000)]
                if not lote:
                    break
                insertar(destino, "_etl_origen", lote)
                cantidad += len(lote)
        anteriores = conteo_previo(tabla, int(destino.execute(text(f"SELECT count(*) FROM {tabla}")).scalar()))
        if cantidad == 0 and anteriores:
            raise ValueError("Origen vacío frente a una fact poblada. No se modificó el DW; revise la conexión.")
        destino.execute(text("ANALYZE _etl_origen"))
        destino.execute(text("CREATE TEMP TABLE _etl_candidatos ON COMMIT DROP AS " + consulta_candidatos))
        if destino.execute(text("SELECT count(*) FROM _etl_candidatos")).scalar() != cantidad:
            raise ValueError("El cruce cambió la cantidad de registros del origen.")
        for columna in fechas_fk:
            faltantes = destino.execute(text(f"""
                SELECT count(*) FROM _etl_candidatos c LEFT JOIN dim_tiempo t
                ON t.sk_fecha=c.{columna} WHERE t.sk_fecha IS NULL
            """)).scalar()
            if faltantes:
                raise ValueError(f"Faltan fechas en dim_tiempo para {columna}. Complete el calendario y repita.")
        campos = ",".join(columnas)
        destino.execute(text(f"""
            CREATE TEMP TABLE _etl_fechas ON COMMIT DROP AS
            SELECT DISTINCT {columna_fecha} FROM (
                (SELECT {campos} FROM _etl_candidatos EXCEPT ALL SELECT {campos} FROM {tabla})
                UNION ALL
                (SELECT {campos} FROM {tabla} EXCEPT ALL SELECT {campos} FROM _etl_candidatos)
            ) diferencias
        """))
        dias = int(destino.execute(text("SELECT count(*) FROM _etl_fechas")).scalar())
        eliminadas = insertadas = 0
        if modo == "INICIAL":
            eliminadas = anteriores
            destino.execute(text(f"TRUNCATE TABLE {tabla} RESTART IDENTITY"))
            insertadas = destino.execute(text(f"INSERT INTO {tabla} ({campos}) SELECT {campos} FROM _etl_candidatos")).rowcount
        elif dias:
            eliminadas = destino.execute(text(f"""DELETE FROM {tabla} f USING _etl_fechas d
                WHERE f.{columna_fecha}=d.{columna_fecha}""")).rowcount
            insertadas = destino.execute(text(f"""INSERT INTO {tabla} ({campos})
                SELECT {','.join('c.' + campo for campo in columnas)} FROM _etl_candidatos c
                JOIN _etl_fechas d ON c.{columna_fecha}=d.{columna_fecha}""")).rowcount
        agregados = ",".join(["count(*) AS filas"] + [f"coalesce(sum({m}),0) AS {m}" for m in medidas])
        esperado = leer(destino, f"SELECT {agregados} FROM _etl_candidatos")[0]
        obtenido = leer(destino, f"SELECT {agregados} FROM {tabla}")[0]
        if esperado != obtenido:
            raise ValueError(f"Conciliación incorrecta: esperado={esperado}, obtenido={obtenido}")
        claves = [col for col in columnas if col.startswith("sk_") and col not in fechas_fk]
        desconocidos = leer(destino, "SELECT " + ",".join(
            f"count(*) FILTER (WHERE {col}=-1) AS {col}" for col in claves) + " FROM _etl_candidatos")[0]
        resumen = {"origen": cantidad, "dias_reemplazados": dias,
                   "filas_reemplazadas": eliminadas, "filas_insertadas": insertadas,
                   "claves_desconocidas": desconocidos}
    resumen["filas_eliminadas"] = eliminadas
    resumen["filas_actualizadas"] = 0
    if modo == "DIFERENCIAL" and dias == 0:
        print(f"{tabla}: cambios no detectados; no se modificaron filas.")
    else:
        print(f"{tabla}: {resumen}")
    return resumen
