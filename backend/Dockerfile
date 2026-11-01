# ---------------------------------------------------------------------------
# Cenzi API · imagen del backend (FastAPI + scikit-learn)
# Construcción en dos etapas:
#   1) "entrenamiento": instala dependencias, genera el dataset sintético,
#      entrena el modelo y ejecuta las pruebas (si fallan, falla el build).
#   2) "ejecucion": copia sólo el código, el modelo y las dependencias de
#      ejecución; corre como usuario sin privilegios.
# ---------------------------------------------------------------------------
ARG BASE_IMAGE=python:3.13-slim

FROM ${BASE_IMAGE} AS entrenamiento
ARG PIP_EXTRA_ARGS=""
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
WORKDIR /build
COPY requirements.txt requirements-dev.txt ./
RUN python -m pip install ${PIP_EXTRA_ARGS} --prefix=/install -r requirements.txt \
 && python -m pip install ${PIP_EXTRA_ARGS} -r requirements-dev.txt
COPY scripts/ scripts/
COPY data/respuestas_aprobadas_cenzi.csv data/
RUN python scripts/generar_dataset.py && python scripts/entrenar.py
COPY app/ app/
COPY tests/ tests/
RUN python -m pytest -q

FROM ${BASE_IMAGE} AS ejecucion
LABEL org.opencontainers.image.title="cenzi-api" \
      org.opencontainers.image.description="API de clasificación de consultas de Cenzi (MSCA2102)" \
      org.opencontainers.image.version="1.0.0"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PORT=8000 CENZI_MODEL_PATH=/app/models/cenzi_model.joblib CENZI_ENV=contenedor
WORKDIR /app
COPY --from=entrenamiento /install /usr/local
COPY --from=entrenamiento /build/models/ models/
COPY --from=entrenamiento /build/data/ data/
COPY app/ app/
RUN useradd --system --uid 10001 --no-create-home cenzi 2>/dev/null || echo "cenzi:x:10001:10001::/app:/sbin/nologin" >> /etc/passwd
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/ready', timeout=2)"
# Forma shell para que ${PORT} se expanda (Cloud Run / Render / Azure inyectan PORT)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY:-2} --no-access-log"]
