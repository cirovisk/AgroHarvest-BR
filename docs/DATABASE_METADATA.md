# Database Metadata - AgroHarvest BR

This document describes the PostgreSQL database structure used by **AgroHarvest BR**, following a **Star Schema** model.

## 🏗️ Data Architecture

The database is composed of three dimension tables and eleven fact tables, enabling granular analysis by crop, municipality, and time.

---

## 📐 Dimensions

### `dim_cultura`
Stores standardized crop names to guarantee referential integrity across different sources (SIDRA, CONAB, ZARC, Agrofit).
- `id_cultura` (PK): Unique identifier.
- `nome_padronizado` (Unique): Crop name in snake_case (for example, `soja`, `milho`).

### `dim_municipio`
Stores geographic information based on the IBGE code.
- `id_municipio` (PK): Unique identifier.
- `codigo_ibge` (Unique): Seven-digit IBGE code.
- `nome`: Municipality name.
- `uf`: State abbreviation.

### `dim_mantenedor`
Registry of companies or institutions responsible for cultivar registration.
- `id_mantenedor` (PK): Unique identifier.
- `nome` (Unique): Legal name or applicant name.
- `setor`: Maintainer classification (public, private, or mixed).

---

## 📊 Facts

### `fato_registro_cultivares` (Fonte: MAPA/SNPC)
Official cultivar records in the National Cultivar Registry (RNC).
- `nr_registro` (PK): MAPA registration number.
- `id_cultura` (FK): Key to `dim_cultura`.
- `id_mantenedor` (FK): Key to `dim_mantenedor`.
- `cultivar`: Commercial cultivar name.
- `nome_secundario`: Alternative name or alias.
- `situacao`: Registration status (for example, REGISTRADA).
- `nr_formulario`: Submission form number.
- `data_reg`: Official registration date.
- `data_val`: Registration expiration date.

### `fato_producao_pam` (Fonte: IBGE/SIDRA)
Historical series for Municipal Agricultural Production.
- `id_producao` (PK): Unique identifier.
- `id_cultura` (FK): Key to `dim_cultura`.
- `id_municipio` (FK): Key to `dim_municipio`.
- `ano`: Reference year.
- `area_plantada_ha`: Planted area in hectares.
- `area_colhida_ha`: Harvested area in hectares.
- `qtde_produzida_ton`: Total production in tons.
- `valor_producao_mil_reais`: Production value in thousand BRL.

### `fato_risco_zarc` (Fonte: MAPA/ZARC)
Climate Risk Zoning by municipality and soil.
- `id_zarc` (PK): Unique identifier.
- `id_cultura` (FK): Key to `dim_cultura`.
- `id_municipio` (FK): Key to `dim_municipio`.
- `tipo_solo`: Soil classification (type 1, 2, or 3).
- `periodo_plantio`: Recommended ten-day period/window.
- `risco_climatico`: Risk percentage (20%, 30%, 40%).
- `safra`: ZARC season (for example, 2025-2026).
- `finalidade`: Sugar/alcohol, other purposes, or not applicable.
- `cod_cultura_zarc`: Original MAPA ZARC crop code.
- `data_modificacao`: Audit timestamp.

### `fato_producao_conab` (Fonte: CONAB)
Production estimates and history by state and crop season.
- `id_conab` (PK): Unique identifier.
- `id_cultura` (FK): Key to `dim_cultura`.
- `uf`: Reference state.
- `ano_agricola`: Cycle (for example, 2023/24).
- `safra`: Crop-season identifier (1st, 2nd, or 3rd).
- `area_plantada_mil_ha`: Area in thousand hectares.
- `producao_mil_t`: Production in thousand tons.
- `produtividade_t_ha`: Average yield (ton/ha).

### `fato_precos_conab_mensal` (Fonte: CONAB)
Monthly average price series received by producers.
- `id_preco` (PK): Unique identifier.
- `id_cultura` (FK): Key to `dim_cultura`.
- `id_municipio` (FK): Optional key to `dim_municipio`.
- `uf`: Reference state.
- `ano`: Calendar year.
- `mes`: Month (1 to 12).
- `valor_kg`: Amount paid to the producer per kg.
- `nivel_comercializacao`: Transaction level (for example, producer).

### `fato_precos_conab_semanal` (Fonte: CONAB)
Price data with weekly granularity.
- `semana`: Week number in the year.
- `data_referencia`: Week period (start/end).
- Other fields are identical to the monthly table.

### `fato_agrofit` (Fonte: MAPA/Agrofit)
Relationship between crops and registered pesticides/crop protection products.
- `id_agrofit` (PK): Unique identifier.
- `id_cultura` (FK): Key to `dim_cultura`.
- `nr_registro`: Product registration in MAPA.
- `marca_comercial`: Commercial name of the crop protection product.
- `ingrediente_ativo`: Active ingredient.
- `titular_registro`: Company holding the registration.
- `classe`: Classification (herbicide, insecticide, and so on).
- `praga_comum`: Common name of the pest/biological target.

