# AgroHarvest BR - Architecture and Modeling

This document details the data structure and information flow of the AgroHarvest BR project.

## 1. Data Model (Star Schema)

The Entity-Relationship Diagram (ERD) below details how dimensions and facts relate in PostgreSQL. This model was designed to optimize analytical queries and reduce data redundancy.

```mermaid
erDiagram
    DIM-CULTURA ||--o{ FATO-CULTIVAR : "has"
    DIM-CULTURA ||--o{ FATO-PAM : "produces"
    DIM-CULTURA ||--o{ FATO-ZARC : "risk"
    DIM-CULTURA ||--o{ FATO-CONAB : "estimate"
    DIM-CULTURA ||--o{ FATO-AGROFIT : "inputs"
    DIM-CULTURA ||--o{ FATO-SIGEF : "seeds"
    
    DIM-MUNICIPIO ||--o{ FATO-PAM : "location"
    DIM-MUNICIPIO ||--o{ FATO-ZARC : "location"
    DIM-MUNICIPIO ||--o{ FATO-METEOROLOGIA : "weather"
    DIM-MUNICIPIO ||--o{ FATO-FERTILIZANTES : "establishments"
    DIM-MUNICIPIO ||--o{ FATO-SIGEF : "location"
    DIM-MUNICIPIO ||--o{ FATO-NDVI : "satellite"
    
    DIM-MANTENEDOR ||--o{ FATO-CULTIVAR : "maintains"

    DIM-CULTURA {
        int id_cultura PK
        string nome_padronizado "Ex: soybean, corn"
    }
    DIM-MUNICIPIO {
        int id_municipio PK
        string codigo_ibge "7 digits"
        string nome
        string uf
    }
    DIM-MANTENEDOR {
        int id_mantenedor PK
        string nome
        string setor
    }
    FATO-PAM {
        int id_cultura FK
        int id_municipio FK
        int ano PK
        float area_plantada_ha
        float qtde_produzida_ton
    }
    FATO-ZARC {
        int id_cultura FK
        int id_municipio FK
        string tipo_solo PK
        string periodo_plantio PK
        string risco_climatico
    }
    FATO-METEOROLOGIA {
        int id_municipio FK
        datetime data PK
        float precipitacao_mm
        float temp_media_c
    }
    FATO-NDVI {
        int id_municipio FK
        int ano PK
        float ndvi_max_safra
        float ndvi_mean_safra
    }
```

## 2. Data Flow (ETL Pipeline - Registry Pattern)

The pipeline uses the **Registry Pattern**: each data source is a self-contained class (`extract + clean + load`) registered through the `@register` decorator. The orchestrator discovers and runs sources automatically without manual configuration.

```mermaid
graph LR
    subgraph "Gov.br Sources"
        MAPA["MAPA (ZARC, RNC, SIGEF)"]
        IBGE["IBGE (SIDRA/PAM)"]
        INMET["INMET (Weather)"]
        CONAB["CONAB (Crop Seasons)"]
    end

    subgraph "Pipeline Engine (Python/Docker)"
        REG["Registry (@register)"]
        SRC["Sources (E+C+L)"]
        DIM["Dimensions"]
        UTL["Utils (upsert)"]
    end

    subgraph "Storage & BI"
        PG[(PostgreSQL DW)]
        API["FastAPI"]
        MB["Metabase"]
    end

    MAPA --> SRC
    IBGE --> SRC
    INMET --> SRC
    CONAB --> SRC
    
    SRC --> REG
    REG --> DIM
    DIM --> PG
    SRC --> UTL
    UTL --> PG
    
    PG --> API
    PG --> MB
```

### Directory Structure

```
src/
├── main.py                     # Generic orchestrator (~65 lines)
├── db/
│   └── manager.py              # ORM Models (Star Schema)
├── pipeline/
│   ├── registry.py             # @register decorator + discovery
│   ├── base.py                 # BaseSource contract (E+C+L)
│   ├── utils.py                # upsert_data, normalize_string, get_cultura_id
│   ├── dimensions.py           # DimCultura, DimMunicipio, DimMantenedor
│   └── sources/
│       ├── cultivares.py       # SNPC/MAPA
│       ├── sidra.py            # PAM/IBGE
│       ├── zarc.py             # Climate risk (streaming)
│       ├── conab.py            # Production + prices
│       ├── agrofit.py          # Pesticides
│       ├── fertilizantes.py    # SIPEAGRO
│       ├── sigef.py            # Seeds
│       └── inmet.py            # Weather
└── api/                        # FastAPI (analytical endpoints)
```

---
*Diagrams generated for the AgroHarvest BR portfolio.*
