"""SIDRA/PAM pipeline: Municipal Agricultural Production (IBGE)."""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests

from db.manager import FatoProducaoPAM
from pipeline.base import BaseSource
from pipeline.registry import register
from pipeline.utils import get_cultura_id, normalize_string, upsert_data

log = logging.getLogger(__name__)


@register("sidra")
class SidraPipeline(BaseSource):
    """
    Extrator PAM: Produção Agrícola Municipal (SIDRA/IBGE).
    Tabela 5457: Lavouras Temporárias.
    """

    from config import CULTURAS_IBGE_IDS

    TARGET_CROPS = CULTURAS_IBGE_IDS

    DEFAULT_YEARS = ("2021", "2022", "2023", "2024")

    def __init__(
        self, ano: str | list[str] | tuple[str, ...] | None = None, data_dir: str = "data/sidra", use_cache: bool = True
    ):
        super().__init__()
        configured_years = ano if ano is not None else (os.getenv("SIDRA_ANOS") or os.getenv("SIDRA_ANO_DEFAULT"))
        if configured_years is None:
            self.anos = self.DEFAULT_YEARS
        elif isinstance(configured_years, str):
            self.anos = tuple(year.strip() for year in configured_years.split(",") if year.strip())
        else:
            self.anos = tuple(str(year).strip() for year in configured_years if str(year).strip())
        if not self.anos:
            raise ValueError("SIDRA requer pelo menos um ano configurado")
        if any(not year.isdigit() or len(year) != 4 for year in self.anos):
            raise ValueError(f"Anos SIDRA inválidos: {self.anos}")
        # Mantido para consumidores que ainda consultam o atributo antigo.
        self.ano = self.anos[0] if len(self.anos) == 1 else ",".join(self.anos)
        self.missing_years: list[str] = []
        self.missing_requests: list[tuple[str, str]] = []
        self.data_dir = data_dir
        self.use_cache = use_cache
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

    def _map_culture_ids(self) -> dict:
        """Metadados: Consulta de IDs de categoria no IBGE."""
        self.log.info("Buscando metadados da tabela 5457 no IBGE...")
        url = "https://servicodados.ibge.gov.br/api/v3/agregados/5457/metadados"
        metadata_map = {}
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for cls in data.get("classificacoes", []):
                if cls["id"] == "782":
                    for cat in cls.get("categorias", []):
                        name_norm = normalize_string(pd.Series([cat["nome"]])).iloc[0]
                        # Normalization: remove suffixes (for example, "em grão")
                        name_clean = name_norm.split("(")[0].strip()
                        metadata_map[name_clean] = cat["id"]
        except Exception as e:
            self.log.warning(f"Falha ao buscar metadados, usando hardcoded. Erro: {e}")
            return self.TARGET_CROPS

        final_map = {}
        for target in self.TARGET_CROPS.keys():
            target_norm = normalize_string(pd.Series([target])).iloc[0]
            for clean_name, cid in metadata_map.items():
                if target_norm in clean_name:
                    final_map[target_norm] = cid
                    break
            if target_norm not in final_map:  # Fallback
                final_map[target_norm] = self.TARGET_CROPS[target]

        return final_map

    def extract(self, **kwargs) -> pd.DataFrame:
        cache_scope = "-".join(self.anos)
        cache_file = os.path.join(self.data_dir, f"pam_sidra_{cache_scope}.csv")

        if self.use_cache and os.path.exists(cache_file):
            if not self.is_file_stale(cache_file, threshold_days=30):
                self.log.info(f"Carregando cache SIDRA: {cache_file}")
                cached = pd.read_csv(cache_file, dtype=str)
                cached_years = set(cached["D3N"].unique()) if "D3N" in cached.columns else set()
                if cached_years == set(self.anos):
                    self.missing_years = []
                    self.missing_requests = []
                    return cached
                self.log.warning(
                    f"Cache SIDRA ignorado: períodos encontrados {sorted(cached_years)}, esperados {list(self.anos)}."
                )

        crops_ids = self._map_culture_ids()

        # Table 5457 variables: 8331 (planted area), 216 (harvested area), 214 (production), 215 (production value)
        variables = "8331,216,214,215"

        def _fetch_crop(crop_name, crop_id, year):
            self.log.info(f"Buscando dados IBGE para {crop_name} (ID: {crop_id}), ano {year}")
            url = f"https://apisidra.ibge.gov.br/values/t/5457/n6/all/v/{variables}/p/{year}/c782/{crop_id}"
            try:
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and len(data) > 1:
                        df_tmp = pd.DataFrame(data[1:], columns=data[0])
                        if "D3N" not in df_tmp.columns:
                            self.log.warning(f"SIDRA não retornou a coluna de período para {crop_name}, ano {year}.")
                            return None
                        returned_years = set(df_tmp["D3N"].astype(str).unique())
                        if returned_years != {year}:
                            self.log.warning(
                                f"SIDRA retornou período(s) {sorted(returned_years)} para {crop_name}, ano solicitado {year}."
                            )
                            return None
                        df_tmp["cultura_raw"] = crop_name
                        return year, df_tmp
                    self.log.warning(f"SIDRA retornou somente cabeçalho para {crop_name}, ano {year}.")
                else:
                    self.log.warning(f"Erro {resp.status_code} na consulta de {crop_name}, ano {year}: {resp.text}")
            except Exception as e:
                self.log.error(f"Exceção ao buscar {crop_name}, ano {year}: {e}")
            return None

        # Parallel requests: five simultaneous crops instead of sequential processing
        all_dfs = []
        years_with_data = set()
        successful_requests = set()
        max_workers = min(10, len(crops_ids) * len(self.anos))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_fetch_crop, name, cid, year): (name, year)
                for year in self.anos
                for name, cid in crops_ids.items()
            }
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    year, frame = result
                    years_with_data.add(year)
                    crop_name, _ = futures[future]
                    successful_requests.add((crop_name, year))
                    all_dfs.append(frame)

        self.missing_years = [year for year in self.anos if year not in years_with_data]
        self.missing_requests = [
            (crop_name, year)
            for year in self.anos
            for crop_name in crops_ids
            if (crop_name, year) not in successful_requests
        ]
        if self.missing_years:
            self.log.warning(f"SIDRA sem dados válidos para os anos solicitados: {self.missing_years}")
        if self.missing_requests:
            self.log.warning(f"SIDRA com consultas ausentes ou inválidas: {self.missing_requests}")

        if not all_dfs:
            self.log.warning("Extrator SIDRA: nenhum dado retornado para todas as culturas alvo.")
            return pd.DataFrame()

        final_df = pd.concat(all_dfs, ignore_index=True)
        self.log.info(f"Extrator SIDRA: {len(final_df)} linha(s) brutas consolidadas de {len(all_dfs)} cultura(s).")

        if self.use_cache and not self.missing_requests:
            final_df.to_csv(cache_file, index=False)
            self.log.info(f"Cache salvo: {cache_file}")

        return final_df

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        self.log.info(f"Cleaner PAM/SIDRA: {len(df)} linha(s) recebida(s).")

        col_map = {
            "D2N": "variavel",
            "V": "valor",
            "D1C": "cod_municipio_ibge",
            "D1N": "municipio_nome",
            "D3N": "ano",
            "cultura_raw": "cultura",
        }

        ausentes = [k for k in col_map if k not in df.columns]
        if ausentes:
            self.log.warning(f"PAM/SIDRA: colunas esperadas ausentes no DataFrame bruto: {ausentes}")

        df_clean = df.rename(columns=col_map)
        df_clean = df_clean[[c for c in col_map.values() if c in df_clean.columns]].copy()

        nulos_antes = df_clean["valor"].isna().sum()
        df_clean["valor"] = pd.to_numeric(df_clean["valor"].replace(["...", "-"], np.nan), errors="coerce")
        nulos_depois = df_clean["valor"].isna().sum()
        if nulos_depois > nulos_antes:
            self.log.info(
                f"PAM/SIDRA: {nulos_depois - nulos_antes} valor(es) não numérico(s) do IBGE ('...', '-') convertido(s) para NaN."
            )

        # Transformation: pivot variables into fact columns
        df_pivot = df_clean.pivot_table(
            index=["cod_municipio_ibge", "municipio_nome", "ano", "cultura"], columns="variavel", values="valor"
        ).reset_index()
        self.log.info(f"PAM/SIDRA pivot: {len(df_pivot)} combinação(ões) (município × cultura × ano).")

        df_pivot.columns.name = None

        var_renames = {
            "Área plantada": "area_plantada_ha",
            "Área colhida": "area_colhida_ha",
            "Quantidade produzida": "qtde_produzida_ton",
            "Valor da produção": "valor_producao_mil_reais",
        }

        actual_renames = {}
        for col in df_pivot.columns:
            for key, target in var_renames.items():
                if key in col:
                    actual_renames[col] = target

        df_pivot = df_pivot.rename(columns=actual_renames)

        for target in var_renames.values():
            if target not in df_pivot.columns:
                df_pivot[target] = np.nan

        df_pivot["cultura"] = normalize_string(df_pivot["cultura"])

        # Extract state from the IBGE code (first two digits) for municipality usage
        # SIDRA data does not include an explicit state column

        return df_pivot

    def load(self, df: pd.DataFrame, lookups: dict) -> dict:
        if df.empty:
            return {
                "source": "sidra",
                "status": "partial",
                "rows_loaded": 0,
                "coverage_expected": list(self.anos),
                "coverage_observed": [],
                "warnings": ["Nenhum dado válido retornado pelo SIDRA"],
            }

        df_f = df.copy()
        df_f["id_cultura"] = df_f["cultura"].apply(lambda x: get_cultura_id(x, lookups["culturas"]))
        df_f["cod_municipio_ibge"] = df_f["cod_municipio_ibge"].astype(str).str[:7]
        df_f["id_municipio"] = df_f["cod_municipio_ibge"].map(lookups["municipios_ibge"])
        cols = [
            "id_cultura",
            "id_municipio",
            "ano",
            "area_plantada_ha",
            "area_colhida_ha",
            "qtde_produzida_ton",
            "valor_producao_mil_reais",
        ]
        df_f = df_f[cols].dropna(subset=["id_cultura", "id_municipio"])
        upsert_data(FatoProducaoPAM, df_f, index_elements=["id_cultura", "id_municipio", "ano"])
        observed_years = sorted(df_f["ano"].astype(str).unique().tolist())
        warnings = [f"Consulta ausente ou inválida: {crop}/{year}" for crop, year in self.missing_requests]
        result = {
            "source": "sidra",
            "status": "partial" if self.missing_requests else "success",
            "rows_loaded": len(df_f),
            "coverage_expected": list(self.anos),
            "coverage_observed": observed_years,
            "warnings": warnings,
        }
        self.log.info("Fato PAM: %d registros upserted.", len(df_f))
        return result
