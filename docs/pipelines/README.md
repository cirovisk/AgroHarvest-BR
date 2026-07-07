# Pipeline Documentation (ETL)

This folder contains the technical details for each extraction and transformation (ETL) pipeline implemented in **AgroHarvest BR**.

## 📑 Source Index

| Source | Responsible Entity | Documentation File |
| :--- | :--- | :--- |
| **SIDRA/PAM** | IBGE | [pam_sidra.md](./pam_sidra.md) |
| **ZARC** | MAPA | [zarc_mapa.md](./zarc_mapa.md) |
| **CONAB** | CONAB | [conab_agro.md](./conab_agro.md) |
| **Cultivares (RNC)** | MAPA/SNPC | [rnc_cultivares.md](./rnc_cultivares.md) |
| **Agrofit** | MAPA | [agrofit.md](./agrofit.md) |
| **Fertilizers** | MAPA/SIPEAGRO | [sipeagro_fertilizantes.md](./sipeagro_fertilizantes.md) |

---

## 🏗️ Engineering Pattern
 
The project uses a decoupled pipeline architecture:

1.  **Extractors (`src/pipeline/`):** Classes that manage the connection to each source, data downloads, and cache persistence. They do not contain complex business logic.
2.  **Cleaners (`src/pipeline/cleaners/`):** Pure stateless functions that receive raw data (JSON/CSV) and return normalized DataFrames. This decoupling makes it possible to test data cleaning without internet or database access.
3.  **Centralized Normalization:** The `normalize_culture_name` method (`src/pipeline/utils.py`) is used to unify crop names across IBGE, MAPA, and CONAB.
