FROM python:3.14.3-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto
COPY . .

# Comprobar conexiones por defecto
CMD ["python", "db_config.py"]