# Cenzi · Clasificador de consultas de clientes, contenerizado y listo para la nube

Solución técnica completa y desplegable del caso **Cenzi** (Financiera Cenzontle, empresa ficticia, MSCA2102 · Tecmilenio).
Un cliente escribe su consulta en español; el sistema reconoce la intención entre **13 posibles**, devuelve una **respuesta aprobada** o **escala a una persona** cuando la confianza es baja, cuando es una queja o aclaración, o cuando el texto trae datos sensibles.

```
Navegador ──► cenzi-web (8080) ──/api/*──► cenzi-api (8000) ──► modelo TF-IDF + regresión logística
              interfaz + proxy              FastAPI + reglas de negocio
```

| Componente | Tecnología | Imagen | Puerto |
|---|---|---|---|
| Backend (API REST) | Python 3.13 · FastAPI · scikit-learn | `cenzi-api:1.0.0` | 8000 |
| Frontend (interfaz + proxy inverso) | HTML/CSS/JS · servidor Python (biblioteca estándar) | `cenzi-web:1.0.0` | 8080 |

> Datos **sintéticos** (1 404 consultas generadas por script). No es un sistema productivo.

---

## Inicio rápido (3 comandos)

Requisitos: Docker Engine 24+ con Docker Compose v2, 2 GB de RAM libres y conexión a internet (para descargar `python:3.13-slim` y los paquetes de PyPI).

```bash
git clone https://github.com/<tu-usuario>/<tu-repo>.git && cd <tu-repo>
cp .env.example .env
docker compose up --build -d
```

Abre **http://localhost:8080** (interfaz) y **http://localhost:8000/docs** (documentación interactiva de la API).
La primera construcción tarda entre 1 y 3 minutos: el build del backend **genera el dataset, entrena el modelo y ejecuta 68 pruebas**; si alguna falla, la imagen no se construye.

Verificación en segundos:

```bash
docker compose ps                 # ambos contenedores en estado (healthy)
sh pruebas/smoke_test.sh          # 7 verificaciones → "Prueba de humo correcta."
```

Apagar: `docker compose down`.

### Sin Docker Compose (sólo Docker)

```bash
docker network create cenzi-net
docker build -t cenzi-api:1.0.0 backend
docker build -t cenzi-web:1.0.0 frontend
docker run -d --name cenzi-api --network cenzi-net -p 8000:8000 cenzi-api:1.0.0
docker run -d --name cenzi-web --network cenzi-net -p 8080:8080 -e BACKEND_URL=http://cenzi-api:8000 cenzi-web:1.0.0
```

---

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Liveness: el proceso responde y reporta si el modelo está cargado |
| GET | `/ready` | Readiness: 200 si el modelo está listo, 503 si no |
| GET | `/v1/info` | Versión del modelo, umbral, intenciones y métricas de prueba |
| GET | `/v1/intenciones` | Catálogo de intenciones y su acción (responder / escalar) |
| POST | `/v1/clasificar` | Clasifica una consulta |
| POST | `/v1/clasificar/lote` | Clasifica hasta 50 consultas |
| GET | `/v1/metricas` | Contadores de uso desde el arranque |
| GET | `/docs` · `/openapi.json` | Documentación OpenAPI (Swagger UI) |

Desde el frontend, la misma API se consume como `/api/<ruta>` (por ejemplo `/api/v1/clasificar`).

```bash
curl -s -X POST http://localhost:8080/api/v1/clasificar \
  -H "Content-Type: application/json" \
  -d '{"texto": "ya pagué y no aparece mi pago"}'
```

```json
{
  "id_solicitud": "c1aa3402dfc0",
  "intencion": "pago_no_reflejado",
  "confianza": 0.9975,
  "accion": "responder",
  "motivo": "confianza_suficiente",
  "respuesta": "Los pagos por transferencia se reflejan el mismo día hábil ...",
  "alternativas": [{"intencion": "pago_no_reflejado", "confianza": 0.9975}, "..."],
  "umbral": 0.49,
  "version_modelo": "1.0.0",
  "latencia_ms": 9.64
}
```

Errores: `422` con `{"error": "solicitud_invalida", "detalles": [{"campo", "mensaje"}]}` · `502` del frontend si la API no responde · `503` si el modelo no está cargado.

### Lógica de decisión

| Orden | Condición | Acción | `motivo` |
|---|---|---|---|
| 1 | Menos de 3 letras (números, símbolos, emojis) | escalar | `texto_sin_contenido` |
| 2 | Número de tarjeta, CLABE o CURP | escalar (y se enmascara en bitácora) | `datos_sensibles` |
| 3 | Palabras de queja, aclaración o enojo | escalar | `regla_queja_aclaracion` |
| 4 | Confianza < umbral (0.49) | escalar | `confianza_baja` |
| 5 | Intención `queja` o `aclaracion` | escalar | `intencion_requiere_persona` |
| 6 | En otro caso | responder con la respuesta aprobada | `confianza_suficiente` |

---

## Configuración (variables de entorno)

