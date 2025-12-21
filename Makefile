SHELL := /bin/bash

.PHONY: bootstrap up down test smoke openapi baseline

bootstrap:
	bash scripts/tmp_rovodev_first_deploy.sh

up:
	docker compose up -d --build
	docker compose ps

down:
	docker compose down -v

test:
	pytest -q scripts/tests -q

smoke:
	pytest -q scripts/tests/test_smoke_api.py -q

openapi:
	python scripts/generate_openapi.py

baseline:
	API_URL?=http://localhost:8000 \
	python scripts/generate_deploy_baseline.py
