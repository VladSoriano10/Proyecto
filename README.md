# Data Warehouse — Roaming Movistar El Salvador

Proyecto académico de ingeniería de datos para integrar y analizar consumos de roaming y envíos TAP mediante PostgreSQL, procesos ETL en Python y un modelo dimensional. El respaldo ampliado incluye datos sintéticos para desarrollo y demostración; no debe presentarse como información operativa real de la empresa.

El proyecto permite ejecutar Python desde una terminal local o desde Docker. Las bases de origen y destino pueden estar en PostgreSQL local, en una misma instancia de Docker o en servidores separados.

> **Si ya tienes las bases restauradas y las cargas iniciales terminadas, conserva ese entorno. Actualizar este README no requiere volver a restaurar, crear volúmenes ni repetir cargas iniciales.** La plantilla Docker de esta guía es una opción para instalaciones nuevas, no una migración automática de los entornos existentes.

## 1. Elegir el modo de ejecución

| Modalidad | PostgreSQL | Python / ETL | Conexión desde Python |
|---|---|---|---|
| Local | Instalado en el equipo | Entorno virtual local | `localhost` y el puerto del servidor, normalmente `5432` |
| Mixta | En Docker | Entorno virtual local | `localhost` y el puerto publicado, por ejemplo `5532` |
| Docker | En Docker | Contenedor `etl` | Servicio `postgres` y puerto interno `5432` |
| Servidores separados | Una instancia para origen y otra para DW | Local o en una red con acceso a ambas | Host y puerto específicos para cada conexión |

La plantilla incluida utiliza **una instancia de PostgreSQL con dos bases separadas**: `Roaming` y `DWMovistar`. Es una separación lógica; ambas bases comparten el servidor. La configuración anterior de dos contenedores también puede usarse si se ajustan las conexiones.

## 2. Requisitos

- Docker Desktop y Docker Compose v2 para las modalidades que utilizan Docker. Los comandos de esta guía usan `docker compose`.
- Python y `venv` si el ETL se ejecuta desde Windows. La configuración de referencia de Vlad utiliza **Python 3.14.3**. El proyecto compartido también ha utilizado Python 3.11; cada integrante debe usar una versión compatible con su `requirements.txt`.
- Dependencias del proyecto en `requirements.txt`, entre ellas pandas, SQLAlchemy y un controlador compatible con `postgresql+psycopg2`, como `psycopg2-binary`.
- Respaldo de origen y los dos scripts del DW: `creacionDW-ver2.sql` y `dim_tiempo llenado.sql`.
- DBeaver o pgAdmin, opcionales para consultar las bases y ejecutar los SQL de pruebas.

Para PostgreSQL completamente local se necesita el servidor y sus herramientas `psql`, `pg_restore` y `createdb`. En la modalidad Docker esas herramientas se ejecutan dentro del contenedor; no hace falta instalar otro PostgreSQL en Windows.

Los ejemplos de terminal están escritos para **PowerShell**, desde la raíz del proyecto. Ejecuta cada paso y revisa su resultado antes de continuar.

## 3. Archivos y personalización por integrante

| Archivo | Propósito |
|---|---|
| `db_config.py` | Conexiones compartidas por las cargas iniciales y diferenciales |
| `requirements.txt` | Dependencias del proyecto; conservar las versiones acordadas por el equipo |
| `orquestador.py` | Carga inicial de dimensiones y hechos |
| `orquestador_diferencial.py` | Cargas diferenciales; la versión de pruebas admite `--fecha-corte` |
| `etl_diferencial_utils.py` | Funciones auxiliares requeridas por los diferenciales corregidos |
| `creacionDW-ver2.sql` | Tablas y relaciones del DW |
| `dim_tiempo llenado.sql` | Calendario de 2020 a 2030 |
| `backups_bd/` | Respaldos de origen, fuera de la imagen de Python |
| `compose.personal.yml` | Plantilla Docker opcional para una instalación propia |
| `Dockerfile.personal` | Construcción de la imagen ETL propia |
| `Dockerfile.personal.dockerignore` | Archivos excluidos de esa construcción |
| `.env.personal.example` | Plantilla de variables para Docker, compartible en Git |
| `.env.personal` | Configuración local de cada integrante, creada desde la plantilla |

