# AgroHarvest BR - Pipeline de Dados Agrícolas

Este projeto é uma solução de Engenharia de Dados voltada para o agronegócio brasileiro.

Ele integra múltiplas fontes públicas e organiza os dados em um data warehouse estruturado para análise, auditoria e consumo via API.

## Visão geral

O projeto consolida dados de:

1. RNC / CultivarWeb
2. PAM / IBGE
3. ZARC / MAPA
4. CONAB
5. Agrofit
6. SIPEAGRO
7. SIGEF
8. Open-Meteo
9. NDVI por sensoriamento remoto

## Arquitetura

O fluxo segue uma arquitetura modular baseada em Star Schema e separação por camadas:

- ingestão e limpeza de dados
- persistência em PostgreSQL
- API com FastAPI
- visualização em Metabase

## Características principais

- Processamento modular e escalável
- Integração entre dados agrícolas, climáticos e regulatórios
- API para consulta e auditoria
- testes automatizados com Pytest
- containerização com Docker e Docker Compose

## Como executar

```bash
cp .env.example .env
docker-compose run --rm app
docker-compose up api
docker-compose run --rm test
```

## Documentação

- Arquitetura visual: `docs/ARCHITECTURE_VISUAL.md`
- Metadados do banco: `docs/DATABASE_METADATA.md`

## Licença e dados

- Código sob licença MIT
- Dados públicos sob regras e termos de uso das fontes oficiais
