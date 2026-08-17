FROM python:3.11-slim

WORKDIR /app

# Copiar dependencias primero para aprovechar la caché de Docker
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Ejecutar el ETL principal y luego el diferencial
CMD ["sh", "-c", "python db_config.py && \
                  python orquestador.py && \
                  python orquestador_diferencial.py"]
