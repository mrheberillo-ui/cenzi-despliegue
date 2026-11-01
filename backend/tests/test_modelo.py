"""Pruebas del modelo y de las reglas (sin pasar por HTTP)."""
import json
from pathlib import Path

from app import reglas

RAIZ = Path(__file__).resolve().parents[1]
METRICAS = json.loads((RAIZ / "models" / "metricas.json").read_text(encoding="utf-8"))


def test_M01_metas_de_negocio_en_prueba():
    p = METRICAS["prueba"]
    assert p["acierto_respondidas"] >= 0.90   # meta: acierto en lo que responde
    assert p["cobertura"] >= 0.50              # meta: contención
    assert p["error_total"] <= 0.05            # meta: respuestas equivocadas


def test_M02_particion_sin_fuga():
    assert METRICAS["n_entrenamiento"] + METRICAS["n_validacion"] + METRICAS["n_prueba"] == METRICAS["n_total"]


def test_M03_trece_clases():
    assert len(METRICAS["clases"]) == 13


def test_M04_enmascarar():
    t = reglas.enmascarar("tarjeta 4152 3135 7788 9012 curp GOML850101HQTRRS09")
    assert "4152" not in t and "GOML" not in t and "[TARJETA]" in t and "[CURP]" in t


def test_M05_normalizar():
    assert reglas.normalizar("  ÁRBOL   Pequeño ") == "arbol pequeno"


def test_M06_letras_suficientes():
    assert not reglas.letras_suficientes("123 !!")
    assert reglas.letras_suficientes("pago")


def test_M07_enmascarar_conserva_el_texto_alrededor():
    assert reglas.enmascarar("mi tarjeta es 4152 3135 7788 9012 y no pasa") == "mi tarjeta es [TARJETA] y no pasa"
    assert reglas.enmascarar("tarjeta 4152-3135-7788-9012.") == "tarjeta [TARJETA]."
