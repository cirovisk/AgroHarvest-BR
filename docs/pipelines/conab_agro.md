# Pipeline: CONAB (Price and Production Series)

Extraction of market indicators and crop forecast estimates from the National Supply Company.

## 📌 Data Source
- **Data Portal:** [CONAB - Open Data](https://www.conab.gov.br/)
- **Datasets:**
    - Historical price series (monthly and weekly).
    - Crop surveys (production and yield).

## 🛠️ Extraction Process
1.  **Spreadsheet/ZIP Download:** CONAB publishes many datasets as `.xlsx` or compressed files. The pipeline downloads those sources directly.
2.  **Price Series:** Captures average prices at state or trading-center level.
3.  **Crop Surveys:** Extracts planted area (thousand ha), production (thousand t), and yield (t/ha).

## 🔄 Transformations (Cleaners)
Centralized logic in `src/pipeline/cleaners/conab.py`:
- **Unit Normalization:** Converts thousand hectares/tons to base units (ha/t).
- **String Handling:** Removes whitespace and normalizes state abbreviations.
- **Temporal Hierarchy:** Maps "crop year" values (for example, 2023/24) to the harvest start year.
- **Crop Match:** Links records through `normalize_culture_name`.

## 💾 Storage
The data is loaded into three fact tables:
- `fato_producao_conab`: Macro crop and yield data.
- `fato_precos_conab_mensal`: Monthly historical price series per kg.
- `fato_precos_conab_semanal`: Short-term price monitoring.
