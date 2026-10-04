"""Actualiza el DW existente, con corte opcional para pruebas controladas.

python orquestador_diferencial.py
python orquestador_diferencial.py --fecha-corte 2026-10-05

El corte solo afecta a las versiones SCD; las facts leen TODO el origen.
"""
import argparse
from datetime import date, datetime, time
from db_config import probar_conexiones
from control_cargas import ejecutar_lote, ahora_negocio, mensaje_error
from cargas_diferenciales.dim_operador_diferencial import diferencial_dim_operador
from cargas_diferenciales.dim_tarifa_diferencial import diferencial_dim_tarifa
from cargas_diferenciales.dim_tasacambio_diferencial import diferencial_dim_tasa_cambio
from cargas_diferenciales.fact_roaming_diferencial import diferencial_fact_roaming
from cargas_diferenciales.fact_enviotap_diferencial import diferencial_fact_envio_tap


def fecha_iso(valor):
    try:
        resultado=date.fromisoformat(valor)
        if resultado.isoformat()!=valor:
            raise ValueError
        return resultado
    except ValueError as error:
        raise argparse.ArgumentTypeError('Use AAAA-MM-DD con una fecha válida.') from error


def ejecutar(fecha_corte=None):
    if not probar_conexiones():
        raise RuntimeError('No se pudo conectar a las bases de datos.')
    momento=ahora_negocio() if fecha_corte is None else datetime.combine(fecha_corte,time.min)
    print(f'INICIANDO ORQUESTADOR DIFERENCIAL. Corte: {momento.isoformat()}')
    return ejecutar_lote('DIFERENCIAL',[
        ('dim_operador',diferencial_dim_operador,{'fecha_corte':momento.date()}),
        ('dim_tarifa',diferencial_dim_tarifa,{'fecha_corte':momento.date()}),
        ('dim_tasa_cambio',diferencial_dim_tasa_cambio,{'momento_corte':momento}),
        ('fact_roaming',diferencial_fact_roaming,{}),
        ('fact_envio_tap',diferencial_fact_envio_tap,{}),
    ],parametros={'momento_corte':momento,'corte_simulado':fecha_corte is not None})


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fecha-corte',type=fecha_iso,metavar='AAAA-MM-DD',
                        help='Fecha de prueba. Sin ella se utiliza la hora de El Salvador.')
    argumentos=parser.parse_args(argv)
    try:
        return ejecutar(argumentos.fecha_corte)
    except Exception as error:
        raise SystemExit('ERROR: '+mensaje_error(error)) from error


if __name__=='__main__':
    main()
