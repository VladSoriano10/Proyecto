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
Configuración de la Base de Datos
Antes de correr el código, debes configurar las credenciales de conexión.

Abre el archivo db_config.py.

Verifica que el usuario, contraseña, puerto (por defecto 5432) y nombres de las bases de datos (Origen y Destino) coincidan con tu configuración local de PostgreSQL para el caso de ocupar docker tambien cambiar los puertos.

Markdown
## 🐳 (Docker)

este proyecto utiliza **Docker** y **Docker Compose**. La arquitectura separa físicamente la carga transaccional (OLTP) de la carga analítica (OLAP) en contenedores independientes de PostgreSQL 18.

### ⚙️ Topología de Contenedores
| Servidor (Contenedor) | Rol | Base de Datos | Puerto Expuesto |
| :--- | :--- | :--- | :--- |
| `movistar_transaccional` | Origen (OLTP) | `Roaming` | `5434` |
| `movistar_datawarehouse` | Destino (OLAP) | `DWRoamingMovistar` | `5433` |

---

### Despliegue Local

#### 1. Levantar los Servidores
Asegúrate de tener Docker Desktop ejecutándose. Abre una terminal en la raíz del proyecto y ejecuta:
```bash
# Levanta la infraestructura en segundo plano
docker-compose up -d
(Para detener la infraestructura en el futuro, utiliza docker-compose down).
```
2. Restaurar la Base de Datos Transaccional (Origen)
Se debe inyectar el backup lógico en el contenedor transaccional para simular la data histórica operativa:

```Bash
# Copiar el archivo de backup al contenedor
docker cp backups_bd/backup_Roaming_20260813_210852.sql movistar_transaccional:/tmp/backup.sql

# Ejecutar la restauración de la base de datos
docker exec -it movistar_transaccional pg_restore -U postgres -d Roaming -1 /tmp/backup.sql
```

3. Construir el Data Warehouse (Destino)
El contenedor del Data Warehouse inicia vacío. Debemos construir el esquema en estrella e inyectar la dimensión de tiempo:

```Bash
# 3.1 Copiar los scripts SQL al contenedor
docker cp creacionDW-ver2.sql movistar_datawarehouse:/tmp/creacionDW-ver2.sql
docker cp "dim_tiempo llenado.sql" movistar_datawarehouse:"/tmp/dim_tiempo llenado.sql"

# 3.2 Crear las tablas de Dimensiones y Hechos
docker exec -it movistar_datawarehouse psql -U postgres -d DWRoamingMovistarV2 -f /tmp/creacionDW-ver2.sql

# 3.3 Poblar la Dimensión Tiempo
docker exec -it movistar_datawarehouse psql -U postgres -d DWRoamingMovistarV2 -f "/tmp/dim_tiempo llenado.sql"
```

4. Ejecución del llenado ETL
Una vez que ambos servidores están en línea y estructurados, activa tu entorno virtual y ejecuta el orquestador maestro:

Bash
python orquestador_etl.py
