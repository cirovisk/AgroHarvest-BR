.PHONY: help env setup build up down ingest api test lint format logs shell status validate-db

help:
	@echo "Available commands (cultivares v1):"
	@echo "  make env         - Create .env from .env.example when missing"
	@echo "  make setup       - Prepare .env and build Docker images"
	@echo "  make build       - Build the project's Docker images"
	@echo "  make up          - Start the main services in the background (PostgreSQL and API)"
	@echo "  make ingest      - Run the full ingestion pipeline"
	@echo "  make api         - Start only PostgreSQL and API"
	@echo "  make down        - Stop services and remove containers"
	@echo "  make test        - Run all unit tests through Docker"
	@echo "  make lint        - Roda checagem de estilo/qualidade (Ruff) e checagem de tipos (Mypy)"
	@echo "  make format      - Run automatic code formatting with Ruff"
	@echo "  make logs        - Exibe e acompanha os logs dos containers"
	@echo "  make shell       - Abre um shell interativo bash no container de desenvolvimento"
	@echo "  make status      - Show the current container runtime status"
	@echo "  make validate-db - Validate required PostgreSQL tables after ingestion"

env:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; else echo ".env already exists"; fi

setup: env build

build:
	docker compose build

up:
	docker compose up -d

api:
	docker compose up -d postgres api

ingest:
	docker compose run --rm app

down:
	docker compose down

test:
	docker compose run --rm test

lint:
	docker compose run --rm app ruff check src/
	docker compose run --rm app mypy --ignore-missing-imports src/

format:
	docker compose run --rm app ruff format src/

logs:
	docker compose logs -f

shell:
	docker compose run --rm app bash

status:
	docker compose ps

validate-db:
	docker compose run --rm app python scripts/validate_database.py
