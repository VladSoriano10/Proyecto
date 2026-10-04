"""Extracción y limpieza compartidas por las dos modalidades de carga."""
from datetime import date, datetime, timedelta
from sqlalchemy import text
from control_cargas import transaccion_destino
from etl_comun import (FIN_FECHA, FIN_INSTANTE, cadena, fecha, instante, decimal,
                       leer, insertar, unicos, verificar_vigencias)


def extraer_operadores(engine):
    with engine.connect() as conn:
        filas = leer(conn, '''SELECT o.id_operador AS nk_id_operador,
            o.nombre_operador,o.status,o.id_pais AS nk_id_pais,
            p.nombre_pais,p.prefijo_telefonico
            FROM operadores o LEFT JOIN pais p ON p.id_pais=o.id_pais''')
    defaults = {'nk_id_operador':'','nombre_operador':'OPERADOR DESCONOCIDO',
                'status':'DESCONOCIDO','nk_id_pais':'N/D',
                'nombre_pais':'PAÍS DESCONOCIDO','prefijo_telefonico':'000'}
    filas = [dict({c:cadena(f[c],d) for c,d in defaults.items()},
                  fecha_inicio_vigencia=date(1900,1,1),fecha_fin_vigencia=FIN_FECHA)
             for f in filas]
    unicos(filas,'nk_id_operador')
    return filas


def extraer_tarifas(engine):
    with engine.connect() as conn:
        filas=leer(conn,'''SELECT id_tarifa AS nk_id_tarifa,tipo_trafico,
            costo_unidad,moneda,fecha_inicio_vigencia,fecha_fin_vigencia FROM tarifas''')
    servicios={'GPRS':'GPRS - DATOS MÓVILES','PORTAL':'PORTAL - VOZ','CAMEL':'CAMEL - EVENTOS'}
    for f in filas:
        f['nk_id_tarifa']=int(f['nk_id_tarifa'])
        servicio=cadena(f['tipo_trafico'],'DESCONOCIDO')
        f['tipo_trafico']=servicios.get(servicio,servicio)
        f['costo_unidad']=decimal(f['costo_unidad'],4)
        f['moneda']=cadena(f['moneda'],'USD')
        f['fecha_inicio_vigencia']=fecha(f['fecha_inicio_vigencia'])
        f['fecha_fin_vigencia']=fecha(f['fecha_fin_vigencia']) if f['fecha_fin_vigencia'] else FIN_FECHA
    unicos(filas,'nk_id_tarifa')
    verificar_vigencias(filas,'nk_id_tarifa','fecha_inicio_vigencia','fecha_fin_vigencia')
    return filas


def extraer_tasas(engine):
    with engine.connect() as conn:
        filas=leer(conn,'''SELECT id_tasa AS nk_id_tasa,moneda_origen,
            moneda_destino,factor_cambio,fecha_desde,fecha_hasta FROM tasa_de_cambio''')
    grupos={}
    for f in filas:
        f['nk_id_tasa']=int(f['nk_id_tasa'])
        f['moneda_origen']=cadena(f['moneda_origen'],'N/D')
        f['moneda_destino']=cadena(f['moneda_destino'],'USD')
        f['factor_cambio']=decimal(f['factor_cambio'],6)
        f['fecha_desde']=instante(f['fecha_desde'])
        f['fecha_hasta']=instante(f['fecha_hasta']) if f['fecha_hasta'] else FIN_INSTANTE
        grupos.setdefault((f['moneda_origen'],f['moneda_destino']),[]).append(f)
    unicos(filas,'nk_id_tasa')
    for par,tasas in grupos.items():
        tasas.sort(key=lambda f:f['fecha_desde'])
        for anterior,siguiente in zip(tasas,tasas[1:]):
            if anterior['fecha_desde']==siguiente['fecha_desde']:
                raise ValueError(f'Dos tasas de {par} comienzan al mismo tiempo.')
            anterior['fecha_hasta']=min(anterior['fecha_hasta'],
                                        siguiente['fecha_desde']-timedelta(microseconds=1))
    verificar_vigencias(filas,'nk_id_tasa','fecha_desde','fecha_hasta')
    return filas


CATALOGOS = {
    'dim_operador':('sk_operador',{'sk_operador':-1,'nk_id_operador':'N/A',
        'nombre_operador':'DESCONOCIDO','status':'N/A','nk_id_pais':'N/A',
        'nombre_pais':'DESCONOCIDO','prefijo_telefonico':'N/A',
        'fecha_inicio_vigencia':date(1900,1,1),'fecha_fin_vigencia':FIN_FECHA}),
    'dim_tarifa':('sk_tarifa',{'sk_tarifa':-1,'nk_id_tarifa':-1,
        'tipo_trafico':'DESCONOCIDO','costo_unidad':decimal(0,4),'moneda':'N/A',
        'fecha_inicio_vigencia':date(1900,1,1),'fecha_fin_vigencia':FIN_FECHA}),
    'dim_tasa_cambio':('sk_tasa',{'sk_tasa':-1,'nk_id_tasa':-1,
        'moneda_origen':'N/A','moneda_destino':'N/A','factor_cambio':decimal(1,6),
        'fecha_desde':datetime(1900,1,1),'fecha_hasta':FIN_INSTANTE}),
}


def cargar_catalogo_inicial(engine, tabla, filas):
    if tabla not in CATALOGOS:
        raise ValueError('Catálogo no permitido.')
    pk,comodin=CATALOGOS[tabla]
    with transaccion_destino(engine) as conn:
        conn.execute(text(f'LOCK TABLE {tabla} IN ACCESS EXCLUSIVE MODE'))
        anteriores=int(conn.execute(text(f'SELECT count(*) FROM {tabla}')).scalar())
        if not filas and anteriores:
            raise ValueError(f'{tabla}: origen vacío ante una dimensión poblada. Revise la conexión.')
        # El orquestador ejecuta las tres dimensiones y las dos facts en una
        # transacción. CASCADE reinicia las facts; si un paso falla se revierte todo.
        conn.execute(text(f'TRUNCATE TABLE {tabla} RESTART IDENTITY CASCADE'))
        insertar(conn,tabla,filas)
        insertar(conn,tabla,[comodin])
    return dict(origen=len(filas),insertadas=len(filas),versiones_nuevas=0,
                filas_insertadas=len(filas)+1,filas_actualizadas=0,
                filas_eliminadas=anteriores,comodines_insertados=1,
                advertencia='Carga inicial: CASCADE reconstruye también las facts dependientes.')
