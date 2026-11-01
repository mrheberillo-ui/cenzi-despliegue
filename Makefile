# Atajos para trabajar con Cenzi. Uso: make <objetivo>
.PHONY: env construir levantar estado humo validar resiliencia logs apagar limpiar

env:            ## crea .env a partir de la plantilla
	@test -f .env || cp .env.example .env

construir: env  ## construye las dos imágenes (entrena el modelo y corre pytest)
	docker compose build

levantar: env   ## levanta el sistema en segundo plano
	docker compose up -d
	@echo "Interfaz: http://localhost:8080   API: http://localhost:8000/docs"

estado:         ## muestra contenedores y salud
	docker compose ps

humo:           ## prueba de humo
	sh pruebas/smoke_test.sh

validar:        ## validación de caja negra (integración, modelo, extremos y carga)
	mkdir -p resultados && docker cp cenzi-api:/app/models/conjunto_prueba.csv resultados/conjunto_prueba.csv
	python3 pruebas/validacion_sistema.py --prueba resultados/conjunto_prueba.csv --salida resultados

resiliencia:    ## pruebas de resiliencia y portabilidad
	bash pruebas/pruebas_resiliencia.sh

logs:           ## bitácoras de ambos contenedores
	docker compose logs -f

apagar:         ## detiene y elimina los contenedores
	docker compose down

limpiar: apagar ## elimina también las imágenes
	docker image rm cenzi-api:1.0.0 cenzi-web:1.0.0
