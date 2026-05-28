.PHONY: build up down test lint format logs shell status help

help:
	@echo "Comandos disponíveis (cultivares v1):"
	@echo "  make build       - Constrói as imagens Docker do projeto"
	@echo "  make up          - Sobe os serviços principais em background (PostgreSQL e API)"
	@echo "  make down        - Derruba os serviços e remove os containers"
	@echo "  make test        - Executa todos os testes unitários via Docker"
	@echo "  make lint        - Roda checagem de estilo/qualidade (Ruff) e checagem de tipos (Mypy)"
	@echo "  make format      - Roda a formatação automática de código com Ruff"
	@echo "  make logs        - Exibe e acompanha os logs dos containers"
	@echo "  make shell       - Abre um shell interativo bash no container de desenvolvimento"
	@echo "  make status      - Exibe o status atual de execução dos containers"

build:
	docker compose build

up:
	docker compose up -d

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
