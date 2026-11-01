"""Casos extremos: entradas inválidas, ruido, seguridad y límites."""
import pytest


# ---------- validación de entrada (deben responder 422) ----------
@pytest.mark.parametrize("cuerpo,nombre", [
    ({"texto": ""}, "vacio"),
    ({"texto": "      "}, "solo_espacios"),
    ({"texto": "a" * 501}, "501_caracteres"),
    ({}, "sin_campo"),
    ({"texto": None}, "nulo"),
    ({"texto": 12345}, "numero_no_texto"),
    ({"texto": ["fecha"]}, "lista"),
    ({"texto": "hola", "extra": 1}, "campo_extra"),
    ({"texto": "hola", "canal": "fax"}, "canal_invalido"),
])
def test_E01_entradas_invalidas(cliente, cuerpo, nombre):
    r = cliente.post("/v1/clasificar", json=cuerpo)
    assert r.status_code == 422, nombre
    assert r.json()["error"] == "solicitud_invalida"


def test_E02_json_malformado(cliente):
    r = cliente.post("/v1/clasificar", content=b'{"texto": "hola"', headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_E03_metodo_no_permitido(cliente):
    assert cliente.get("/v1/clasificar").status_code == 405


def test_E04_ruta_inexistente(cliente):
    assert cliente.get("/v1/no-existe").status_code == 404


def test_E05_limite_exacto_500(clasificar):
    assert clasificar("cuándo pago " + "x" * 488).status_code == 200


def test_E06_lote_51_rechazado(cliente):
    r = cliente.post("/v1/clasificar/lote", json={"textos": ["hola"] * 51})
    assert r.status_code == 422


def test_E07_lote_con_vacio(cliente):
    assert cliente.post("/v1/clasificar/lote", json={"textos": ["hola", " "]}).status_code == 422


# ---------- ruido: deben escalar, nunca responder algo inventado ----------
@pytest.mark.parametrize("texto,motivo", [
    ("asdfgh qwerty zxcv", None),
    ("12345 678", "texto_sin_contenido"),
    ("?? !! ...", "texto_sin_contenido"),
    ("😀😀😀", "texto_sin_contenido"),
    ("a", "texto_sin_contenido"),
])
def test_E08_ruido_escala(clasificar, texto, motivo):
    d = clasificar(texto).json()
    assert d["accion"] == "escalar"
    if motivo:
        assert d["motivo"] == motivo


@pytest.mark.parametrize("texto", [
    "What is the weather today in London",
    "receta de pastel de chocolate",
    "quién ganó el partido de ayer",
])
def test_E09_fuera_de_dominio_escala(clasificar, texto):
    assert clasificar(texto).json()["accion"] == "escalar"


# ---------- variaciones del lenguaje del cliente ----------
@pytest.mark.parametrize("texto,esperada", [
    ("CUANDO ES MI FECHA DE PAGO", "fecha_pago"),
    ("cuando es mi fecha de pago", "fecha_pago"),
    ("cunado es mi fehca de pago", "fecha_pago"),
    ("hola buenas tardes, disculpe, ¿a qué hora abren la sucursal del centro? gracias", "sucursales_horarios"),
])
def test_E10_variaciones(clasificar, texto, esperada):
    assert clasificar(texto).json()["intencion"] == esperada


@pytest.mark.parametrize("texto", ["xfa dnd pago mi cred", "dnd pago mi cred"])
def test_E15_abreviatura_extrema_falla_segura(clasificar, texto):
    """Con abreviaturas extremas el modelo puede equivocarse; lo exigible es que no responda con confianza."""
    d = clasificar(texto).json()
    assert d["intencion"] == "medios_pago" or d["accion"] == "escalar"


# ---------- seguridad ----------
@pytest.mark.parametrize("texto", [
    "mi tarjeta es 4152 3135 7788 9012 y no pasa el pago",
    "mi clabe 012180001234567891 para el depósito",
    "mi curp es GOML850101HQTRRS09",
])
def test_E11_datos_sensibles_escalan(clasificar, texto):
    d = clasificar(texto).json()
    assert d["accion"] == "escalar" and d["motivo"] == "datos_sensibles"
    assert "4152" not in d["respuesta"]


@pytest.mark.parametrize("texto", [
    "<script>alert('x')</script> fecha de pago",
    "'; DROP TABLE clientes; --",
    "{{7*7}} ${jndi:ldap://x}",
])
def test_E12_inyeccion_no_rompe(clasificar, texto):
    r = clasificar(texto)
    assert r.status_code == 200
    assert "<script>" not in r.json()["respuesta"]


def test_E13_consulta_mixta_toma_una(clasificar):
    d = clasificar("quiero saber mi saldo y también me cobraron de más").json()
    assert d["accion"] == "escalar"  # la parte de aclaración manda


def test_E14_palabra_queja_con_confianza_alta(clasificar):
    d = clasificar("dónde está la sucursal para poner una queja").json()
    assert d["accion"] == "escalar" and d["motivo"] == "regla_queja_aclaracion"
