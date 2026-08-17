Data Warehouse - Proyecto de Roaming

Requisitos Previos

Antes de ejecutar el proyecto, asegúrate de tener instalado:
* **Python 3.8+** 
* **PostgreSQL** (Bases de datos Origen y Destino creadas).

 Configuración del Entorno de Desarrollo

Para evitar conflictos con otras librerías en tu computadora, es altamente recomendable usar un entorno virtual. Sigue estos pasos en la terminal de tu editor 

**1. Abrir la terminal en la carpeta del proyecto y crear el entorno virtual:**
```bash
python -m venv venv
```
2. Activar el entorno virtual:

En Windows:

```Bash
venv\Scripts\activate
```

3. Instalar las dependencias del proyecto:
Con el entorno activado, ejecuta el siguiente comando para instalar las librerías necesarias:

```Bash
pip install -r requirements.txt
```

Copiar .env.example en un nuevo archivo .env
```
cp .env.example .env
```

Si en VS Code en Python no logra detectar las configuraciones del .env, agregar esta configuracion al settings.json de su VS Code:
```
{
    // ...
    "python.terminal.useEnvFile": true,
}
```

Configuración de la Base de Datos
Antes de correr el código, debes configurar las credenciales de conexión.

Abre el archivo db_config.py.

Verifica que el usuario, contraseña, puerto (por defecto 5432) y nombres de las bases de datos (Origen y Destino) coincidan con tu configuración local de PostgreSQL.

Ejecución del Proyecto
El proyecto está diseñado de forma modular. Aunque puedes correr cada script por separado, la forma correcta de actualizar el DataWarehouse es utilizando el Orquestador inicial y luego el diferencial, el cual respeta el orden de las dependencias.

Para ejecutar, asegúrate de tener tu entorno virtual activado y ejecuta:

```Bash
python orquestador.py
```

# Carga de Scripts iniciales para Contenedores de Docker

En el siguiente orden cargar la data de la base de datos Roaming y las de DWRoamingMovistarV2 despues de creado el contenedor de docker.

```
pg_restore roaming.sql -> DB Transaccional Roaming
psql creacionDW-ver2.sql -> DWRoamingMovistarV2
psql dim_tiempo llenado.sql -> DWRoamingMovistarV2
```

TODO: 
O Luego mover en un orden lexicografico los scripts que se utilizaran bajo un mismo orden en la carpeta init-db. 

