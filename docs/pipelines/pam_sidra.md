# Pipeline: Municipal Agricultural Production (PAM/SIDRA)

Extraction of agricultural production data for temporary crops through the IBGE SIDRA v3 API.

## 📌 Data Source
- **Aggregate:** Table 1612 (Municipal Agricultural Production - temporary crops)
- **API:** [SIDRA API](https://apisidra.ibge.gov.br/)
- **Granularity:** Municipality (level 6) and crop (C81).

## 🛠️ Extraction Process
1.  **Metadata:** The pipeline first queries the metadata for Table 1612 to retrieve the dynamic IDs for each crop in classification 81.
    - URL: `https://servicodados.ibge.gov.br/api/v3/agregados/1612/metadados`
2.  **Query:** For each identified `crop_id` (for example, soybean = 40280), the pipeline makes a REST call requesting:
    - **Variables (`v`):** 109 (planted area), 216 (harvested area), 214 (produced quantity).
    - **Territory (`n6`):** All Brazilian municipalities.
    - **Period (`p`):** Specific year configured in the extractor.
3.  **Example URL:** `https://apisidra.ibge.gov.br/values/t/1612/n6/all/v/109,216,214/p/2022/c81/40280`

## 🔄 Transformations (Cleaners)
Logic implemented in `src/pipeline/cleaners/sidra.py`:
- **Column Normalization:** Maps SIDRA codes (D2N, V, D1C) to friendly names.
- **Pivoting:** Transforms variables from API rows into fact columns.
- **Null Handling:** Converts IBGE symbols (`...`, `-`) to `NaN`.
- **Crop Match:** Applies `normalize_culture_name`.

## 💾 Storage
The data is loaded into the `fato_producao_pam` table in PostgreSQL, preserving history by year and municipality.
