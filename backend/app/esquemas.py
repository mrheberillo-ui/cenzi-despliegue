"""Contratos de entrada y salida de la API (Pydantic)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import config


class Consulta(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"texto": "ya pagué y no aparece mi pago"}]})
    texto: str = Field(..., description="Consulta del cliente en español")
    canal: Literal["web", "app", "whatsapp", "prueba"] = "web"

    @field_validator("texto")
    @classmethod
    def validar_texto(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("el texto no puede estar vacío ni contener sólo espacios")
        if len(v) > config.max_caracteres:
            raise ValueError(f"el texto excede {config.max_caracteres} caracteres")
        return v


class ConsultaLote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    textos: list[str] = Field(..., min_length=1, description="Lista de consultas")

    @field_validator("textos")
    @classmethod
    def validar_textos(cls, v: list[str]) -> list[str]:
        if len(v) > config.max_lote:
            raise ValueError(f"máximo {config.max_lote} textos por lote")
        limpios = []
        for i, t in enumerate(v):
            t = " ".join(t.split())
            if not t:
                raise ValueError(f"el texto {i} está vacío")
            if len(t) > config.max_caracteres:
                raise ValueError(f"el texto {i} excede {config.max_caracteres} caracteres")
            limpios.append(t)
        return limpios


class Alternativa(BaseModel):
    intencion: str
    confianza: float


class Clasificacion(BaseModel):
    id_solicitud: str
    intencion: str
    confianza: float
    accion: Literal["responder", "escalar"]
    motivo: str
    respuesta: str
    alternativas: list[Alternativa]
    umbral: float
    version_modelo: str
    latencia_ms: float


class ClasificacionLote(BaseModel):
    total: int
    resultados: list[Clasificacion]


class Salud(BaseModel):
    estado: str
    modelo_cargado: bool
    version_modelo: str | None = None
    entorno: str
    tiempo_activo_s: float