Cada persona puede cambiar los nombres, por ejemplo `docker-compose-ana.yml`, `Dockerfile.ana` y `.env.ana`. En ese caso:

1. Usa el nombre real del Compose en `-f`.
2. Usa el nombre real del archivo de entorno en `--env-file` y en `APP_ENV_FILE`.
3. Define el Dockerfile elegido en `ETL_DOCKERFILE`.
4. Si cambias el Dockerfile, renombra también su archivo de exclusiones: por ejemplo `Dockerfile.ana.dockerignore`.
5. Elige un proyecto Docker propio con `-p`, por ejemplo `roaming-ana`, y un puerto publicado disponible.

Cambiar solo el nombre del archivo Compose no aísla una instalación. El proyecto, sus volúmenes y los puertos deben corresponder al entorno deseado. La plantilla no fija `container_name`, para que Docker genere nombres separados por proyecto.

### Entorno de Vlad ya existente

El entorno construido anteriormente utiliza estos valores:

| Parámetro | Valor |
|---|---|
| Proyecto Docker | `movistar-vlad` |
| Archivo Compose | `docker-compose-vlad.yml` |
| Archivo de entorno del servicio | `vlad.env` |
| Contenedor PostgreSQL | `movistar_postgres_vlad` |
| Volumen | `movistar-vlad_postgres_data_vlad` |
| Puerto publicado | `5532` |
| Bases | `Roaming` y `DWMovistar` |

Para ese entorno conserva su Compose y sus comandos, por ejemplo:

```powershell
docker compose -p movistar-vlad -f docker-compose-vlad.yml ps
```

Si quieres un Dockerfile propio allí, crea `Dockerfile.vlad` y cambia **solo** `build.dockerfile` del servicio `etl` para apuntar a él. Conserva el proyecto, volumen, servicio y puerto de PostgreSQL. La plantilla genérica usa otro proyecto y otro nombre de volumen; no la levantes en el puerto ocupado por la instalación existente ni esperes que encuentre sus datos automáticamente.

## 4. Puertos y nombres de bases

**`5432` es el puerto habitual de PostgreSQL, pero el puerto publicado en Windows puede ser otro.**

| Escenario desde Windows | Host origen | Puerto origen | Host destino | Puerto destino |
|---|---|---:|---|---:|
| Ambas bases en PostgreSQL local estándar | `localhost` | `5432` | `localhost` | `5432` |
| Ambas bases en un Docker publicado en 5532 | `localhost` | `5532` | `localhost` | `5532` |
| Configuración anterior con dos contenedores | `localhost` | `5434` | `localhost` | `5433` |
| Puerto personal de ejemplo | `localhost` | `5540` | `localhost` | `5540` |

En un mapeo `5532:5432`, el primer número es el puerto de Windows y el segundo es el puerto interno del contenedor. Desde DBeaver o Python local se usa `localhost:5532`; desde `etl` se usa `postgres:5432`.

Para usar el puerto estándar en Windows, define `POSTGRES_HOST_PORT=5432`, siempre que esté libre. Para elegir otro, por ejemplo `5540`, cambia ese valor y utiliza `5540` en DBeaver y Python local. **El puerto interno puede seguir siendo `5432`.** Dos servicios no pueden publicar simultáneamente la misma dirección y puerto.

Los nombres de bases también son configurables. Los ejemplos usan `Roaming` y `DWMovistar`; si el equipo utiliza `DWRoamingMovistarV2`, cambia `DB_DESTINO` y el nombre indicado en los comandos `createdb`, `psql`, `pg_restore` y en el cliente SQL. Las variables no crean ni renombran por sí mismas bases existentes.

## 5. Preparar una instalación Docker personal nueva

### 5.1. Archivo de entorno

Copia la plantilla solo si todavía no tienes tu archivo personal:

```powershell
Copy-Item .env.personal.example .env.personal
```

Contenido de referencia de `.env.personal`:

