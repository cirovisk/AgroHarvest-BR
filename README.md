# AgroHarvest BR

Pipeline de dados agrícolas com integração de fontes públicas, modelagem analítica e API para consumo dos dados.  
Selecione o idioma:

- [Português](./README.pt-BR.md)
- [English](./README.en.md)

## Destaques

- Integração de RNC, PAM, ZARC, CONAB, Agrofit, SIPEAGRO, SIGEF e Open-Meteo
- Pipeline modular com PostgreSQL, FastAPI e Metabase
- Modelagem em Star Schema com foco em escalabilidade
- Documentação visual em `docs/ARCHITECTURE_VISUAL.md`

## Stack

Python, PostgreSQL, SQLAlchemy, FastAPI, Uvicorn, SlowAPI, Docker, Docker Compose, Pytest, GitHub Actions e Metabase.

## Estrutura

- `src/`: API, pipeline, modelagem e orquestração
- `docs/`: documentação técnica, metadata e diagramas
- `tests/`: suíte de testes
- `docker/`: imagem e dependências do ambiente
