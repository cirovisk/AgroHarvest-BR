# AgroHarvest BR - Agricultural Data Pipeline

This project is a data engineering solution focused on Brazilian agribusiness.

It integrates multiple public data sources and organizes them into a structured warehouse for analysis, auditing, and API consumption.

## Overview

The project consolidates data from:

1. RNC / CultivarWeb
2. PAM / IBGE
3. ZARC / MAPA
4. CONAB
5. Agrofit
6. SIPEAGRO
7. SIGEF
8. Open-Meteo
9. Remote-sensing NDVI

## Architecture

The workflow follows a modular Star Schema design with clear separation of concerns:

- data ingestion and cleaning
- PostgreSQL persistence
- FastAPI service layer
- Metabase dashboards

## Main characteristics

- Modular and scalable processing
- Integration of agricultural, climate, and regulatory data
- API for querying and auditability
- automated tests with Pytest
- Docker and Docker Compose containerization

## How to run

```bash
cp .env.example .env
docker-compose run --rm app
docker-compose up api
docker-compose run --rm test
```

## Documentation

- Visual architecture: `docs/ARCHITECTURE_VISUAL.md`
- Database metadata: `docs/DATABASE_METADATA.md`

## License and data

- Code under the MIT license
- Public datasets governed by the terms of each official source