```dotenv
# Copiar como .env.personal. Valores de ejemplo para desarrollo local.
# Si cambias el nombre del archivo, actualiza APP_ENV_FILE y --env-file.
APP_ENV_FILE=.env.personal
ETL_DOCKERFILE=Dockerfile.personal
PYTHON_VERSION=3.14.3

# Puerto publicado en Windows. Puede ser 5432 si está libre, 5532 u otro.
POSTGRES_HOST_PORT=5532

DB_USER=postgres
DB_PASSWORD=admin
DB_ORIGEN=Roaming
DB_DESTINO=DWMovistar

# Estas direcciones son para Python DENTRO de Docker.
DB_HOST=postgres
DB_PORT=5432
DB_HOST_ORIGEN=postgres
DB_HOST_DESTINO=postgres
DB_PORT_ORIGEN=5432
DB_PORT_DESTINO=5432
```

`admin` es una contraseña de ejemplo para desarrollo local. Si eliges otra, mantenla coherente en las conexiones. Las variables de inicialización de PostgreSQL se aplican al crear un volumen vacío; editarlas después no cambia las credenciales guardadas en un servidor existente.

El archivo anterior está destinado a **Python dentro de Docker**. No se debe cargar sin ajustes en Python local, porque `postgres` es un nombre de servicio de la red Docker.

### 5.2. Dockerfile propio

Contenido de `Dockerfile.personal`:

```dockerfile
ARG PYTHON_VERSION=3.14.3
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "db_config.py"]
```

`PYTHON_VERSION` permite seleccionar otra versión, por ejemplo `3.11`, sin editar el Dockerfile. La versión elegida debe poder instalar las dependencias de `requirements.txt`. El Python del entorno virtual de Windows no determina el Python del contenedor.

Contenido de `Dockerfile.personal.dockerignore`:

```text
.git
.env
.env.*
*.env
venv
.venv
**/__pycache__
**/*.pyc
backups_bd
*.backup
*.dump
*.zip
```

Estas exclusiones evitan copiar el entorno virtual, respaldos y configuración privada dentro de la imagen. Durante la ejecución, Compose monta la carpeta del proyecto en `/app`; el entorno virtual de Windows no se utiliza como intérprete dentro de Linux.

### 5.3. Compose personal

Contenido de `compose.personal.yml`:

```yaml
services:
  postgres:
    image: postgres:18-alpine
    env_file:
      - ${APP_ENV_FILE:-.env.personal}
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:?Define DB_PASSWORD en el archivo de entorno}
      POSTGRES_DB: ${DB_ORIGEN:-Roaming}
      POSTGRES_INITDB_ARGS: "--encoding=UTF8"
    ports:
      - "127.0.0.1:${POSTGRES_HOST_PORT:-5532}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", 'pg_isready -h 127.0.0.1 -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"']
      interval: 5s
      timeout: 5s
      retries: 12
      start_period: 10s
    restart: unless-stopped

  etl:
    profiles: ["manual"]
    build:
      context: .
      dockerfile: ${ETL_DOCKERFILE:-Dockerfile.personal}
      args:
        PYTHON_VERSION: ${PYTHON_VERSION:-3.14.3}
    env_file:
      - ${APP_ENV_FILE:-.env.personal}
    working_dir: /app
    environment:
      DB_USER: ${DB_USER:-postgres}
      DB_PASSWORD: ${DB_PASSWORD:?Define DB_PASSWORD en el archivo de entorno}
      DB_ORIGEN: ${DB_ORIGEN:-Roaming}
      DB_DESTINO: ${DB_DESTINO:-DWMovistar}
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - .:/app
    entrypoint: ["python"]
    command: ["db_config.py"]
    restart: "no"

volumes:
  postgres_data:
```

Esta plantilla utiliza PostgreSQL 18 y monta sus datos en `/var/lib/postgresql`. Las imágenes oficiales de PostgreSQL 17 y anteriores utilizan otra disposición, habitualmente `/var/lib/postgresql/data`. No cambies de versión mayor reutilizando directamente el mismo volumen; prepara una migración mediante respaldo y restauración.

El perfil `manual` evita iniciar automáticamente el ETL. El servicio puede ejecutarse expresamente con `run --rm etl ...`.

### 5.4. Validar e iniciar PostgreSQL

Con Docker Desktop encendido:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml config --quiet
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml up -d --wait postgres
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml ps
```

Usa siempre el mismo conjunto de `--env-file`, `-p` y `-f` para administrar esa instalación. Las variables de la terminal pueden sobrescribir valores usados por la interpolación de Compose; evita mezclar configuraciones de distintos entornos en la misma sesión.

### 5.5. Crear la base destino

En el primer arranque del volumen vacío, la plantilla crea la base indicada en `DB_ORIGEN`. Con los valores del ejemplo, se crea `Roaming`. Crea `DWMovistar` **una sola vez**, si todavía no existe:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml exec -T postgres createdb -U postgres DWMovistar
```

