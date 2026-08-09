# Archivo: run_pipeline.py
import sys
from datetime import datetime

# Importamos EXCLUSIVAMENTE las funciones incrementales de nuestros scripts
# Asegúrate de que los nombres de los archivos (.py) coincidan con los tuyos
try:
    from dim_operador_diferencial import diferencial_dim_operador
    from dim_tarifa_diferencial import diferencial_dim_tarifa
    from dim_tasacambio_diferencial import diferencial_dim_tasa_cambio
    from fact_enviotap_diferencial import diferencial_fact_envio_tap
    from fact_roaming_diferencial import diferencial_fact_roaming
except ImportError as e:
    print(f"❌ Error al importar los módulos. Verifica los nombres de los archivos: {e}")
    sys.exit(1)

def run_orquestador_roaming():
    inicio = datetime.now()
    print("="*60)
    print(f"INICIANDO ORQUESTADOR DE DATOS (ROAMING) - {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    try:
        # CARGA DE DIMENSIONES
        print("\n Actualizando Dimensiones...")
        diferencial_dim_operador()
        diferencial_dim_tarifa()
        diferencial_dim_tasa_cambio()
        print("completada con éxito.")

        # CARGA DE HECHOS 
        # Solo se ejecuta si las dimensiones no tuvieron errores
        print("\n Actualizando Tablas de Hechos...")
        diferencial_fact_roaming()
        diferencial_fact_envio_tap()
        print("completada con éxito.")

        # CIERRE Y MÉTRICAS DE EJECUCIÓN
        fin = datetime.now()
        duracion = fin - inicio
        print("\n" + "="*60)
        print(f"FINALIZADO CON ÉXITO")
        print(f"Tiempo total de ejecución: {duracion.total_seconds():.2f} segundos")
        print("="*60 + "\n")

    except Exception as e:
        # Si CUALQUIER script falla, el pipeline aborta para proteger los datos
        print("\n" + "!"*60)
        print(f"ERROR FATAL EN LA CARGA: {e}")
        print("El proceso se detuvo de emergencia para proteger la integridad del DW.")
        print("!"*60 + "\n")
        sys.exit(1)

if __name__ == '__main__':
    run_orquestador_roaming()