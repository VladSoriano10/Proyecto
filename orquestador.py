import time

from db_config import probar_conexiones

# Importamos las funciones principales de cada script ETL 
from dim_operador import cargar_dim_operador
from dim_tarifa import cargar_dim_tarifa
from dim_tasa_cambio import cargar_dim_tasa_cambio
from fact_envio_tap import cargar_fact_envio_tap
from fact_roaming import cargar_fact_roaming


def ejecutar_carga_inicial():
    print("=========================================================")
    print("🚀 INICIANDO ORQUESTADOR DE CARGA INICIAL (DW MOVISTAR) 🚀")
    print("=========================================================")
    
    # 1. Verificación de conexiones
    if not probar_conexiones():
        print("\n FALLA CRÍTICA: No se pudo conectar a las bases de datos. Abortando pipeline.")
        return


    pasos_etl = [
        {"nombre": "Dimensión Operador", "funcion": cargar_dim_operador},
        {"nombre": "Dimensión Tarifa", "funcion": cargar_dim_tarifa},
        {"nombre": "Dimensión Tasa de Cambio", "funcion": cargar_dim_tasa_cambio},
        {"nombre": "Hechos - Roaming", "funcion": cargar_fact_roaming},
        {"nombre": "Hechos - Envíos TAP", "funcion": cargar_fact_envio_tap}
    ]

    inicio_total = time.time()

    # 3. Ejecución secuencial con manejo de errores
    for paso in pasos_etl:
        print(f"\n⏳ Ejecutando: {paso['nombre']}...")
        inicio_paso = time.time()
        
        try:
            paso['funcion']()
            
            fin_paso = time.time()
            duracion = round(fin_paso - inicio_paso, 2)
            print(f"✅ {paso['nombre']} completado exitosamente en {duracion} segundos.")
            
        except Exception as e:
            print(f"\n ERROR FATAL durante la ejecución de {paso['nombre']}.")
            print(f"Detalle técnico del error: {str(e)}")
            print("Pipeline abortado. Revisa el error antes de continuar.")
            return

    fin_total = time.time()
    duracion_total = round((fin_total - inicio_total) / 60, 2)
    
    print("\n=========================================================")
    print(f" PIPELINE COMPLETADO EXITOSAMENTE")
    print(f"⏱️ Tiempo total de ejecución: {duracion_total} minutos.")
    print("=========================================================")

if __name__ == '__main__':
    ejecutar_carga_inicial()