"""Control de ejecuciones y una transacción de destino para el lote completo.

La fila LOTE se abre antes de empezar. Sus resultados y los datos se confirman
juntos. Si falla un paso, se revierten todos los cambios del lote y se registra
el fallo en otra transacción. Una caída abrupta puede dejar LOTE EN_CURSO.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from functools import wraps
import json
from time import perf_counter
from uuid import uuid4

from sqlalchemy import text

_conexion = ContextVar('conexion_etl', default=None)
_conteos_previos = ContextVar('conteos_previos_etl', default={})


def conteo_previo(tabla, actual):
    """Conserva el conteo anterior a los TRUNCATE CASCADE de la carga inicial."""
    return _conteos_previos.get().get(tabla, actual)


def ahora_negocio():
    """Hora de El Salvador, independiente de la zona del contenedor."""
    return datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=-6))).replace(tzinfo=None)


@contextmanager
def transaccion_destino(engine):
    activa = _conexion.get()
    if activa is not None:
        if activa.engine is not engine:
            raise RuntimeError('El lote intentó utilizar otro motor de destino.')
        yield activa
    else:
        with engine.begin() as conn:
            yield conn


def mensaje_error(error):
    # Evita volcar parámetros de INSERT o credenciales en la tabla de control.
    original = getattr(error, 'orig', None)
    if original is not None:
        diag = getattr(original, 'diag', None)
        mensaje = getattr(diag, 'message_primary', None) or type(original).__name__
        codigo = getattr(original, 'pgcode', None)
        return f'{type(error).__name__}: {mensaje}; SQLSTATE={codigo}'[:1800]
    return f'{type(error).__name__}: {error}'[:1800]


def _estado(resumen):
    claves = ('filas_insertadas', 'filas_actualizadas', 'filas_eliminadas')
    return 'EXITOSO' if any(resumen.get(c, 0) for c in claves) else 'SIN_CAMBIOS'


def _insertar_proceso(conn, ejecucion, tipo, paso, resultado, estado,
                     inicio, fin, duracion, mensaje=None):
    confirmado = estado in ('EXITOSO', 'SIN_CAMBIOS')
    datos = resultado or {}
    detalle = datos if confirmado else {'operaciones_revertidas': datos}
    conn.execute(text('''INSERT INTO public.control_cargas
        (id_ejecucion,tipo_carga,proceso,tabla_destino,fecha_inicio,fecha_fin,
         duracion_segundos,estado,registros_leidos,filas_insertadas,
         filas_actualizadas,filas_eliminadas,versiones_nuevas,dias_reemplazados,detalle,mensaje)
        VALUES (CAST(:ej AS uuid),:tipo,:paso,:paso,:inicio,:fin,:duracion,:estado,
                :leidos,:ins,:act,:elim,:versiones,:dias,CAST(:detalle AS jsonb),:mensaje)
    '''), dict(ej=ejecucion, tipo=tipo, paso=paso, inicio=inicio, fin=fin,
        duracion=round(duracion,3), estado=estado, leidos=datos.get('origen'),
        ins=datos.get('filas_insertadas',0) if confirmado else 0,
        act=datos.get('filas_actualizadas',0) if confirmado else 0,
        elim=datos.get('filas_eliminadas',0) if confirmado else 0,
        versiones=datos.get('versiones_nuevas',0) if confirmado else 0,
        dias=datos.get('dias_reemplazados',0) if confirmado else 0,
        detalle=json.dumps(detalle, default=str, ensure_ascii=False), mensaje=mensaje))


def ejecutar_lote(tipo, pasos, parametros=None):
    """pasos: lista de (nombre de tabla, función, argumentos).

