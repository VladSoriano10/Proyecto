from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


# CONFIGURACIÓN DEL SERVIDOR 

USER = "postgres"  
PASSWORD = "admin"  
HOST = "localhost"
PORT = "5432"

# Cadenas de conexión
str_origen = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/Roaming"
str_destino = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/DWRoamingMovistar"

# Creación de los motores 
engine_origen = create_engine(str_origen)
engine_destino = create_engine(str_destino)


def probar_conexiones():
    print("Verificando conexiones a las bases de datos...")

    #Probar base de origen 
    try:
        with engine_origen.connect() as conn:
            print("[OK] Conectado a la base origen: 'Roaming'")
    except OperationalError:
        print(
            "[ERROR] Falló la conexión a 'Roaming'. Verifica que el servidor 'data' esté activo y las credenciales sean correctas."
        )
        return False

    #Probar base destino 
    try:
        with engine_destino.connect() as conn:
            print("[OK] Conectado a la base destino: 'DWRoamingMovistar'")
    except OperationalError:
        print(
            "[ERROR] Falló la conexión a 'DWRoamingMovistar'. Verifica que la base de datos exista."
        )
        return False

    return True


if __name__ == "__main__":
    probar_conexiones()
