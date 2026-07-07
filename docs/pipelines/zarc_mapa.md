# Pipeline: Agricultural Climate Risk Zoning (ZARC)

Large-scale extraction and processing of climate risk scenarios and cultivar recommendations.

## 📌 Data Source
- **Agency:** MAPA
- **Origin:** [Zarc Portal (MAPA)](https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico)
- **Access Method:** CSV files consolidated by crop (soybean, corn, wheat, cotton, and sugarcane).

## 🛠️ Extraction Process (Optimized)
Because the files are large and some CSVs exceed 1.3 GB, the pipeline uses a **streaming and chunking** strategy:
1. **Magic Bytes:** The code automatically identifies whether the file is Gzip-compressed by reading the first bytes, allowing it to read raw `.csv.gz` or `.csv` files without code changes.
2. **Chunking:** Pandas reads the file in 50,000-row blocks, processes each block, and releases memory before reading the next one.
3. **Selective Loading:** To populate `dim_municipio`, the pipeline performs a partial read with only ID and name columns, avoiding unnecessary loading of the 36 ten-day-period columns.

## 🔄 High Performance in PostgreSQL
Unlike approaches that require separate OLAP databases, ZARC resides entirely in PostgreSQL here. Performance is supported by:
- **Composite B-Tree Index:** Created on `(id_municipio, id_cultura)` in the `fato_risco_zarc` table.
- **Partition Filters:** Dashboard queries are optimized to filter by municipality first, reducing scans from millions of rows to a few hundred.

## 💾 Storage (Star Schema)
- **Fact:** `fato_risco_zarc`.
- **Relationships:** Foreign keys to `dim_municipio` and `dim_cultura`.

## 📥 Expansion Guide
The project currently processes **soybean, corn, wheat, cotton, and sugarcane** natively. To add a new crop:
1. Download the CSV from the MAPA portal.
2. Save it in `data/zarc/` using the name `zarc_{crop}.csv`.
3. Add the crop name to the `TARGET_CROPS` list in `src/pipeline/sources/zarc.py`.
