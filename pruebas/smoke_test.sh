#!/usr/bin/env sh
# Prueba de humo: verifica en segundos que los dos contenedores funcionan.
# Uso: sh pruebas/smoke_test.sh [URL_WEB] [URL_API]
WEB=${1:-http://localhost:8080}
API=${2:-http://localhost:8000}
fallas=0

revisar() { # nombre, comando, texto esperado
  salida=$(eval "$2" 2>&1)
  if echo "$salida" | grep -q "$3"; then echo "[PASA] $1"; else echo "[FALLA] $1 -> $salida"; fallas=$((fallas+1)); fi
}

revisar "API /health"                 "curl -s $API/health"                 '"estado":"ok"'
revisar "API /ready"                  "curl -s $API/ready"                  '"listo"'
revisar "Web /healthz alcanza la API" "curl -s $WEB/healthz"                '"backend": "listo"'
revisar "Web sirve la interfaz"       "curl -s $WEB/"                       'id="formulario"'
revisar "Clasificar vía proxy"        "curl -s -X POST $WEB/api/v1/clasificar -H 'Content-Type: application/json' -d '{\"texto\":\"cuándo es mi fecha de pago\"}'" '"intencion":"fecha_pago"'
revisar "Queja se escala"             "curl -s -X POST $WEB/api/v1/clasificar -H 'Content-Type: application/json' -d '{\"texto\":\"quiero poner una queja\"}'" '"accion":"escalar"'
revisar "Texto vacío -> 422"          "curl -s -o /dev/null -w '%{http_code}' -X POST $WEB/api/v1/clasificar -H 'Content-Type: application/json' -d '{\"texto\":\"\"}'" '422'

[ $fallas -eq 0 ] && echo "Prueba de humo correcta." || { echo "$fallas verificaciones fallaron."; exit 1; }
