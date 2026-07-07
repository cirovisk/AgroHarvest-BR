"""NDVI pipeline: satellite remote sensing (MODIS/GEE)."""

import logging
import os

import pandas as pd

from db.manager import FatoNdviSatelite
from pipeline.base import BaseSource
from pipeline.registry import register
from pipeline.utils import upsert_data

log = logging.getLogger(__name__)


@register("ndvi")
class NdviPipeline(BaseSource):
    """
    Extrator NDVI: Dados de satélite coletados por município.
    Lê o CSV exportado do Google Earth Engine ou simulado localmente.
    """

    FILENAME = "ndvi_municipios.csv"

    def __init__(self, data_dir="data/ndvi", force_refresh=False):
        super().__init__()
        self.data_dir = data_dir
        self.force_refresh = force_refresh
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

    def extract(self, **kwargs) -> pd.DataFrame:
        """Carrega os dados brutos de NDVI."""
        local_path = os.path.join(self.data_dir, self.FILENAME)

        if not os.path.exists(local_path):
            self.log.error(f"Arquivo de NDVI não encontrado em {local_path}!")
            return pd.DataFrame()

        try:
            df = pd.read_csv(local_path, dtype={"codigo_ibge": str})
            self.log.info(f"NDVI carregado: {len(df)} linha(s), {len(df.columns)} coluna(s).")
            return df
        except Exception as e:
            self.log.error(f"Erro ao ler {self.FILENAME}: {e}")
            return pd.DataFrame()

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        self.log.info(f"Cleaner NDVI: {len(df)} linha(s) recebida(s).")

        # Garantir limpeza de strings e tipos corretos
        df["codigo_ibge"] = df["codigo_ibge"].astype(str).str.strip()
        df["ano"] = df["ano"].astype(int)
        df["ndvi_max_safra"] = pd.to_numeric(df["ndvi_max_safra"], errors="coerce")
        df["ndvi_mean_safra"] = pd.to_numeric(df["ndvi_mean_safra"], errors="coerce")

        self.log.info("Cleaner NDVI concluído.")
        return df

    def load(self, df: pd.DataFrame, lookups: dict) -> str:
        if df.empty:
            return "0 registros"

        df_f = df.copy()

        # Map codigo_ibge to id_municipio
        df_f["codigo_ibge"] = df_f["codigo_ibge"].str[:7]
        df_f["id_municipio"] = df_f["codigo_ibge"].map(lookups["municipios_ibge"])

        # Remover registros sem id_municipio correspondente
        df_f = df_f.dropna(subset=["id_municipio"])

        # Realizar upsert
        upsert_data(FatoNdviSatelite, df_f, index_elements=["id_municipio", "ano"])

        result = f"{len(df_f)} registros upserted"
        self.log.info(f"Fato NDVI: {result}.")
        return result
