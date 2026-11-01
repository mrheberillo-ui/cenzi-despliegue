#!/usr/bin/env bash
# Pruebas de resiliencia, configuración y portabilidad de los contenedores.
# Requiere: el sistema levantado con `docker compose up -d`.
# Uso: bash pruebas/pruebas_resiliencia.sh
set -u
WEB=http://localhost:8080
API=http://localhost:8000
IMG_API=${IMG_API:-cenzi-api:1.0.0}
fallas=0
ok()   { echo "[PASA] $1 -> $2"; }
mal()  { echo "[FALLA] $1 -> $2"; fallas=$((fallas+1)); }
esperar_listo() { # url, segundos máximos
  local t0=$(date +%s.%N)
  for _ in $(seq 1 $(( $2 * 5 ))); do curl -sf "$1" >/dev/null 2>&1 && { printf "%.2f" "$(echo "$(date +%s.%N) - $t0" | bc)"; return 0; }; sleep 0.2; done
  echo "-1"; return 1
}

echo "== R01 Backend detenido: el frontend sigue en pie y responde 502 controlado =="
docker stop cenzi-api >/dev/null
salud=$(curl -s $WEB/healthz); codigo=$(curl -s -o /tmp/r01.json -w '%{http_code}' -X POST $WEB/api/v1/clasificar -H 'Content-Type: application/json' -d '{"texto":"fecha de pago"}')
ui=$(curl -s -o /dev/null -w '%{http_code}' $WEB/)
if [[ "$salud" == *no_disponible* && "$codigo" == 502 && "$ui" == 200 ]]; then ok R01 "healthz=no_disponible · clasificar=502 · interfaz=200 · $(cat /tmp/r01.json | head -c 120)"; else mal R01 "$salud $codigo $ui"; fi

echo "== R02 Backend reiniciado: recuperación sin reiniciar el frontend =="
docker start cenzi-api >/dev/null
t=$(esperar_listo "$WEB/api/ready" 60)
codigo=$(curl -s -o /dev/null -w '%{http_code}' -X POST $WEB/api/v1/clasificar -H 'Content-Type: application/json' -d '{"texto":"fecha de pago"}')
[[ "$codigo" == 200 ]] && ok R02 "listo de nuevo en ${t}s · clasificar=200" || mal R02 "$codigo"

echo "== R03 Caída abrupta del proceso (kill -9): la política restart lo levanta =="
reinicios0=$(docker inspect -f '{{.RestartCount}}' cenzi-api)
kill -9 "$(docker inspect -f '{{.State.Pid}}' cenzi-api)"
sleep 1
t=$(esperar_listo "$API/ready" 60)
reinicios1=$(docker inspect -f '{{.RestartCount}}' cenzi-api)
[[ "$t" != "-1" && $reinicios1 -gt $reinicios0 ]] && ok R03 "reinicio automático #$reinicios1 · listo en ${t}s" || mal R03 "t=$t reinicios=$reinicios1"

echo "== R04 Modelo ausente: el contenedor arranca, /ready=503 y healthcheck unhealthy =="
docker rm -f cenzi-sin-modelo >/dev/null 2>&1
docker run -d --name cenzi-sin-modelo -e CENZI_MODEL_PATH=/app/models/no-existe.joblib -p 18000:8000 $IMG_API >/dev/null
sleep 4
h=$(curl -s localhost:18000/health); r=$(curl -s -o /dev/null -w '%{http_code}' localhost:18000/ready)
c=$(curl -s -o /dev/null -w '%{http_code}' -X POST localhost:18000/v1/clasificar -H 'Content-Type: application/json' -d '{"texto":"hola"}')
sleep 40; estado=$(docker inspect -f '{{.State.Health.Status}}' cenzi-sin-modelo)
[[ "$h" == *'"modelo_cargado":false'* && "$r" == 503 && "$c" == 503 && "$estado" == unhealthy ]] && ok R04 "health=modelo_cargado:false · ready=503 · clasificar=503 · healthcheck=$estado" || mal R04 "$h $r $c $estado"
docker rm -f cenzi-sin-modelo >/dev/null

echo "== R05 Configuración por variables de entorno (umbral) =="
docker rm -f cenzi-umbral >/dev/null 2>&1
docker run -d --name cenzi-umbral -e CENZI_UMBRAL=0.95 -p 18001:8000 $IMG_API >/dev/null
esperar_listo localhost:18001/ready 30 >/dev/null
u=$(curl -s localhost:18001/v1/info | python3 -c "import sys,json;print(json.load(sys.stdin)['umbral'])")
a=$(curl -s -X POST localhost:18001/v1/clasificar -H 'Content-Type: application/json' -d '{"texto":"cunado es mi fehca de pago"}' | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['accion'],d['confianza'])")
[[ "$u" == 0.95 && "$a" == escalar* ]] && ok R05 "umbral=$u · consulta con confianza ${a#* } ahora se escala" || mal R05 "$u $a"
docker rm -f cenzi-umbral >/dev/null

echo "== R06 Portabilidad: puerto inyectado por la plataforma (PORT=9000, como Cloud Run) =="
docker rm -f cenzi-puerto >/dev/null 2>&1
docker run -d --name cenzi-puerto -e PORT=9000 -p 19000:9000 $IMG_API >/dev/null
t=$(esperar_listo localhost:19000/ready 30)
[[ "$t" != "-1" ]] && ok R06 "escucha en 9000 · listo en ${t}s" || mal R06 "no respondió"
docker rm -f cenzi-puerto >/dev/null

echo "== R07 Seguridad: usuario sin privilegios y sistema de archivos de la app protegido =="
u=$(docker inspect -f '{{.Config.User}}' cenzi-api)
w=$(docker exec cenzi-api python -c "open('/app/app/x','w')" 2>&1 | tail -1)
[[ "$u" == 10001 && "$w" == *Permission* ]] && ok R07 "usuario=$u · escritura en /app/app denegada" || mal R07 "$u $w"

echo "== R08 Arranque en frío del contenedor de la API (docker run → /ready) =="
docker rm -f cenzi-frio >/dev/null 2>&1
t0=$(date +%s.%N); docker run -d --name cenzi-frio -p 18002:8000 $IMG_API >/dev/null
t=$(esperar_listo localhost:18002/ready 30)
[[ "$t" != "-1" ]] && ok R08 "listo en $(printf "%.2f" "$(echo "$(date +%s.%N) - $t0" | bc)") s" || mal R08 "sin respuesta"
docker rm -f cenzi-frio >/dev/null

echo "== R09 Sistema completo sigue sano al terminar =="
s=$(curl -s $WEB/healthz)
[[ "$s" == *listo* ]] && ok R09 "$s" || mal R09 "$s"

[[ $fallas -eq 0 ]] && echo "Todas las pruebas de resiliencia pasan." || { echo "$fallas pruebas fallaron."; exit 1; }
