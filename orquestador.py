"""Carga inicial completa. Reconstruye dimensiones y hechos; conserva dim_tiempo.

Usar en un DW nuevo o en una reconstrucción deliberada. Para un DW con
historial SCD ya acumulado, usar orquestador_diferencial.py.
"""
from db_config import probar_conexiones
from control_cargas import ejecutar_lote, mensaje_error
from cargas_iniciales.dim_operador import cargar_dim_operador
from cargas_iniciales.dim_tarifa import cargar_dim_tarifa
from cargas_iniciales.dim_tasa_cambio import cargar_dim_tasa_cambio
from cargas_iniciales.fact_roaming import cargar_fact_roaming
from cargas_iniciales.fact_envio_tap import cargar_fact_envio_tap


def ejecutar_carga_inicial():
    print('INICIANDO ORQUESTADOR DE CARGA INICIAL (DW MOVISTAR)')
    if not probar_conexiones():
        raise RuntimeError('No se pudo conectar a las bases de datos.')
    return ejecutar_lote('INICIAL',[
        ('dim_operador',cargar_dim_operador,{}),
        ('dim_tarifa',cargar_dim_tarifa,{}),
        ('dim_tasa_cambio',cargar_dim_tasa_cambio,{}),
        ('fact_roaming',cargar_fact_roaming,{}),
        ('fact_envio_tap',cargar_fact_envio_tap,{}),
    ])


if __name__=='__main__':
    try:
        ejecutar_carga_inicial()
    except Exception as error:
        raise SystemExit('ERROR: '+mensaje_error(error)) from error
