from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

# CONFIGURACIÓN DE CREDENCIALES
USER = "postgres"  
PASSWORD = "admin"  
HOST = "localhost"

# PUERTOS ASIGNADOS EN DOCKER-COMPOSE
PORT_ORIGEN = "5434"
PORT_DESTINO = "5433"

# NOMBRES DE LAS BASES DE DATOS
DB_ORIGEN = "Roaming"
DB_DESTINO = "DWRoamingMovistarV2"  # Corregido para coincidir con Docker

# Cadenas de conexión (separadas por puerto)
str_origen = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT_ORIGEN}/{DB_ORIGEN}"
str_destino = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT_DESTINO}/{DB_DESTINO}"

# Creación de los motores de SQLAlchemy
engine_origen = create_engine(str_origen)
engine_destino = create_engine(str_destino)

def probar_conexiones():
    print("Verificando conexiones a los contenedores de Docker...")

    # Probar base de origen 
    try:
        with engine_origen.connect() as conn:
            print(f"[OK] Conectado a la base origen: '{DB_ORIGEN}' (Puerto {PORT_ORIGEN})")
    except OperationalError as e:
        print(
            f"[ERROR] Falló la conexión a '{DB_ORIGEN}'. Verifica que el contenedor 'movistar_transaccional' esté encendido."
        )
        print(f"Detalle: {e}")
        return False

    # Probar base destino 
    try:
        with engine_destino.connect() as conn:
            print(f"[OK] Conectado a la base destino: '{DB_DESTINO}' (Puerto {PORT_DESTINO})")
    except OperationalError as e:
        print(
            f"[ERROR] Falló la conexión a '{DB_DESTINO}'. Verifica que el contenedor 'movistar_datawarehouse' esté encendido."
        )
        print(f"Detalle: {e}")
        return False

    return True

if __name__ == "__main__":
    probar_conexiones()