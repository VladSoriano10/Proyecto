"""Conexiones para las cargas iniciales y diferenciales de Movistar."""

import os

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


# CREDENCIALES
USER = os.getenv("DB_USER", "postgres")
PASSWORD = os.getenv("DB_PASSWORD", "admin")

# Desde Windows se utiliza localhost.
# Dentro de Docker, Compose proporciona DB_HOST=postgres.
HOST = os.getenv("DB_HOST", "localhost")


# PUERTO PREDETERMINADO
# Dejar activa solamente UNA de las dos líneas.

# VLAD: Python desde Windows conectado al PostgreSQL de Docker.
PORT = os.getenv("DB_PORT", "5532")

# COMPAÑERA: puerto 5432.
# Para usarlo, comenta la línea anterior y descomenta esta:
# PORT = os.getenv("DB_PORT", "5432")


# CONFIGURACIÓN POR CONEXIÓN
# Si estas variables no existen, ambas conexiones usan HOST y PORT.
HOST_ORIGEN = os.getenv("DB_HOST_ORIGEN", HOST)
HOST_DESTINO = os.getenv("DB_HOST_DESTINO", HOST)

PORT_ORIGEN = os.getenv("DB_PORT_ORIGEN", PORT)
PORT_DESTINO = os.getenv("DB_PORT_DESTINO", PORT)


# BASE DE DATOS ORIGEN
DB_ORIGEN = os.getenv("DB_ORIGEN", "Roaming")


# BASE DE DATOS DESTINO
# Dejar activa solamente UNA de las dos líneas.

# VLAD: DW nuevo, sin versión.
DB_DESTINO = os.getenv("DB_DESTINO", "DWMovistar")

# COMPAÑERA: DW versión 2.
# Para usarlo, comenta la línea anterior y descomenta esta:
# DB_DESTINO = os.getenv("DB_DESTINO", "DWRoamingMovistarV2")


# CADENAS DE CONEXIÓN
str_origen = (
    f"postgresql+psycopg2://{USER}:{PASSWORD}"
    f"@{HOST_ORIGEN}:{PORT_ORIGEN}/{DB_ORIGEN}"
)

str_destino = (
    f"postgresql+psycopg2://{USER}:{PASSWORD}"
    f"@{HOST_DESTINO}:{PORT_DESTINO}/{DB_DESTINO}"
)


# MOTORES DE SQLALCHEMY
engine_origen = create_engine(str_origen)
engine_destino = create_engine(str_destino)


def probar_conexiones():
    print("Verificando conexiones a las bases de datos...")

    conexiones = [
        (
            "origen",
            DB_ORIGEN,
            HOST_ORIGEN,
            PORT_ORIGEN,
            engine_origen,
        ),
        (
            "destino",
            DB_DESTINO,
            HOST_DESTINO,
            PORT_DESTINO,
            engine_destino,
        ),
    ]

    for tipo, nombre, servidor, puerto, motor in conexiones:
        try:
            with motor.connect():
                print(
                    f"[OK] Conectado a {tipo}: '{nombre}' "
                    f"({servidor}:{puerto})"
                )

        except OperationalError as error:
            print(
                f"[ERROR] Falló la conexión a {tipo}: '{nombre}' "
                f"({servidor}:{puerto}). "
                "Verifica que PostgreSQL esté encendido, "
                "la base exista y las credenciales sean correctas."
            )
            print(f"Detalle: {error.orig}")
            return False

    return True


if __name__ == "__main__":
    raise SystemExit(0 if probar_conexiones() else 1)