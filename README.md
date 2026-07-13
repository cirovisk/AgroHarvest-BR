# AgroHarvest BR

Agricultural data pipeline with public-source integration, analytical modeling, and an API for data consumption.  
Select a language:

- [Português](./README.pt-BR.md)
- [English](./README.en.md)

## Highlights

- Integration of RNC, PAM, ZARC, CONAB, Agrofit, SIPEAGRO, SIGEF, and Open-Meteo
- Modular pipeline with PostgreSQL, FastAPI, and Metabase
- Star Schema modeling focused on scalability
- Visual documentation in `docs/ARCHITECTURE_VISUAL.md`

## Stack

Python, PostgreSQL, SQLAlchemy, FastAPI, Uvicorn, SlowAPI, Docker, Docker Compose, Pytest, GitHub Actions, and Metabase.

## Operational Quickstart

```bash
make setup
make ingest
make validate-db
make api
```

`make validate-db` checks whether the required PostgreSQL tables exist and contain data after ingestion.

## Structure

- `src/`: API, pipeline, modeling, and orchestration
- `docs/`: technical documentation, metadata, and diagrams
- `tests/`: test suite
- `docker/`: image and environment dependencies
