# Cenzi · Instrucciones de ejecución con Docker

Repositorio: https://github.com/mrheberillo-ui/cenzi-despliegue

## Archivos

| Archivo | Contenido |
|---|---|
| `backend/Dockerfile` | Imagen de la API (FastAPI + modelo). Dos etapas: genera los datos, entrena el modelo y ejecuta 68 pruebas; si una falla, la imagen no se construye. Corre con usuario sin privilegios. |
| `frontend/Dockerfile` | Imagen de la interfaz web y del proxy `/api/*` hacia la API. |
| `docker-compose.yml` | Levanta los dos contenedores juntos, con verificación de salud, reinicio automático y límites de recursos. |
| `.env.example` | Variables de configuración (se copia como `.env`). |

## Requisitos

- Docker Engine 24+ (o Docker Desktop) con Docker Compose v2
- 2 GB de RAM libres y conexión a internet (para descargar `python:3.13-slim` y los paquetes de Python)
- Puertos 8000 y 8080 libres

## Opción A: Docker Compose (recomendada)

```bash
git clone https://github.com/mrheberillo-ui/cenzi-despliegue.git
cd cenzi-despliegue
cp .env.example .env
docker compose up --build -d
```

La primera construcción tarda de 1 a 3 minutos.

## Opción B: solo Docker

```bash
docker network create cenzi-net
docker build -t cenzi-api:1.0.0 backend
docker build -t cenzi-web:1.0.0 frontend
docker run -d --name cenzi-api --network cenzi-net -p 8000:8000 cenzi-api:1.0.0
docker run -d --name cenzi-web --network cenzi-net -p 8080:8080 -e BACKEND_URL=http://cenzi-api:8000 cenzi-web:1.0.0
```

## Verificación

```bash
docker compose ps                 # ambos contenedores en estado (healthy)
sh pruebas/smoke_test.sh          # termina con "Prueba de humo correcta."
curl -s -X POST http://localhost:8080/api/v1/clasificar \
  -H "Content-Type: application/json" -d '{"texto":"cuándo es mi fecha de pago"}'
```

- Interfaz: http://localhost:8080
- Documentación de la API: http://localhost:8000/docs

Resultado esperado de `docker compose ps`:

```
NAME        IMAGE             STATUS                   PORTS
cenzi-api   cenzi-api:1.0.0   Up 21 seconds (healthy)  0.0.0.0:8000->8000/tcp
cenzi-web   cenzi-web:1.0.0   Up 15 seconds (healthy)  0.0.0.0:8080->8080/tcp
```

## Detener

```bash
docker compose down                      # opción A
docker rm -f cenzi-api cenzi-web         # opción B
docker network rm cenzi-net
```

## Versión pública (las mismas imágenes en la nube)

- Interfaz: https://cenzi-web.onrender.com
- API: https://cenzi-api.onrender.com/docs

La primera visita después de 15 minutos sin uso tarda cerca de un minuto en cargar.
