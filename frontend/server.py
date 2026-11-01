"""Servidor del frontend de Cenzi.

- Sirve los archivos estáticos de ./static
- Reenvía /api/* al backend definido en BACKEND_URL (proxy inverso), así el
  navegador sólo habla con un origen y no hay problemas de CORS.
- /healthz responde el estado del frontend y si alcanza al backend.

Sólo usa la biblioteca estándar de Python (sin dependencias).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").strip().rstrip("/")
if BACKEND_URL and "://" not in BACKEND_URL:  # se aceptan valores sin esquema (p. ej. cenzi-api.onrender.com)
    BACKEND_URL = "https://" + BACKEND_URL
PUERTO = int(os.getenv("PORT", "8080"))
ESTATICOS = Path(__file__).resolve().parent / "static"
TIEMPO_ESPERA = float(os.getenv("BACKEND_TIMEOUT_S", "10"))
MAX_CUERPO = 64 * 1024


class Manejador(SimpleHTTPRequestHandler):
    server_version = "CenziFrontend/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ESTATICOS), **kwargs)

    # ---------- utilidades ----------
    def _json(self, estado: int, cuerpo: dict) -> None:
        datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, formato, *args):
        print(json.dumps({"evento": "http_frontend", "cliente": self.client_address[0],
                          "linea": formato % args}), flush=True)

    # ---------- proxy ----------
    def _proxy(self, metodo: str) -> None:
        destino = BACKEND_URL + self.path[len("/api"):]
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > MAX_CUERPO:
            self._json(413, {"error": "cuerpo_demasiado_grande"})
            return
        cuerpo = self.rfile.read(largo) if largo else None
        encabezados = {"Content-Type": self.headers.get("Content-Type", "application/json")}
        if self.headers.get("X-Request-Id"):
            encabezados["X-Request-Id"] = self.headers["X-Request-Id"]
        req = urllib.request.Request(destino, data=cuerpo, method=metodo, headers=encabezados)
        try:
            with urllib.request.urlopen(req, timeout=TIEMPO_ESPERA) as r:
                self._reenviar(r.status, r.headers, r.read())
        except urllib.error.HTTPError as e:  # 4xx/5xx del backend: se reenvían tal cual
            self._reenviar(e.code, e.headers, e.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            self._json(502, {"error": "backend_no_disponible",
                             "mensaje": "El servicio de clasificación no responde. Intenta de nuevo en unos minutos.",
                             "detalle": str(getattr(e, "reason", e))})

    def _reenviar(self, estado, encabezados, datos: bytes) -> None:
        self.send_response(estado)
        for k in ("Content-Type", "X-Request-Id", "X-Process-Time-Ms"):
            if encabezados.get(k):
                self.send_header(k, encabezados[k])
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    # ---------- verbos ----------
    def do_GET(self):
        if self.path == "/healthz":
            try:
                with urllib.request.urlopen(BACKEND_URL + "/ready", timeout=3) as r:
                    backend = "listo" if r.status == 200 else f"http_{r.status}"
            except Exception:
                backend = "no_disponible"
            self._json(200, {"estado": "ok", "backend": backend, "backend_url": BACKEND_URL})
        elif self.path.startswith("/api/"):
            self._proxy("GET")
        elif self.path == "/openapi.json":  # lo pide Swagger UI cuando se abre /api/docs
            self.path = "/api/openapi.json"
            self._proxy("GET")
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy("POST")
        else:
            self._json(405, {"error": "metodo_no_permitido"})


class Servidor(ThreadingHTTPServer):
    # El valor por defecto (5) hace que con muchas conexiones simultáneas el sistema
    # operativo rechace las excedentes y el cliente reintente ~1 s después.
    request_queue_size = int(os.getenv("WEB_BACKLOG", "256"))
    daemon_threads = True


def main() -> None:
    servidor = Servidor(("0.0.0.0", PUERTO), Manejador)
    print(json.dumps({"evento": "frontend_iniciado", "puerto": PUERTO, "backend_url": BACKEND_URL}), flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
