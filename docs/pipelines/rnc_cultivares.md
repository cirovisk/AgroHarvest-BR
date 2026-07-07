# Pipeline: Registro Nacional de Cultivares (RNC)

Extraction of the official registry of all cultivars (seeds/seedlings) registered for commercialization in Brazil.

## 📌 Data Source
- **System:** CultivarWeb / MAPA SNPC.
- **Type:** Registration and protection data (Law No. 9,456/1997 and Law No. 10,711/2003).

## 🛠️ Extraction Process
1.  **Web Scraping / Download:** The pipeline accesses the consolidated CultivarWeb dataset that lists varieties by crop.
2.  **Granularity:** The data is provided at **variety (cultivar)** level and includes the respective **maintainer** (the company responsible for the genetics).

## 🔄 Transformations (Cleaners)
Executed in `src/pipeline/cleaners/cultivares.py`:
- **Company Extraction:** Normalizes the maintainer name and classifies the **sector** (for example, private vs. public - EMBRAPA).
- **Validity Dates:** Converts strings to `date` objects.
- **Crop Match:** Uses `normalize_culture_name` and looks up IDs in the dimension.

## 💾 Storage
- Maintainers populate `dim_mantenedor`.
- Detailed variety records populate `fato_registro_cultivares`.
- This table is the **diamond** of the project, making it possible to identify which seed technologies were available in each crop year.
