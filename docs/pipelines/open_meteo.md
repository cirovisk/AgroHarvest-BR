# Pipeline: Open-Meteo (Weather)

Extraction and consolidation of historical climate and weather data. This pipeline previously used INMET, but it was replaced because the agency servers were unstable and frequently unavailable.

## 📌 Data Source
- **Agency:** Open-Meteo (global open weather data API)
- **Origin:** [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- **Latency:** D-2 (data consolidated with a two-day delay).

## 🛠️ Extraction Process
1. **Coordinates:** The pipeline first joins the official municipality list (IBGE) with an open-source GitHub dataset containing latitude and longitude for all 5,570 Brazilian municipalities.
2. **Parallel Workers:** To speed up daily data ingestion, it uses `ThreadPoolExecutor` for parallel and simultaneous requests.
3. **Daily Limit:** Although free, the API is limited to 10,000 daily calls. The pipeline can be configured to slice requests.

## 💾 Storage (Star Schema)
- **Fact:** `fato_meteorologia`.
- **Relationships:** Foreign keys to `dim_municipio`.

## 🔄 Extracted Indicators
- **Total precipitation (mm)**
- **Maximum temperature (°C)**
- **Minimum temperature (°C)**
- **Average temperature (°C)**

*Note: Unlike physical INMET stations, the satellite and global model API (Open-Meteo) provides continuous and uninterrupted coverage for every municipality, including those without weather stations.*
