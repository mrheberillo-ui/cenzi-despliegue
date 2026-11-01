"""Configuración leída de variables de entorno (12-factor)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _lista(valor: str) -> list[str]:
    return [v.strip() for v in valor.split(",") if v.strip()]


@dataclass(frozen=True)
class Config:
    ruta_modelo: Path = field(default_factory=lambda: Path(os.getenv("CENZI_MODEL_PATH", "models/cenzi_model.joblib")))
    umbral: float | None = field(default_factory=lambda: float(os.environ["CENZI_UMBRAL"]) if os.getenv("CENZI_UMBRAL") else None)
    max_caracteres: int = field(default_factory=lambda: int(os.getenv("CENZI_MAX_CARACTERES", "500")))
    max_lote: int = field(default_factory=lambda: int(os.getenv("CENZI_MAX_LOTE", "50")))
    origenes_cors: list[str] = field(default_factory=lambda: _lista(os.getenv("CENZI_CORS_ORIGINS", "*")))
    nivel_log: str = field(default_factory=lambda: os.getenv("CENZI_LOG_LEVEL", "INFO"))
    entorno: str = field(default_factory=lambda: os.getenv("CENZI_ENV", "local"))


config = Config()