No anidar lotes. El candado evita dos ejecuciones simultáneas de estos scripts
en el mismo DW. El origen debe conservar el historial completo de las facts.
"""
    from db_config import engine_destino
    if _conexion.get() is not None:
        raise RuntimeError('No se permite iniciar un lote dentro de otro.')
    if tipo not in ('INICIAL', 'DIFERENCIAL') or not pasos:
        raise ValueError('Tipo de carga o lista de pasos no válidos.')
    ejecucion = str(uuid4())
    reloj = perf_counter()
    with engine_destino.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.control_cargas')")).scalar() is None:
            raise RuntimeError('Falta public.control_cargas. Ejecute Agregar_Control_Cargas.sql en el DW.')
        conn.execute(text('''INSERT INTO public.control_cargas
            (id_ejecucion,tipo_carga,proceso,estado,detalle)
            VALUES (CAST(:ej AS uuid),:tipo,'LOTE','EN_CURSO',CAST(:detalle AS jsonb))
        '''), dict(ej=ejecucion,tipo=tipo,detalle=json.dumps(parametros or {},default=str)))
    resultados, completados = {}, []
    actual = None
    inicio_paso = None
    reloj_paso = perf_counter()
    print(f'Ejecución {ejecucion} ({tipo})', flush=True)
    try:
        with engine_destino.begin() as conn:
            if not conn.execute(text('SELECT pg_try_advisory_xact_lock(7426, 20261002)')).scalar():
                raise RuntimeError('Ya hay otra carga activa en este DW. Espere a que termine.')
            previos = {}
            if tipo == 'INICIAL':
                for tabla in ('fact_roaming', 'fact_envio_tap'):
                    previos[tabla] = int(conn.execute(text(f'SELECT count(*) FROM {tabla}')).scalar())
            token = _conexion.set(conn)
            token_conteos = _conteos_previos.set(previos)
            try:
                for nombre, funcion, argumentos in pasos:
                    actual = nombre
                    inicio_paso = datetime.now(timezone.utc)
                    reloj_paso = perf_counter()
                    print(f'Procesando {nombre}...', flush=True)
                    resultado = funcion(**argumentos)
                    if not isinstance(resultado, dict):
                        raise RuntimeError(f'{nombre} no devolvió un resumen de carga.')
                    fin = datetime.now(timezone.utc)
                    duracion = perf_counter() - reloj_paso
                    resultados[nombre] = resultado
                    completados.append((nombre,resultado,inicio_paso,fin,duracion))
                    _insertar_proceso(conn,ejecucion,tipo,nombre,resultado,
                                      _estado(resultado),inicio_paso,fin,duracion)
                    actual = None
                estado = 'EXITOSO' if any(_estado(r)=='EXITOSO' for r in resultados.values()) else 'SIN_CAMBIOS'
                conn.execute(text('''UPDATE public.control_cargas
                    SET estado=:estado,fecha_fin=clock_timestamp(),duracion_segundos=:duracion,
                        detalle=detalle || CAST(:detalle AS jsonb),mensaje=:mensaje
                    WHERE id_ejecucion=CAST(:ej AS uuid) AND proceso='LOTE'
                '''),dict(estado=estado,duracion=round(perf_counter()-reloj,3),ej=ejecucion,
                    detalle=json.dumps({'procesos_completados':len(resultados)}),
                    mensaje='Lote confirmado completo. Consulte las filas por tabla.'))
            finally:
                _conexion.reset(token)
                _conteos_previos.reset(token_conteos)
    except BaseException as error:
        # Llegamos después del rollback. Nunca se informan escrituras revertidas
        # como si estuvieran confirmadas. Se preserva el error original.
        mensaje = mensaje_error(error)
        try:
            with engine_destino.begin() as conn:
                conn.execute(text('''UPDATE public.control_cargas
                    SET estado='ERROR',fecha_fin=clock_timestamp(),duracion_segundos=:duracion,mensaje=:mensaje
                    WHERE id_ejecucion=CAST(:ej AS uuid) AND proceso='LOTE'
                '''),dict(ej=ejecucion,duracion=round(perf_counter()-reloj,3),mensaje=mensaje))
                registrados = set()
                for nombre,resultado,inicio,fin,duracion in completados:
                    _insertar_proceso(conn,ejecucion,tipo,nombre,resultado,'REVERTIDO',
                                      inicio,fin,duracion,'Se revirtió el lote completo.')
                    registrados.add(nombre)
                if actual and actual not in registrados:
                    _insertar_proceso(conn,ejecucion,tipo,actual,{},'ERROR',inicio_paso,
                                      datetime.now(timezone.utc),perf_counter()-reloj_paso,mensaje)
                    registrados.add(actual)
                for nombre,_,_ in pasos:
                    if nombre not in registrados:
                        ahora = datetime.now(timezone.utc)
                        _insertar_proceso(conn,ejecucion,tipo,nombre,{},'OMITIDO',ahora,ahora,0,
                                          'No se ejecutó debido al fallo del lote.')
        except Exception as error_control:
            print(f'No se pudo registrar el cierre del fallo: {mensaje_error(error_control)}',flush=True)
        raise
    print(f'Carga {tipo.lower()} confirmada: {estado}.',flush=True)
    return resultados


def registrar_carga(tabla, tipo):
    """También registra y protege una ejecución individual por python -m."""
    def decorar(funcion):
        @wraps(funcion)
        def ejecutar(*args, **kwargs):
            if _conexion.get() is not None:
                return funcion(*args, **kwargs)
            return ejecutar_lote(tipo,[(tabla,lambda: funcion(*args,**kwargs),{})],
                                 parametros=kwargs)[tabla]
        return ejecutar
    return decorar