| Variable | Servicio | Valor por defecto | Uso |
|---|---|---|---|
| `PORT` | ambos | 8000 / 8080 | Puerto de escucha (Cloud Run, Render y Azure lo inyectan) |
| `CENZI_UMBRAL` | api | umbral guardado con el modelo (0.49) | Sobrescribe el umbral de confianza |
| `CENZI_MAX_CARACTERES` | api | 500 | Largo máximo de una consulta |
| `CENZI_MAX_LOTE` | api | 50 | Máximo de consultas por lote |
| `CENZI_CORS_ORIGINS` | api | `*` | Orígenes permitidos si se llama la API directo desde un navegador |
| `CENZI_LOG_LEVEL` | api | INFO | Nivel de bitácora (JSON por línea) |
| `WEB_CONCURRENCY` | api | 2 | Procesos de uvicorn |
| `BACKEND_URL` | web | `http://api:8000` | URL de la API a la que el frontend reenvía `/api/*` |
| `BACKEND_TIMEOUT_S` | web | 10 | Tiempo máximo de espera a la API |

---

## Pruebas

| Suite | Dónde corre | Qué cubre | Resultado |
|---|---|---|---|
| `backend/tests/` (pytest, 68 casos) | Dentro del build de Docker | Contrato de la API, intenciones, reglas, casos extremos | 68 / 68 |
| `pruebas/smoke_test.sh` | Contra el sistema levantado | 7 verificaciones rápidas de punta a punta | 7 / 7 |
| `pruebas/validacion_sistema.py` | Contra el sistema levantado, vía frontend | Integración (10), modelo con datos no vistos (5), casos extremos (31), carga (3) | 47 / 49 |
| `pruebas/pruebas_resiliencia.sh` | Contra el sistema levantado | Caída y recuperación, reinicio automático, modelo ausente, configuración, portabilidad, seguridad | 9 / 9 |

Las dos pruebas que no pasan se documentan en el reporte de validación: quejas y aclaraciones escaladas **87.0 %** (meta 95 %) y p95 de **347 ms** con 50 usuarios simultáneos por instancia (meta 300 ms).

Modelo en el contenedor (282 consultas nunca vistas, partición por frase base): accuracy **0.823**, acierto en lo que responde **95.4 %**, cobertura **54.3 %**, respuestas equivocadas **2.5 %** del total.

```bash
make construir && make levantar && make humo && make validar && make resiliencia
```

---

## Despliegue en la nube

### Versión pública (Render)

| Servicio | URL |
|---|---|
| Interfaz web | https://cenzi-web.onrender.com |
| API (documentación) | https://cenzi-api.onrender.com/docs |

Desplegado con el blueprint [`render.yaml`](render.yaml): dos servicios web gratuitos construidos desde los Dockerfile de este repositorio. Render → **New → Blueprint** → elegir el repositorio → escribir en `BACKEND_URL` la URL de la API.

> Plan gratuito: si nadie usa el servicio durante 15 minutos se suspende, y la siguiente visita tarda alrededor de un minuto en despertarlo. La interfaz espera hasta 60 s a la API.

### Google Cloud Run

Estrategia recomendada para un uso continuo: **Google Cloud Run** (contenedores sin servidor, región `northamerica-south1`, México), dos servicios independientes. Script listo:

```bash
export PROYECTO=<id-de-tu-proyecto>
bash deploy/cloud-run/desplegar.sh
```

Paso a paso, requisitos, alternativas (Azure Container Apps, Render) y operación: **[docs/MANUAL_DESPLIEGUE.md](docs/MANUAL_DESPLIEGUE.md)**.

---

## Estructura

```
.
├── backend/
│   ├── app/                 main.py (endpoints) · modelo.py · reglas.py · esquemas.py · config.py
│   ├── data/                respuestas_aprobadas_cenzi.csv (el dataset se genera en el build)
│   ├── scripts/             generar_dataset.py · entrenar.py
│   ├── tests/               pytest: test_api.py · test_casos_extremos.py · test_modelo.py
│   ├── Dockerfile           2 etapas: entrenamiento + ejecución (usuario sin privilegios)
│   └── requirements*.txt
├── frontend/
│   ├── static/              index.html · app.js · styles.css
│   ├── server.py            sirve la interfaz y hace de proxy hacia la API
│   └── Dockerfile
├── pruebas/                 smoke_test.sh · validacion_sistema.py · pruebas_resiliencia.sh
├── deploy/cloud-run/        desplegar.sh
├── docs/                    MANUAL_DESPLIEGUE.md · evidencias/ (capturas)
├── resultados/              bitácoras y resultados de la última validación
├── .github/workflows/ci.yml construcción y pruebas en cada push
├── docker-compose.yml · .env.example · Makefile
```

## Reproducibilidad

- Versiones fijas en `requirements.txt` (FastAPI 0.162.0, uvicorn 0.54.0, scikit-learn 1.9.1, joblib 1.6.0) y en la imagen base (`python:3.13-slim`).
- Semilla 42 en la generación de datos, la partición y el modelo: cada build produce el mismo modelo y las mismas métricas.
- El conjunto de prueba nunca se usa para entrenar ni para elegir el umbral; se guarda en `/app/models/conjunto_prueba.csv` dentro de la imagen para validar el contenedor.
