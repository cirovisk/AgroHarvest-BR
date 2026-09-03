# Pipeline: Municipal Agricultural Production (PAM/SIDRA)

Extraction of agricultural production data for temporary crops through the IBGE SIDRA v3 API.

## 📌 Data Source
- **Aggregate:** Table 5457 (Municipal Agricultural Production - temporary crops)
- **API:** [SIDRA API](https://apisidra.ibge.gov.br/)
- **Granularity:** Municipality (level 6) and crop (classification 782).

## 🛠️ Extraction Process
1.  **Metadata:** The pipeline first queries the metadata for Table 5457 to retrieve the dynamic IDs for each crop in classification 782.
    - URL: `https://servicodados.ibge.gov.br/api/v3/agregados/5457/metadados`
2.  **Query:** For each identified `crop_id` (for example, soybean = 40280), the pipeline makes a REST call requesting:
    - **Variables (`v`):** 8331 (planted area), 216 (harvested area), 214 (produced quantity), 215 (production value).
    - **Territory (`n6`):** All Brazilian municipalities.
    - **Period (`p`):** Each explicit year configured in `SIDRA_ANOS` (default: 2021–2024).
3.  **Example URL:** `https://apisidra.ibge.gov.br/values/t/5457/n6/all/v/8331,216,214,215/p/2022/c782/40124`

Each year is requested and validated separately. Responses containing only the header,
or rows whose `D3N` differs from the requested year, are reported as missing. The cache
name includes the complete year scope (for example,
`pam_sidra_2021-2022-2023-2024.csv`), so one scope cannot satisfy another silently.

## 🔄 Transformations (Cleaners)
Logic implemented in `src/pipeline/sources/sidra.py`:
- **Column Normalization:** Maps SIDRA codes (D2N, V, D1C) to friendly names.
- **Pivoting:** Transforms variables from API rows into fact columns.
- **Null Handling:** Converts IBGE symbols (`...`, `-`) to `NaN`.
- **Crop Match:** Applies `normalize_culture_name`.

## 💾 Storage
The data is loaded into the `fato_producao_pam` table in PostgreSQL, preserving history by year and municipality.