Consulta las bases disponibles:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml exec -T postgres psql -U postgres -d postgres -c "SELECT datname FROM pg_database WHERE datistemplate = false;"
```

Aquí `-d postgres` es intencional: se consulta el catálogo desde la base predeterminada. Si cambiaste el usuario o el nombre del DW, sustituye también los argumentos de estos comandos.

## 6. Restaurar el origen

Usa el respaldo final previo a las pruebas diferenciales y una base origen vacía. No repitas la restauración sobre una base que ya contiene el mismo respaldo.

Comprueba el nombre real del archivo:

```powershell
Get-ChildItem -LiteralPath ".\backups_bd" -File | Select-Object Name
```

**El formato del contenido determina la herramienta.** Un archivo personalizado de PostgreSQL se restaura con `pg_restore`, aunque termine en `.sql`. Un script SQL de texto se ejecuta con `psql`. Cambiar la extensión no convierte el formato.

### Opción A: respaldo personalizado, normalmente `.backup`

Sustituye `NOMBRE_REAL.backup` por el nombre que aparece en tu carpeta:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml cp ".\backups_bd\NOMBRE_REAL.backup" postgres:/tmp/roaming.backup
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml exec -T postgres pg_restore -U postgres -d Roaming --no-owner --no-privileges --single-transaction --verbose /tmp/roaming.backup
```

`--no-owner` y `--no-privileges` omiten propietarios y permisos del servidor anterior en esta copia de desarrollo. La transacción única revierte este intento si falla. No se utiliza `--clean`: el procedimiento parte de una base vacía.

### Opción B: script SQL de texto

Ejecuta esta alternativa únicamente si tu respaldo es texto SQL. Ajusta el nombre del archivo:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml cp ".\backups_bd\Roaming_Ampliado_Sintetico.sql" postgres:/tmp/roaming.sql
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml exec -T postgres psql -U postgres -d Roaming -v ON_ERROR_STOP=1 -f /tmp/roaming.sql
```

No ejecutes ambas opciones para el mismo respaldo. Si `psql` informa `The input is a PostgreSQL custom-format dump`, utiliza la opción A sobre el archivo ya copiado, conservando su ruta real dentro del contenedor.

Inmediatamente después de la restauración, consulta el código de salida:

```powershell
$LASTEXITCODE
```

Debe ser `0`. Si hay errores, resuélvelos antes de continuar. En un SQL de texto sin transacción global, los comandos previos al error pueden haber quedado aplicados; no asumas que la base permanece vacía.

## 7. Crear el DW y llenar la dimensión de tiempo

En la base destino nueva, ejecuta **estos dos archivos en este orden**:

1. `creacionDW-ver2.sql`: tablas y relaciones.
2. `dim_tiempo llenado.sql`: calendario de 2020 a 2030.

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml cp ".\creacionDW-ver2.sql" postgres:/tmp/crear_dw.sql
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml exec -T postgres psql -U postgres -d DWMovistar -v ON_ERROR_STOP=1 -f /tmp/crear_dw.sql
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml cp ".\dim_tiempo llenado.sql" postgres:/tmp/dim_tiempo.sql
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml exec -T postgres psql -U postgres -d DWMovistar -v ON_ERROR_STOP=1 -f /tmp/dim_tiempo.sql
```

Las comillas permiten utilizar el nombre del archivo que contiene espacios. Si los SQL están en otra carpeta, ajusta su ruta local.

Antes de cargar las facts, ejecuta en el DW:

```sql
SELECT sk_fecha, fecha
FROM public.dim_tiempo
WHERE sk_fecha IN (-1, 20200101, 20301231)
ORDER BY sk_fecha;

SELECT COUNT(*) AS dias_2020_2030
FROM public.dim_tiempo
WHERE fecha BETWEEN DATE '2020-01-01' AND DATE '2030-12-31';
```