### `fato_fertilizantes_estabelecimentos` (Fonte: MAPA/SIPEAGRO)
Registry of fertilizer producers, importers, and traders.
- `id_fertilizante` (PK): Unique identifier.
- `id_municipio` (FK): Key to `dim_municipio` through name/state mapping.
- `uf`: Establishment state.
- `municipio`: Original municipality name.
- `nr_registro_estabelecimento` (Unique): SIPEAGRO registration number.
- `status_registro`: Status (active, canceled, and so on).
- `cnpj`: Establishment CNPJ.
- `razao_social`: Company legal name.
- `nome_fantasia`: Trade name.
- `area_atuacao`: Area (for example, FERTILIZANTE, INOCULANTE).
- `atividade`: Activity (for example, PRODUTOR, IMPORTADOR).
- `classificacao`: Detailed establishment classification.
 
### `fato_sigef_producao` (Fonte: MAPA/SIGEF)
Commercial seed and seedling production control.
- `id_sigef_producao` (PK): Unique identifier.
- `id_cultura` (FK): Key to `dim_cultura`.
- `id_municipio` (FK): Key to `dim_municipio`.
- `safra`: Production cycle (for example, 2023/2023).
- `especie`: Original species name.
- `cultivar_raw`: Original cultivar name.
- `categoria`: Seed category (C1, C2, S1, S2, and so on).
- `status`: Production field status.
- `data_plantio`: Field planting date.
- `data_colheita`: Harvest date.
- `area_ha`: Field area in hectares.
- `producao_bruta_t`: Gross harvested volume (tons).
- `producao_est_t`: Production estimate (tons).
 
### `fato_sigef_reserva_semente` (Fonte: MAPA/SIGEF)
Seed reserve declarations for producers' own use.
- `id_sigef_reserva` (PK): Unique identifier.
- `id_cultura` (FK): Key to `dim_cultura`.
- `id_municipio` (FK): Key to `dim_municipio`.
- `periodo`: Declaration year/crop season.
- `tipo_periodo`: Period granularity (for example, ANO).
- `cultivar_raw`: Reserved cultivar.
- `data_plantio`: Planting date, when supplied by SIGEF.
- `quantidade_reservada_t`: Reserved quantity in tons, when supplied by SIGEF.
- `area_total_ha`: Total declared area.
- `area_plantada_ha`: Actually planted area.
- `area_estimada_ha`: Estimated production area.
 
### `fato_meteorologia` (Fonte: INMET)
Daily weather data aggregated by municipality.
- `id_meteo` (PK): Unique identifier.
- `id_municipio` (FK): Key to `dim_municipio`.
- `data`: Reference date.
- `precipitacao_total_mm`: Accumulated rainfall for the day.
- `temp_max_c`: Maximum observed temperature.
- `temp_min_c`: Minimum observed temperature.
- `temp_media_c`: Arithmetic average temperature for the day.
- `umidade_media`: Average relative humidity (%).
- `estacao_id`: Source INMET station code.

### `fato_ndvi_satelite` (Fonte: Sensoriamento Remoto / MODIS)
Annual NDVI vegetation index data aggregated by municipality.
- `id_ndvi` (PK): Unique identifier.
- `id_municipio` (FK): Key to `dim_municipio`.
- `ano`: Calendar year corresponding to the crop season.
- `ndvi_max_safra`: Maximum NDVI value reached during the critical period.
- `ndvi_mean_safra`: Average NDVI value during the critical period.
- `data_modificacao`: Audit timestamp.

---

## 🔒 Security and Access

The database follows the least-privilege principle for the exposure layer:

1.  **Application User (`postgres`):** Has `OWNER` permissions and is used exclusively by the ETL pipeline to create tables and perform `UPSERT`.
2.  **API User (`api_reader`):** Has restricted `SELECT` permissions on all tables.
    - All FastAPI communication uses this user.
    - Setup script: `docs/setup_api_reader.sql`.

## 🔄 Auditing and Technical Metadata

All fact tables include the following field:
- `data_modificacao`: Timestamp of the latest insert or update (UPSERT), supporting incremental loads and data freshness auditing.

---

## 🔗 Official Metadata References

If you need to consult the original methodology for each source:

- **IBGE (PAM):** [Methodology and Concepts - SIDRA](https://www.ibge.gov.br/estatisticas/economicas/agricultura-e-pecuaria/9117-producao-agricola-municipal-culturas-temporarias-e-permanentes.html?=&t=o-que-e)
- **MAPA (ZARC):** [Manual de Indicadores e Metodologia ZARC](https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico)
- **CONAB (Prices and Crop Seasons):** [Crop Survey Methodology](https://www.conab.gov.br/info-agro/safras/metodologia)
- **MAPA (Agrofit):** [Input and Crop Protection Product Search](https://agrofit.agricultura.gov.br/agrofit_cons/principal_agrofit_cons)
