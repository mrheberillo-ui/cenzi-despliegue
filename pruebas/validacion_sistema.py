"""Validación de caja negra del sistema Cenzi en ejecución (contenedores).

Todas las peticiones pasan por el frontend (http://localhost:8080/api/...),
así se prueba la cadena completa navegador -> frontend -> backend -> modelo.

Bloques:
  1. Integración: salud, endpoints y contrato.
  2. Modelo en el contenedor: el conjunto de prueba (nunca visto) vía /v1/clasificar/lote.
  3. Casos extremos por HTTP.
  4. Carga: concurrencia 1, 10 y 50.

Uso:
    python pruebas/validacion_sistema.py --web http://localhost:8080 \
        --prueba backend/models/conjunto_prueba.csv --salida resultados/
Sólo usa la biblioteca estándar.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RESULTADOS: list[dict] = []


def peticion(metodo: str, url: str, cuerpo=None, crudo: bytes | None = None, timeout=15):
    datos = crudo if crudo is not None else (json.dumps(cuerpo).encode() if cuerpo is not None else None)
    req = urllib.request.Request(url, data=datos, method=metodo, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            texto = r.read().decode()
            estado = r.status
    except urllib.error.HTTPError as e:
        texto, estado = e.read().decode(), e.code
    ms = (time.perf_counter() - t0) * 1000
    try:
        j = json.loads(texto)
    except json.JSONDecodeError:
        j = None
    return estado, j, ms, texto


def registrar(bloque, id_, descripcion, esperado, obtenido, ok):
    RESULTADOS.append({"bloque": bloque, "id": id_, "descripcion": descripcion,
                       "esperado": esperado, "obtenido": obtenido, "resultado": "PASA" if ok else "FALLA"})
    print(f"[{'PASA' if ok else 'FALLA'}] {id_} {descripcion} -> {obtenido}")


# ------------------------------------------------------------------ 1
def integracion(web: str):
    e, j, _, _ = peticion("GET", f"{web}/healthz")
    registrar("integracion", "I01", "Frontend responde y alcanza al backend", "200 · backend=listo",
              f"{e} · backend={j and j.get('backend')}", e == 200 and j.get("backend") == "listo")
    e, _, _, html = peticion("GET", f"{web}/")
    registrar("integracion", "I02", "Interfaz web servida", "200 · contiene formulario",
              f"{e} · formulario={'formulario' in html}", e == 200 and 'id="formulario"' in html)
    e, j, _, _ = peticion("GET", f"{web}/api/health")
    registrar("integracion", "I03", "GET /health vía proxy", "200 · modelo_cargado=true",
              f"{e} · modelo_cargado={j and j.get('modelo_cargado')}", e == 200 and j["modelo_cargado"])
    e, j, _, _ = peticion("GET", f"{web}/api/ready")
    registrar("integracion", "I04", "GET /ready vía proxy", "200 · listo", f"{e} · {j}", e == 200)
    e, j, _, _ = peticion("GET", f"{web}/api/v1/info")
    registrar("integracion", "I05", "GET /v1/info", "13 intenciones y umbral",
              f"{e} · {len(j['intenciones'])} intenciones · umbral {j['umbral']}", e == 200 and len(j["intenciones"]) == 13)
    e, j, _, _ = peticion("GET", f"{web}/api/v1/intenciones")
    registrar("integracion", "I06", "GET /v1/intenciones", "queja y aclaración = escalar",
              f"{e} · escalar={[x['intencion'] for x in j if x['accion']=='escalar']}",
              e == 200 and {x["intencion"] for x in j if x["accion"] == "escalar"} == {"queja", "aclaracion"})
    e, j, ms, _ = peticion("POST", f"{web}/api/v1/clasificar", {"texto": "ya pagué y no aparece mi pago"})
    campos = {"id_solicitud", "intencion", "confianza", "accion", "motivo", "respuesta", "alternativas", "umbral", "version_modelo", "latencia_ms"}
    registrar("integracion", "I07", "POST /v1/clasificar: contrato completo", "200 · 10 campos · pago_no_reflejado",
              f"{e} · {j['intencion']} · {j['confianza']:.3f} · {ms:.1f} ms", e == 200 and campos <= j.keys() and j["intencion"] == "pago_no_reflejado")
    e, j, _, _ = peticion("POST", f"{web}/api/v1/clasificar/lote", {"textos": ["fecha de pago", "dónde pago", "quiero poner una queja"]})
    registrar("integracion", "I08", "POST /v1/clasificar/lote", "200 · total=3",
              f"{e} · total={j and j.get('total')} · acciones={[r['accion'] for r in j['resultados']]}", e == 200 and j["total"] == 3)
    e, j, _, _ = peticion("GET", f"{web}/api/openapi.json")
    registrar("integracion", "I09", "Especificación OpenAPI disponible", "200 · rutas /v1/*",
              f"{e} · {len(j['paths'])} rutas", e == 200 and "/v1/clasificar" in j["paths"])
    e, j, _, _ = peticion("GET", f"{web}/api/v1/metricas")
    registrar("integracion", "I10", "GET /v1/metricas cuenta consultas", "200 · consultas > 0",
              f"{e} · consultas={j.get('consultas')}", e == 200 and j.get("consultas", 0) > 0)


# ------------------------------------------------------------------ 2
def modelo_en_contenedor(web: str, ruta_prueba: Path) -> dict:
    with ruta_prueba.open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    predichos = []
    for i in range(0, len(filas), 50):
        bloque = filas[i:i + 50]
        e, j, _, _ = peticion("POST", f"{web}/api/v1/clasificar/lote", {"textos": [x["texto"] for x in bloque]}, timeout=60)
        assert e == 200, j
        predichos += j["resultados"]
    n = len(filas)
    correctas = sum(p["intencion"] == f["intencion"] for p, f in zip(predichos, filas))
    responde = [(p, f) for p, f in zip(predichos, filas) if p["accion"] == "responder"]
    ok_resp = sum(p["intencion"] == f["intencion"] for p, f in responde)
    sensibles = [(p, f) for p, f in zip(predichos, filas) if f["accion"] == "escalar"]
    sens_esc = sum(p["accion"] == "escalar" for p, _ in sensibles)
    por_motivo: dict[str, int] = {}
    for p in predichos:
        por_motivo[p["motivo"]] = por_motivo.get(p["motivo"], 0) + 1
    m = {
        "n": n, "accuracy": correctas / n, "cobertura": len(responde) / n,
        "acierto_respondidas": ok_resp / len(responde), "error_total": (len(responde) - ok_resp) / n,
        "quejas_aclaraciones": len(sensibles), "quejas_aclaraciones_escaladas": sens_esc / len(sensibles),
        "por_motivo": por_motivo,
        "errores_respondidos": [{"texto": f["texto"], "real": f["intencion"], "predicha": p["intencion"],
                                 "confianza": p["confianza"]} for p, f in responde if p["intencion"] != f["intencion"]],
    }
    registrar("modelo", "M01", f"Accuracy en {n} consultas de prueba (vía contenedor)", "≥ 0.75", f"{m['accuracy']:.3f}", m["accuracy"] >= 0.75)
    registrar("modelo", "M02", "Acierto en lo que responde", "≥ 90 %", f"{m['acierto_respondidas']:.1%}", m["acierto_respondidas"] >= 0.90)
    registrar("modelo", "M03", "Cobertura (consultas resueltas sin persona)", "≥ 50 %", f"{m['cobertura']:.1%}", m["cobertura"] >= 0.50)
    registrar("modelo", "M04", "Respuestas equivocadas sobre el total", "≤ 5 %", f"{m['error_total']:.1%}", m["error_total"] <= 0.05)
    registrar("modelo", "M05", "Quejas y aclaraciones que llegan a una persona", "≥ 95 %", f"{m['quejas_aclaraciones_escaladas']:.1%}", m["quejas_aclaraciones_escaladas"] >= 0.95)
    return m


# ------------------------------------------------------------------ 3
CASOS = [
    ("E01", "Texto vacío", {"texto": ""}, 422, None),
    ("E02", "Sólo espacios", {"texto": "     "}, 422, None),
    ("E03", "501 caracteres", {"texto": "a" * 501}, 422, None),
    ("E04", "Exactamente 500 caracteres", {"texto": "cuándo pago " + "x" * 488}, 200, None),
    ("E05", "Campo texto ausente", {}, 422, None),
    ("E06", "Texto numérico (no cadena)", {"texto": 12345}, 422, None),
    ("E07", "Campo no permitido", {"texto": "hola", "extra": 1}, 422, None),
    ("E08", "Canal inválido", {"texto": "hola", "canal": "fax"}, 422, None),
    ("E09", "Galimatías", {"texto": "asdfgh qwerty zxcv"}, 200, "escalar"),
    ("E10", "Sólo números", {"texto": "12345 678"}, 200, "escalar"),
    ("E11", "Sólo emojis", {"texto": "😀😀😀"}, 200, "escalar"),
    ("E12", "Un carácter", {"texto": "a"}, 200, "escalar"),
    ("E13", "Inglés (fuera de idioma)", {"texto": "What is the weather today in London"}, 200, "escalar"),
    ("E14", "Fuera de dominio", {"texto": "receta de pastel de chocolate"}, 200, "escalar"),
    ("E15", "Mayúsculas sostenidas", {"texto": "CUANDO ES MI FECHA DE PAGO"}, 200, "responder"),
    ("E16", "Errores de tecleo", {"texto": "cunado es mi fehca de pago"}, 200, "responder"),
    ("E17", "Abreviatura extrema", {"texto": "xfa dnd pago mi cred"}, 200, "escalar_o_correcta"),
    ("E18", "Consulta larga con cortesías", {"texto": "hola buenas tardes, disculpe, ¿a qué hora abren la sucursal del centro? gracias"}, 200, "responder"),
    ("E19", "Número de tarjeta", {"texto": "mi tarjeta es 4152 3135 7788 9012 y no pasa el pago"}, 200, "escalar"),
    ("E20", "CLABE interbancaria", {"texto": "mi clabe 012180001234567891 para el depósito"}, 200, "escalar"),
    ("E21", "CURP", {"texto": "mi curp es GOML850101HQTRRS09"}, 200, "escalar"),
    ("E22", "Etiqueta <script>", {"texto": "<script>alert('x')</script> fecha de pago"}, 200, None),
    ("E23", "Inyección SQL", {"texto": "'; DROP TABLE clientes; --"}, 200, None),
    ("E24", "Plantillas / JNDI", {"texto": "{{7*7}} ${jndi:ldap://x}"}, 200, None),
    ("E25", "Consulta mixta (saldo + cobro indebido)", {"texto": "quiero saber mi saldo y también me cobraron de más"}, 200, "escalar"),
    ("E26", "Queja dentro de pregunta de sucursal", {"texto": "dónde está la sucursal para poner una queja"}, 200, "escalar"),
]


def casos_extremos(web: str):
    for id_, desc, cuerpo, estado_esp, accion_esp in CASOS:
        e, j, _, _ = peticion("POST", f"{web}/api/v1/clasificar", cuerpo)
        ok = e == estado_esp
        obtenido = str(e)
        if e == 200 and j:
            obtenido += f" · {j['accion']} · {j['intencion']} ({j['confianza']:.2f}) · {j['motivo']}"
            if accion_esp == "escalar_o_correcta":
                ok = ok and (j["accion"] == "escalar" or j["intencion"] == "medios_pago")
            elif accion_esp:
                ok = ok and j["accion"] == accion_esp
            if "script" in cuerpo.get("texto", ""):
                ok = ok and "<script>" not in j["respuesta"]
        elif e == 422 and j:
            obtenido += " · " + "; ".join(d["mensaje"] for d in j["detalles"])
        esperado = f"{estado_esp}" + (f" · {accion_esp}" if accion_esp else "")
        registrar("extremos", id_, desc, esperado, obtenido, ok)
    # extremos que no son de contenido
    e, j, _, _ = peticion("POST", f"{web}/api/v1/clasificar", crudo=b'{"texto": "hola"')
    registrar("extremos", "E27", "JSON mal formado", "422", f"{e} · {j and j['detalles'][0]['mensaje']}", e == 422)
    e, j, _, _ = peticion("POST", f"{web}/api/v1/clasificar/lote", {"textos": ["hola"] * 51})
    registrar("extremos", "E28", "Lote de 51 textos (límite 50)", "422", f"{e} · {j and j['detalles'][0]['mensaje']}", e == 422)
    e, j, _, _ = peticion("POST", f"{web}/api/v1/clasificar", crudo=b"x" * (70 * 1024))
    registrar("extremos", "E29", "Cuerpo de 70 KB (límite del proxy 64 KB)", "413", f"{e}", e == 413)
    e, _, _, _ = peticion("GET", f"{web}/api/v1/no-existe")
    registrar("extremos", "E30", "Ruta inexistente", "404", f"{e}", e == 404)
    e, _, _, _ = peticion("GET", f"{web}/api/v1/clasificar")
    registrar("extremos", "E31", "Método GET en endpoint POST", "405", f"{e}", e == 405)


# ------------------------------------------------------------------ 4
TEXTOS_CARGA = ["cuándo es mi fecha de pago", "dónde puedo pagar", "ya pagué y no aparece", "cuánto debo",
                "a qué hora abren", "me cobraron de más", "requisitos para un crédito", "asdf"]


def carga(web: str, concurrencia: int, total: int) -> dict:
    def una(i):
        e, _, ms, _ = peticion("POST", f"{web}/api/v1/clasificar", {"texto": TEXTOS_CARGA[i % len(TEXTOS_CARGA)]})
        return e, ms
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrencia) as ex:
        res = list(ex.map(una, range(total)))
    dur = time.perf_counter() - t0
    lat = sorted(ms for _, ms in res)
    errores = sum(e != 200 for e, _ in res)
    r = {"concurrencia": concurrencia, "solicitudes": total, "errores": errores, "duracion_s": round(dur, 2),
         "rps": round(total / dur, 1), "p50_ms": round(statistics.median(lat), 1),
         "p95_ms": round(lat[int(0.95 * (len(lat) - 1))], 1), "p99_ms": round(lat[int(0.99 * (len(lat) - 1))], 1),
         "max_ms": round(lat[-1], 1)}
    registrar("carga", f"C{concurrencia:02d}", f"{total} solicitudes con concurrencia {concurrencia}",
              "0 errores · p95 ≤ 300 ms", f"{errores} errores · p95 {r['p95_ms']} ms · {r['rps']} sol/s",
              errores == 0 and r["p95_ms"] <= 300)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default="http://localhost:8080")
    ap.add_argument("--prueba", default="backend/models/conjunto_prueba.csv")
    ap.add_argument("--salida", default="resultados")
    ap.add_argument("--sin-carga", action="store_true")
    a = ap.parse_args()
    salida = Path(a.salida); salida.mkdir(parents=True, exist_ok=True)

    integracion(a.web)
    metricas = modelo_en_contenedor(a.web, Path(a.prueba))
    casos_extremos(a.web)
    cargas = [] if a.sin_carga else [carga(a.web, c, n) for c, n in ((1, 200), (10, 500), (50, 1000))]

    resumen = {
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(RESULTADOS), "pasan": sum(r["resultado"] == "PASA" for r in RESULTADOS),
        "modelo": metricas, "carga": cargas, "pruebas": RESULTADOS,
    }
    (salida / "validacion_sistema.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    with (salida / "validacion_sistema.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(RESULTADOS[0].keys()))
        w.writeheader(); w.writerows(RESULTADOS)
    print(f"\n{resumen['pasan']} de {resumen['total']} pruebas pasan. Resultados en {salida}/")


if __name__ == "__main__":
    main()