El intervalo completo contiene **4,018 días**. Deben existir las claves de inicio y fin y, conforme al diseño de las cargas, el registro técnico `-1`. Una fecha referenciada por una fact debe existir previamente en `dim_tiempo`.

## 8. Configurar las conexiones de Python

`db_config.py` debe conservar los objetos `engine_origen`, `engine_destino` y la función `probar_conexiones`, utilizados por los ETL.

| Variable | Uso |
|---|---|
| `DB_USER`, `DB_PASSWORD` | Credenciales compartidas por ambas conexiones |
| `DB_HOST`, `DB_PORT` | Host y puerto comunes |
| `DB_HOST_ORIGEN`, `DB_PORT_ORIGEN` | Sobrescriben el host y puerto del origen |
| `DB_HOST_DESTINO`, `DB_PORT_DESTINO` | Sobrescriben el host y puerto del DW |
| `DB_ORIGEN`, `DB_DESTINO` | Nombres reales de las bases |

La versión actual permite defaults comentados para `5532` / `5432` y `DWMovistar` / `DWRoamingMovistarV2`. **Las variables de entorno tienen prioridad sobre esos defaults**, y las variables específicas de cada conexión tienen prioridad sobre las compartidas.

`os.getenv()` no carga automáticamente `.env`, `vlad.env` ni `.env.personal`. Compose pasa las variables al contenedor mediante `env_file`; para Python local, utiliza las variables de PowerShell del siguiente apartado. Esta guía no depende de una configuración particular de VS Code ni de instalar `python-dotenv`.

### 8.1. Python en Windows: entorno virtual

Si el entorno virtual todavía no existe:

```powershell
python --version
python -m venv venv
```

Activa el entorno e instala las dependencias:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip check
```

### 8.2. Python local hacia Docker o PostgreSQL local

Ejemplo para un Docker publicado en `5532`. Ejecuta este bloque en la **misma terminal** donde ejecutarás Python:

```powershell
$env:DB_USER = "postgres"
$env:DB_PASSWORD = "admin"
$env:DB_HOST = "localhost"
$env:DB_PORT = "5532"
$env:DB_HOST_ORIGEN = "localhost"
$env:DB_HOST_DESTINO = "localhost"
$env:DB_PORT_ORIGEN = "5532"
$env:DB_PORT_DESTINO = "5532"
$env:DB_ORIGEN = "Roaming"
$env:DB_DESTINO = "DWMovistar"

python db_config.py
```
<<<<<<< HEAD
=======

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
>>>>>>> 5da1743d954950ceb32b0bc2b847146535178115

Adapta usuario, contraseña, bases y puertos a tu instalación. Para PostgreSQL local estándar, cambia las **tres variables de puerto** a `5432`. Si publicaste Docker en `5540`, utiliza `5540`. Las variables definidas así pertenecen a la sesión de terminal; una nueva terminal necesita su configuración.

<<<<<<< HEAD
Para el entorno antiguo de dos contenedores, después de configurar las demás variables:

```powershell
$env:DB_PORT_ORIGEN = "5434"
$env:DB_PORT_DESTINO = "5433"
$env:DB_DESTINO = "DWRoamingMovistarV2"
python db_config.py
```

Desde Windows ambos hosts son `localhost`. Si Python se ejecuta dentro de la red Docker de esos dos servicios, utiliza sus nombres de servicio —por ejemplo `db_origen` y `db_destino`— y el puerto interno `5432` para cada uno. Esos nombres corresponden al Compose de dos servidores, no a la plantilla de un servidor de esta guía.

### 8.3. Python dentro de Docker

Esta opción no necesita activar el entorno virtual de Windows. Construye la imagen y verifica conexiones:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml build etl
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml run --rm etl db_config.py
```

La prueba debe indicar las bases elegidas en `postgres:5432`. En la modalidad mixta debe indicar `localhost` y el puerto publicado. Si usas exclusivamente Python local, no necesitas construir `etl`.

## 9. Ejecutar la carga inicial

Requisitos: origen restaurado, tablas del DW creadas, calendario lleno y ambas conexiones correctas. El archivo de entrada actual es **`orquestador.py`**.

Elige **una** modalidad:

```powershell
# Python local, con el entorno virtual y las variables configurados:
python orquestador.py
```

```powershell
# Python dentro de Docker:
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml run --rm etl orquestador.py
```

