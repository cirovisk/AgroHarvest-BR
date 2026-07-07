# Pipeline: SIPEAGRO (Fertilizer Establishments)

Extraction of the registry of establishments that sell or produce fertilizers in Brazil.

## 📌 Data Source
- **Agency:** MAPA (Ministry of Agriculture and Livestock)
- **Dataset:** [SIPEAGRO - Establishments](https://dados.agricultura.gov.br/dataset/52a01565-72d6-410e-b21b-64035831a7be/resource/e0bbc9d5-f161-448b-a6d4-c7beb312ec33)

## 🛠️ Extraction Process
1.  **CSV Download:** Direct download over HTTP.
2.  **Versioning:** The script keeps an `archive` folder to store previous dataset versions before updating, preserving idempotency and a history of establishment changes.

## 🔄 Transformations (Cleaners)
Implemented in `src/pipeline/cleaners/fertilizantes.py`:
- **CNPJ Cleaning:** Numeric standardization.
- **Encoding Handling:** Conversion from `latin1` to `utf-8`.
- **Municipality Match:** Dynamic join with `dim_municipio`.

## 💾 Storage
The data feeds the `fato_fertilizantes_estabelecimentos` table, providing a clear view of the input infrastructure available in each producing microregion.
