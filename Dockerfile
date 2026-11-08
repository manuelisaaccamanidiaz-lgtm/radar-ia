# Imagen del entorno de desarrollo de Radar IA
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Instala las dependencias del proyecto (se reutilizan en cada reconstrucción)
COPY radar_ia/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r /tmp/requirements.txt

EXPOSE 8501