Las dimensiones se cargan antes de las facts. La carga inicial vacía y reconstruye las tablas que procesa; **no se utiliza para agregar solamente datos nuevos ni se repite entre pruebas SCD**.

## 10. Verificar la carga inicial

En la base origen:

```sql
SELECT
    (SELECT COUNT(*) FROM public.byte_gprs_sv) AS filas_gprs,
    (SELECT COUNT(*) FROM public.byte_portal_sv) AS filas_portal,
    (SELECT COUNT(*) FROM public.byte_camel_sv) AS filas_camel,
    (SELECT COUNT(*) FROM public.byte_gprs_sv)
      + (SELECT COUNT(*) FROM public.byte_portal_sv)
      + (SELECT COUNT(*) FROM public.byte_camel_sv) AS total_origen;
```

En el DW:

```sql
SELECT COUNT(*) AS total_fact_roaming FROM public.fact_roaming;
SELECT COUNT(*) AS total_fact_envio_tap FROM public.fact_envio_tap;
```

Conteos de referencia del respaldo ampliado, antes de los lotes de prueba, comprobados en la instalación de Vlad:

| Tabla | Registros |
|---|---:|
| `byte_gprs_sv` | 180,153 |
| `byte_portal_sv` | 80,066 |
| `byte_camel_sv` | 40,079 |
| Total de origen | 300,298 |
| `fact_roaming` después de la carga inicial | 300,298 |

Estos números corresponden a ese respaldo; no son una restricción para otros respaldos ni para el estado posterior a los diferenciales. La carga inicial de tráfico combina las tres tablas mediante `UNION ALL`. Con las dimensiones iniciales sin multiplicaciones en sus cruces, el total de hechos debe coincidir con el total de origen.

El conteo no valida por sí solo importes, asignación de llaves ni vigencias históricas. Tampoco debe confundirse con el número de filas que DBeaver ha descargado en su cuadrícula: utiliza `COUNT(*)` para conocer el total.

## 11. Ejecutar diferenciales

Usa los diferenciales corregidos, sus auxiliares y el orquestador correspondiente. Para la primera preparación de las pruebas, ejecuta una conciliación del estado inicial **antes de aplicar el primer lote SQL**:

```powershell
python orquestador_diferencial.py
```

Alternativa Docker:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml run --rm etl orquestador_diferencial.py
```

Después, el ciclo habitual es: aplicar datos de prueba en **el origen**, ejecutar el diferencial y revisar los resultados en **el DW**. Los cambios de dimensiones se procesan antes de las facts.

Los diferenciales corregidos pueden conciliar días completos cuando encuentran diferencias; no debe describírselos como procesos estrictamente de solo inserción en cualquier escenario. Los lotes de octubre están diseñados para demostrar datos nuevos, versiones SCD y conservación de hechos previos en ese escenario concreto.

### Pruebas SCD de octubre de 2026

Estos SQL son de prueba y deben aplicarse sobre una copia del respaldo final. Se requiere la versión de `orquestador_diferencial.py` que admite `--fecha-corte`.

| Orden | SQL completo en la base origen | Diferencial desde Python local |
|---|---|---|
| 1 | `01_Octubre_05_11_SCD.sql` | `python orquestador_diferencial.py --fecha-corte 2026-10-05` |
| 2 | `02_Octubre_15_21_SCD.sql` | `python orquestador_diferencial.py --fecha-corte 2026-10-15` |
| 3 | `03_Octubre_25_31_SCD.sql` | `python orquestador_diferencial.py --fecha-corte 2026-10-25` |

**Ejecuta un diferencial entre cada SQL y el siguiente.** No apliques los tres cambios de catálogo seguidos antes de ejecutar Python.

En Docker, por ejemplo para el primer lote:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml run --rm etl orquestador_diferencial.py --fecha-corte 2026-10-05
```

Repite ese formato con los cortes `2026-10-15` y `2026-10-25` después de sus respectivos SQL. El parámetro fija el corte de las dimensiones; **no filtra las facts por esa fecha ni cambia el reloj del equipo**.

