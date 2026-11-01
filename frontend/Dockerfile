# ---------------------------------------------------------------------------
# Cenzi Web · imagen del frontend
# Sirve la interfaz estática y reenvía /api/* al backend (BACKEND_URL).
# Sólo usa la biblioteca estándar de Python: no instala dependencias.
# ---------------------------------------------------------------------------
ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}
LABEL org.opencontainers.image.title="cenzi-web" \
      org.opencontainers.image.description="Interfaz web de Cenzi con proxy hacia la API" \
      org.opencontainers.image.version="1.0.0"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 BACKEND_URL=http://api:8000
WORKDIR /web
COPY server.py ./
COPY static/ static/
RUN useradd --system --uid 10001 --no-create-home cenzi 2>/dev/null || echo "cenzi:x:10001:10001::/web:/sbin/nologin" >> /etc/passwd
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/healthz', timeout=2)"
CMD ["python", "server.py"]
