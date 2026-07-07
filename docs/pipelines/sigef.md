# Pipeline SIGEF (Sementes e Mudas)

## 📌 Context
SIGEF (Seed and Seedling Inspection Management System) from MAPA provides raw data on seed production and seed reserves in Brazil. One of the main technical challenges in this source is its use of **botanical nomenclature (Latin)** instead of common names.

## 🛠️ Interoperability Solution
To ensure that SIGEF data can be joined with other sources such as IBGE/PAM, the pipeline core implements a **Scientific Synonym Mapper** in `src/pipeline/loaders.py`.

### Implemented Mapping:
| Scientific Name (SIGEF) | Common Name (Database) | Related Crop |
|-------------------------|----------------------|---------------------|
| `Glycine max`           | Soja                 | Soja                |
| `Zea mays`              | Milho                | Milho               |
| `Triticum aestivum`     | Trigo                | Trigo               |
| `Gossypium hirsutum`    | Algodão              | Algodão             |
| `Avena strigosa`        | Aveia                | Aveia               |
| `Saccharum`             | Cana-de-açúcar       | Cana-de-açúcar      |

## 🚀 Normalization Logic
The worker uses **token matching** with word boundaries.
1.  The raw name is normalized by removing accents and lowercasing.
2.  The synonym dictionary is queried.
3.  If there is a partial whole-word match, such as "Avena" in "Avena strigosa Schreb.", the record is linked to the corresponding crop ID.
4.  Records without a botanical or common-name match are discarded to preserve Star Schema referential integrity.

## 📊 Dashboard Impact
This implementation changed the "Seed Reserve" dashboard from a single-crop view (only wheat) to a multi-crop view covering the main commodities in Brazilian agribusiness.