Cada lote agrega 84 consumos y 7 TAP, y modifica atributos de operador, tarifas y tasa de cambio. Sin otros cambios pendientes, debe generar una nueva versión de operador, tres de tarifa y una de tasa. Si se parte de 300,298 consumos sin el lote opcional del 1–2 de octubre, los tres lotes agregan 252 y llevan el total a 300,550.

Ejecuta `04_Verificar_en_DW.sql` en la base destino para revisar versiones, importes e historial. Los comentarios antiguos pueden mencionar `Roaming2` y `DWRoamingMovistarV3`; selecciona las bases equivalentes de tu instalación.

Para comprobar idempotencia, repite el mismo diferencial sin cambios en el origen y con el mismo corte: no debe agregar versiones ni hechos adicionales. Después del lote C, repite con `2026-10-25`; no retrocedas al corte A ni uses una fecha actual anterior a las versiones simuladas. Mantén esta serie separada de los lotes anteriores de noviembre/enero, que asumían otros valores de catálogo. Consulta también el instructivo del paquete SCD.

## 12. Conectar desde DBeaver o pgAdmin

Para el ejemplo de Docker publicado en 5532:

| Campo | Origen | DW |
|---|---|---|
| Host | `localhost` | `localhost` |
| Puerto | `5532` | `5532` |
| Base | `Roaming` | `DWMovistar` |
| Usuario | `postgres` | `postgres` |
| Contraseña | La configurada | La configurada |

Si usas PostgreSQL local estándar, el puerto será normalmente `5432`; si elegiste otro puerto publicado, utiliza ese. En DBeaver crea una conexión PostgreSQL por base, prueba la conexión y expande `Schemas → public → Tables`.

Ejecuta los SQL que agregan datos y modifican catálogos en el origen. Ejecuta las verificaciones de dimensiones y facts en el DW.

## 13. Alternativa: todo en PostgreSQL local

No es obligatorio usar Docker para una prueba local. Con un servidor instalado y el puerto correcto, crea ambas bases si no existen. Ejemplo con usuario `postgres` y puerto `5432`:

```powershell
createdb -h localhost -p 5432 -U postgres -W Roaming
createdb -h localhost -p 5432 -U postgres -W DWMovistar
```

Restaura el origen vacío según su formato, eligiendo **solo una** alternativa:

```powershell
# Respaldo personalizado; sustituir el nombre del archivo:
pg_restore -h localhost -p 5432 -U postgres -W -d Roaming --no-owner --no-privileges --single-transaction --verbose ".\backups_bd\NOMBRE_REAL.backup"
```

```powershell
# Alternativa para un script SQL de texto:
psql -h localhost -p 5432 -U postgres -W -d Roaming -v ON_ERROR_STOP=1 -f ".\backups_bd\Roaming_Ampliado_Sintetico.sql"
```

Prepara el DW:

```powershell
psql -h localhost -p 5432 -U postgres -W -d DWMovistar -v ON_ERROR_STOP=1 -f ".\creacionDW-ver2.sql"
psql -h localhost -p 5432 -U postgres -W -d DWMovistar -v ON_ERROR_STOP=1 -f ".\dim_tiempo llenado.sql"
```

`-W` solicita la contraseña del servidor. Si las herramientas no se reconocen en la terminal, agrega el directorio `bin` de tu instalación PostgreSQL al PATH o utiliza la ruta completa de sus ejecutables. Después configura Python según el apartado 8, usando el puerto local, y sigue las mismas cargas y verificaciones.

## 14. Detener, reanudar y conservar los datos

