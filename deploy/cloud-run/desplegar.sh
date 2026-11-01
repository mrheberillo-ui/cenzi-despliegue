#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Despliegue de Cenzi en Google Cloud Run (dos servicios: API y web).
# Requisitos: gcloud CLI autenticado (gcloud auth login) y un proyecto con
# facturación activa. Ejecutar desde la raíz del repositorio.
#
#   export PROYECTO=mi-proyecto-gcp
#   bash deploy/cloud-run/desplegar.sh
# ---------------------------------------------------------------------------
set -euo pipefail

PROYECTO=${PROYECTO:?Define PROYECTO con el ID de tu proyecto de Google Cloud}
REGION=${REGION:-northamerica-south1}          # México (Querétaro)
REPO=${REPO:-cenzi}
VERSION=${VERSION:-1.0.0}
REGISTRO="${REGION}-docker.pkg.dev/${PROYECTO}/${REPO}"

echo "==> 1/6 Proyecto y APIs"
gcloud config set project "$PROYECTO"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

echo "==> 2/6 Repositorio de imágenes en Artifact Registry"
gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" --repository-format=docker --location "$REGION" \
    --description "Imágenes de Cenzi"

echo "==> 3/6 Construcción de imágenes con Cloud Build (no requiere Docker local)"
gcloud builds submit backend  --tag "${REGISTRO}/cenzi-api:${VERSION}"
gcloud builds submit frontend --tag "${REGISTRO}/cenzi-web:${VERSION}"

echo "==> 4/6 Servicio de la API"
gcloud run deploy cenzi-api \
  --image "${REGISTRO}/cenzi-api:${VERSION}" \
  --region "$REGION" --port 8000 \
  --cpu 1 --memory 512Mi --concurrency 20 \
  --min-instances 0 --max-instances 3 --timeout 30 \
  --set-env-vars CENZI_ENV=cloudrun,CENZI_LOG_LEVEL=INFO,WEB_CONCURRENCY=2 \
  --allow-unauthenticated
API_URL=$(gcloud run services describe cenzi-api --region "$REGION" --format 'value(status.url)')

echo "==> 5/6 Servicio web (apunta a la API)"
gcloud run deploy cenzi-web \
  --image "${REGISTRO}/cenzi-web:${VERSION}" \
  --region "$REGION" --port 8080 \
  --cpu 1 --memory 256Mi --concurrency 80 \
  --min-instances 0 --max-instances 3 --timeout 30 \
  --set-env-vars "BACKEND_URL=${API_URL}" \
  --allow-unauthenticated
WEB_URL=$(gcloud run services describe cenzi-web --region "$REGION" --format 'value(status.url)')

echo "==> 6/6 Verificación"
curl -fsS "${API_URL}/ready" && echo
curl -fsS "${WEB_URL}/healthz" && echo
sh pruebas/smoke_test.sh "$WEB_URL" "$API_URL"
echo "Interfaz: ${WEB_URL}"
echo "API:      ${API_URL}/docs"
