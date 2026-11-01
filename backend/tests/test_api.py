"""Pruebas funcionales de los endpoints (contrato de la API)."""
import pytest

CAMPOS = {"id_solicitud", "intencion", "confianza", "accion", "motivo", "respuesta",
          "alternativas", "umbral", "version_modelo", "latencia_ms"}


def test_F01_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok" and r.json()["modelo_cargado"] is True


def test_F02_ready(cliente):
    assert cliente.get("/ready").json() == {"estado": "listo"}


def test_F03_info(cliente):
    d = cliente.get("/v1/info").json()
    assert len(d["intenciones"]) == 13
    assert 0 < d["umbral"] < 1
    assert d["metricas_prueba"]["acierto_respondidas"] >= 0.90


def test_F04_intenciones(cliente):
    d = cliente.get("/v1/intenciones").json()
    escalar = {x["intencion"] for x in d if x["accion"] == "escalar"}
    assert escalar == {"queja", "aclaracion"}


def test_F05_contrato_respuesta(clasificar):
    r = clasificar("cuándo es mi fecha de pago")
    assert r.status_code == 200
    d = r.json()
    assert CAMPOS <= d.keys()
    assert len(d["alternativas"]) == 3
    confianzas = [a["confianza"] for a in d["alternativas"]]
    assert confianzas == sorted(confianzas, reverse=True) and sum(confianzas) <= 1.0001
    assert d["alternativas"][0]["intencion"] == d["intencion"]


@pytest.mark.parametrize("texto,esperada", [
    ("cuándo es mi fecha de pago", "fecha_pago"),
    ("dónde puedo pagar mi crédito", "medios_pago"),
    ("ya pagué y no aparece mi pago", "pago_no_reflejado"),
    ("cuánto debo de mi crédito", "consultar_saldo"),
    ("qué documentos necesito para un préstamo", "requisitos_credito"),
    ("a qué hora abren la sucursal", "sucursales_horarios"),
    ("quiero cambiar mi número de teléfono", "actualizar_datos"),
    ("cómo descargo mi estado de cuenta", "estado_cuenta"),
    ("cuál es la tasa de interés", "tasa_cat"),
    ("cómo va mi solicitud de crédito", "estatus_solicitud"),
    ("no puedo pagar este mes", "reestructura"),
])
def test_F06_intenciones_canonicas(clasificar, texto, esperada):
    d = clasificar(texto).json()
    assert d["intencion"] == esperada
    assert d["accion"] == "responder"


@pytest.mark.parametrize("texto", ["quiero poner una queja", "me cobraron de más", "hay un cargo que no reconozco"])
def test_F07_quejas_aclaraciones_escalan(clasificar, texto):
    assert clasificar(texto).json()["accion"] == "escalar"


def test_F08_lote(cliente):
    r = cliente.post("/v1/clasificar/lote", json={"textos": ["fecha de pago", "dónde pago", "queja"]})
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 3 and len({x["id_solicitud"] for x in d["resultados"]}) == 3


def test_F09_id_de_solicitud_propagado(cliente):
    r = cliente.post("/v1/clasificar", json={"texto": "fecha de pago"}, headers={"X-Request-Id": "prueba-123"})
    assert r.headers["x-request-id"] == "prueba-123"
    assert r.json()["id_solicitud"] == "prueba-123"


def test_F10_openapi(cliente):
    d = cliente.get("/openapi.json").json()
    assert {"/v1/clasificar", "/v1/clasificar/lote", "/health", "/ready"} <= d["paths"].keys()


def test_F11_metricas_cuentan(cliente):
    antes = cliente.get("/v1/metricas").json().get("consultas", 0)
    cliente.post("/v1/clasificar", json={"texto": "horario de sucursal"})
    assert cliente.get("/v1/metricas").json()["consultas"] == antes + 1


def test_F12_determinismo(clasificar):
    a, b = clasificar("dónde hay una sucursal").json(), clasificar("dónde hay una sucursal").json()
    assert (a["intencion"], a["confianza"]) == (b["intencion"], b["confianza"])