En la plantilla personal:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml stop
```

Para reanudar:

```powershell
docker compose --env-file .env.personal -p roaming-personal -f compose.personal.yml up -d --wait postgres
```

El volumen conserva las bases. No vuelvas a restaurar ni a cargar inicialmente por haber detenido Docker. `down` elimina contenedores y redes del proyecto; `down -v` también elimina sus volúmenes y los datos guardados allí. No uses `-v` para una parada normal.

Los contenedores antiguos `movistar_transaccional` y `movistar_datawarehouse` pueden permanecer detenidos mientras se verifica el entorno nuevo. Mantenerlos no obliga a reutilizarlos ni a borrar sus volúmenes.

## 15. Trabajo en equipo y Git

Conserva las plantillas compartidas y utiliza archivos personales para tus ajustes. Para publicar solo plantillas, agrega al `.gitignore` existente las reglas que falten, sin reemplazarlo completo:

```gitignore
venv/
.venv/
__pycache__/
*.pyc
.env
.env.*
*.env
!.env.example
!.env.*.example
!*.env.example
```

Los Compose y Dockerfiles pueden versionarse cuando se quieren compartir. Si un archivo es exclusivamente personal, agrega su nombre exacto a `.gitignore` o a `.git/info/exclude`. No incluyas respaldos con información privada sin acuerdo del equipo.

**`.gitignore` no deja de rastrear archivos ya versionados ni impide que `git pull` actualice `db_config.py`.** Los ajustes personales deben mantenerse preferentemente en variables y archivos de entorno, en vez de depender de cambios locales permanentes sobre archivos compartidos. Publica plantillas sin credenciales reales.

## 16. Problemas frecuentes

| Mensaje o síntoma | Qué revisar |
|---|---|
| `open Dockerfile: no such file or directory` | Nombre y ubicación del Dockerfile; valor de `ETL_DOCKERFILE` o `build.dockerfile`. No debe tener una extensión `.txt` accidental. |
| Falta `requirements.txt` durante la construcción | Debe estar en el contexto de construcción, junto a los archivos del proyecto. |
| Una dependencia no se instala en Python 3.14 | Revisar sus versiones y compatibilidad con el Python de la imagen; no asumir que instalarse en Windows garantiza el mismo resultado en Linux. |
| `The system cannot find the file specified` al copiar | Verificar carpeta y nombre real del respaldo con `Get-ChildItem`. |
| `The input is a PostgreSQL custom-format dump` | Usar `pg_restore`, no `psql`, sobre la ruta del archivo copiado. |
| Puerto ocupado | Elegir otro puerto publicado y actualizar Python local y el cliente SQL. |
| Conexión local en 5432 cuando se esperaba 5532 | Revisar `DB_PORT`, `DB_PORT_ORIGEN`, `DB_PORT_DESTINO` y sus valores predeterminados. |
| `UnicodeDecodeError` al conectar | Puede ocultar otro error de conexión; comprobar primero host, puerto, base y credenciales. No prueba que los datos estén corruptos. |
| No existe `dim_operador` | Ejecutar `creacionDW-ver2.sql` en el DW correcto antes de la carga inicial. |
| Falta `sk_fecha=20200101` en `dim_tiempo` | Ejecutar el llenado del calendario y comprobar que la fecha existe antes de cargar facts. |
| DBeaver muestra pocas filas | Consultar `COUNT(*)`; las filas descargadas en la cuadrícula pueden ser solo una parte. |
| `unrecognized arguments: --fecha-corte` | Usar la versión del orquestador entregada con las pruebas SCD. |
| Tablas ya existentes al restaurar | Comprobar si el origen ya estaba preparado; no añadir opciones de borrado automáticamente. |

## 17. Referencias técnicas

- [Redes y puertos de Docker Compose](https://docs.docker.com/compose/how-tos/networking/).
- [Proyectos independientes de Compose](https://docs.docker.com/compose/how-tos/project-name/).
- [Variables y archivos de entorno en Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
- [Dockerfile alternativo en Compose](https://docs.docker.com/reference/compose-file/build/).
- [Contexto de construcción y exclusiones](https://docs.docker.com/build/concepts/context/).
- [Imagen oficial de PostgreSQL](https://hub.docker.com/_/postgres).
- [Imagen oficial de Python](https://hub.docker.com/_/python).
- [Restauración con pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).
- [Variables de entorno en PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_environment_variables).
- [Archivos ignorados y archivos ya rastreados por Git](https://git-scm.com/docs/gitignore).
=======
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

# Carga de Scripts iniciales para Contenedores de Docker

En el siguiente orden cargar la data de la base de datos Roaming y las de DWRoamingMovistarV2 despues de creado el contenedor de docker.

```
pg_restore roaming.sql -> DB Transaccional Roaming
psql creacionDW-ver2.sql -> DWRoamingMovistarV2
psql dim_tiempo llenado.sql -> DWRoamingMovistarV2
```

TODO: 
O Luego mover en un orden lexicografico los scripts que se utilizaran bajo un mismo orden en la carpeta init-db. 

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
>>>>>>> 5da1743d954950ceb32b0bc2b847146535178115
