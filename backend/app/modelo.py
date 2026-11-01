"""Carga del modelo y lógica de decisión (responder o escalar)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

from . import reglas


@dataclass
class Resultado:
    intencion: str
    confianza: float
    accion: str
    motivo: str
    respuesta: str
    alternativas: list[dict]
    latencia_ms: float


class ClasificadorCenzi:
    def __init__(self, ruta: Path, umbral: float | None = None):
        artefacto = joblib.load(ruta)
        self.pipeline = artefacto["pipeline"]
        self.umbral = float(umbral if umbral is not None else artefacto["umbral"])
        self.respuestas: dict[str, dict] = artefacto["respuestas"]
        self.version: str = artefacto["version"]
        self.metricas: dict = artefacto.get("metricas_prueba", {})
        self.clases: list[str] = [str(c) for c in self.pipeline.classes_]
        self.intenciones_escalar = {k for k, v in self.respuestas.items() if v["accion"] == "escalar"}

    def clasificar(self, texto: str) -> Resultado:
        t0 = time.perf_counter()
        proba = self.pipeline.predict_proba([texto])[0]
        orden = np.argsort(proba)[::-1]
        intencion = str(self.clases[orden[0]])
        confianza = float(proba[orden[0]])
        alternativas = [{"intencion": str(self.clases[i]), "confianza": round(float(proba[i]), 4)} for i in orden[:3]]

        accion, motivo = "responder", "confianza_suficiente"
        if not reglas.letras_suficientes(texto):
            accion, motivo = "escalar", "texto_sin_contenido"
        elif reglas.contiene_datos_sensibles(texto):
            accion, motivo = "escalar", "datos_sensibles"
        elif reglas.palabra_de_escalamiento(texto):
            accion, motivo = "escalar", "regla_queja_aclaracion"
        elif confianza < self.umbral:
            accion, motivo = "escalar", "confianza_baja"
        elif intencion in self.intenciones_escalar:
            accion, motivo = "escalar", "intencion_requiere_persona"

        if accion == "responder":
            respuesta = self.respuestas[intencion]["respuesta"]
        elif motivo == "datos_sensibles":
            respuesta = ("Por tu seguridad no compartas números de tarjeta, CLABE ni CURP en este canal. "
                         "Te comunicamos con un asesor que validará tu identidad.")
        elif motivo in ("regla_queja_aclaracion", "intencion_requiere_persona") and intencion in self.intenciones_escalar:
            respuesta = self.respuestas[intencion]["respuesta"]
        elif motivo == "regla_queja_aclaracion":
            respuesta = self.respuestas["queja"]["respuesta"]
        else:
            respuesta = ("No estoy seguro de haber entendido tu consulta. "
                         "Te comunico con una persona de nuestro equipo para ayudarte.")

        return Resultado(
            intencion=intencion,
            confianza=round(confianza, 4),
            accion=accion,
            motivo=motivo,
            respuesta=respuesta,
            alternativas=alternativas,
            latencia_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
