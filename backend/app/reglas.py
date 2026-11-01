"""Reglas de negocio que se aplican antes y después del modelo.

El modelo decide la intención; estas reglas deciden si es seguro responder:
- Datos sensibles (tarjeta, CLABE, CURP): se escalan y no se registran en texto claro.
- Palabras de queja o de aclaración: se escalan aunque el modelo tenga confianza alta.
- Texto sin letras suficientes (sólo números, símbolos o emojis): se escala.
"""
from __future__ import annotations

import re
import unicodedata

PATRON_TARJETA = re.compile(r"\b\d(?:[ -]?\d){14,15}\b")
PATRON_CLABE = re.compile(r"\b\d{18}\b")
PATRON_CURP = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", re.IGNORECASE)

PALABRAS_ESCALAR = (
    "queja", "condusef", "supervisor", "gerente", "demanda", "abogado", "profeco",
    "maltrato", "grosero", "amenaz", "acoso", "acosan", "engan", "fraude", "robo",
    "no reconozco", "cobro indebido", "cargo indebido", "me cobraron de mas",
    "cobraron doble", "descontaron dos veces", "aclaracion",
    # sentimiento negativo (léxico ajustado con el conjunto de validación, no con el de prueba)
    "pesim", "mala atencion", "mal servicio", "terrible", "horrible", "harto", "harta",
    "molest", "indignad", "inaceptable", "verguenza",
)


def normalizar(texto: str) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sin_acentos.lower().split())


def contiene_datos_sensibles(texto: str) -> bool:
    return bool(PATRON_TARJETA.search(texto) or PATRON_CLABE.search(texto) or PATRON_CURP.search(texto))


def enmascarar(texto: str) -> str:
    """Oculta datos sensibles antes de escribir el texto en la bitácora."""
    texto = PATRON_CURP.sub("[CURP]", texto)
    texto = PATRON_CLABE.sub("[CLABE]", texto)
    return PATRON_TARJETA.sub("[TARJETA]", texto)


def palabra_de_escalamiento(texto: str) -> str | None:
    t = normalizar(texto)
    for palabra in PALABRAS_ESCALAR:
        if palabra in t:
            return palabra
    return None


def letras_suficientes(texto: str, minimo: int = 3) -> bool:
    return sum(c.isalpha() for c in texto) >= minimo
