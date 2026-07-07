# Pipeline: Agrofit (Crop Protection Products)

Extraction of data for formulated products (pesticides and related products) registered with MAPA.

## 📌 Data Source
- **Agency:** MAPA (Ministry of Agriculture and Livestock)
- **Dataset:** [Agrofit - Open Data](https://dados.agricultura.gov.br/dataset/agrofitprodutosformulados)

## 🛠️ Extraction Process
1.  **CSV Download:** The pipeline downloads the consolidated CSV file for formulated products. Because of the high data volume, the extractor implements **Incremental Cache** logic and checks whether the local file is more than 30 days old.
2.  **Granularity:** Product, active ingredient, and target pest.

## 🔄 Transformations (Cleaners)
The cleaning logic lives in `src/pipeline/cleaners/agrofit.py`:
- **Pest-Crop Mapping:** Connects the product to the recommended crop and common pest.
- **String Normalization:** Cleans active ingredient records and toxicity classification values.
- **Crop Match:** Uses `normalize_culture_name` to link records with `dim_cultura`.

## 💾 Storage
The data is persisted in the `fato_agrofit` table. The model is extensible enough to analyze which cultivars have resistance biotechnology for the active ingredients listed here.
