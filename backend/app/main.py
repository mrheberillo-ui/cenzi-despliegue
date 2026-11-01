"""API REST de Cenzi: clasificación de consultas de clientes.

Endpoints
---------
GET  /health                 liveness (el proceso responde)
GET  /ready                  readiness (el modelo está cargado)
GET  /v1/info                versión, umbral, intenciones y métricas de prueba
GET  /v1/intenciones         catálogo de intenciones y su acción
POST /v1/clasificar          clasifica una consulta
POST /v1/clasificar/lote     clasifica hasta CENZI_MAX_LOTE consultas
GET  /v1/metricas            contadores de uso desde el arranque
GET  /docs                   documentación OpenAPI (Swagger UI)
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import reglas
from .config import config
from .esquemas import Clasificacion, ClasificacionLote, Consulta, ConsultaLote, Salud
from .modelo import ClasificadorCenzi

logging.basicConfig(level=config.nivel_log, format="%(message)s")
log = logging.getLogger("cenzi")

ESTADO: dict = {"modelo": None, "inicio": time.time(), "error_carga": None}
CONTADORES: Counter = Counter()
CANDADO = Lock()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    try:
        ESTADO["modelo"] = ClasificadorCenzi(config.ruta_modelo, config.umbral)
        log.info(json.dumps({"evento": "modelo_cargado", "ruta": str(config.ruta_modelo),
                             "version": ESTADO["modelo"].version, "umbral": ESTADO["modelo"].umbral}))
    except Exception as e:  # el contenedor arranca, pero /ready responde 503
        ESTADO["error_carga"] = str(e)
        log.error(json.dumps({"evento": "error_carga_modelo", "detalle": str(e)}))
    yield


app = FastAPI(
    title="Cenzi API",
    version="1.0.0",
    description="Clasificador de consultas de clientes de Financiera Cenzontle (caso académico, datos sintéticos).",
    lifespan=ciclo_de_vida,
)
app.add_middleware(CORSMiddleware, allow_origins=config.origenes_cors, allow_methods=["GET", "POST"],
                   allow_headers=["*"])


@app.middleware("http")
async def bitacora(request: Request, call_next):
    id_solicitud = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.id_solicitud = id_solicitud
    t0 = time.perf_counter()
    respuesta = await call_next(request)
    ms = round((time.perf_counter() - t0) * 1000, 2)
    respuesta.headers["x-request-id"] = id_solicitud
    respuesta.headers["x-process-time-ms"] = str(ms)
    with CANDADO:
        CONTADORES[f"http_{respuesta.status_code}"] += 1
    log.info(json.dumps({"evento": "http", "id": id_solicitud, "metodo": request.method,
                         "ruta": request.url.path, "estado": respuesta.status_code, "ms": ms}))
    return respuesta


TRADUCCIONES = {
    "missing": "campo obligatorio",
    "string_type": "debe ser texto",
    "list_type": "debe ser una lista",
    "extra_forbidden": "campo no permitido",
    "literal_error": "valor no permitido",
    "json_invalid": "JSON mal formado",
    "too_short": "la lista no puede estar vacía",
}


def _traducir(e: dict) -> str:
    if e.get("type") == "value_error":
        return str(e.get("msg", "")).replace("Value error, ", "")
    return TRADUCCIONES.get(e.get("type"), str(e.get("msg", "")))


@app.exception_handler(RequestValidationError)
async def error_validacion(request: Request, exc: RequestValidationError):
    errores = [{"campo": "cuerpo" if e.get("type") == "json_invalid"
                else ".".join(str(p) for p in e.get("loc", [])[1:]) or "cuerpo",
                "mensaje": _traducir(e)} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "solicitud_invalida", "detalles": errores,
                                                  "id_solicitud": getattr(request.state, "id_solicitud", None)})


def _modelo() -> ClasificadorCenzi:
    if ESTADO["modelo"] is None:
        raise HTTPException(status_code=503, detail="modelo no disponible")
    return ESTADO["modelo"]


def _clasificar(texto: str, id_solicitud: str, canal: str = "web") -> Clasificacion:
    m = _modelo()
    r = m.clasificar(texto)
    with CANDADO:
        CONTADORES["consultas"] += 1
        CONTADORES[f"accion_{r.accion}"] += 1
        CONTADORES[f"motivo_{r.motivo}"] += 1
    log.info(json.dumps({"evento": "clasificacion", "id": id_solicitud, "canal": canal,
                         "texto": reglas.enmascarar(texto)[:120], "intencion": r.intencion,
                         "confianza": r.confianza, "accion": r.accion, "motivo": r.motivo}, ensure_ascii=False))
    return Clasificacion(id_solicitud=id_solicitud, umbral=m.umbral, version_modelo=m.version, **r.__dict__)


@app.get("/health", response_model=Salud, tags=["operación"])
def health():
    m = ESTADO["modelo"]
    return Salud(estado="ok", modelo_cargado=m is not None, version_modelo=m.version if m else None,
                 entorno=config.entorno, tiempo_activo_s=round(time.time() - ESTADO["inicio"], 1))


@app.get("/ready", tags=["operación"])
def ready():
    if ESTADO["modelo"] is None:
        return JSONResponse(status_code=503, content={"estado": "no_listo", "detalle": ESTADO["error_carga"]})
    return {"estado": "listo"}


@app.get("/v1/info", tags=["modelo"])
def info():
    m = _modelo()
    return {"version_modelo": m.version, "umbral": m.umbral, "intenciones": m.clases,
            "max_caracteres": config.max_caracteres, "max_lote": config.max_lote,
            "metricas_prueba": m.metricas}


@app.get("/v1/intenciones", tags=["modelo"])
def intenciones():
    m = _modelo()
    return [{"intencion": k, "accion": v["accion"]} for k, v in sorted(m.respuestas.items())]


@app.post("/v1/clasificar", response_model=Clasificacion, tags=["modelo"])
def clasificar(consulta: Consulta, request: Request):
    return _clasificar(consulta.texto, request.state.id_solicitud, consulta.canal)


@app.post("/v1/clasificar/lote", response_model=ClasificacionLote, tags=["modelo"])
def clasificar_lote(lote: ConsultaLote, request: Request):
    base = request.state.id_solicitud
    resultados = [_clasificar(t, f"{base}-{i}") for i, t in enumerate(lote.textos)]
    return ClasificacionLote(total=len(resultados), resultados=resultados)


@app.get("/v1/metricas", tags=["operación"])
def metricas():
    with CANDADO:
        return {"tiempo_activo_s": round(time.time() - ESTADO["inicio"], 1), **dict(CONTADORES)}
