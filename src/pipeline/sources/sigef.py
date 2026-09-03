"""SIGEF pipeline: seed and seedling production control (MAPA)."""

import hashlib
import io
import logging
import os
import re

import pandas as pd
import requests

from db.manager import FatoSigefProducao, FatoSigefReservaSemente
from pipeline.base import BaseSource
from pipeline.registry import register
from pipeline.utils import get_cultura_id, map_municipio_by_name, normalize_string, upsert_data

log = logging.getLogger(__name__)


@register("sigef")
class SigefPipeline(BaseSource):
    """
    Extrator SIGEF: Controle da Produção de Sementes e Mudas (MAPA).
    Campos de produção e Declarações de uso próprio.
    """

    RESOURCES = {
        "campos_producao": "https://dados.agricultura.gov.br/dataset/c7784a6e-f0ec-4196-a1ce-1d2d4784a58e/resource/6ab20c11-73a0-4ab0-8e13-2420d48dd6f5/download/sigefcamposproducaodesementes.csv",
        "reserva_semente": "https://dados.agricultura.gov.br/dataset/c7784a6e-f0ec-4196-a1ce-1d2d4784a58e/resource/3fc8e266-ec41-40b0-8d62-157b91b36b2c/download/sigefdeclaracaoareaproducaouseproprio.csv",
    }

    def __init__(self, data_dir="data/sigef", use_cache=True, quarantine_path=None):
        super().__init__()
        self.data_dir = data_dir
        self.use_cache = use_cache
        self.quarantine_path = quarantine_path or os.getenv(
            "SIGEF_QUARANTINE_PATH", os.path.join(self.data_dir, "campos_producao_quarentena.csv")
        )
        self.quality_metrics = {}
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

    def extract(self, **kwargs) -> dict:
        dataframes = {}
        for key, url in self.RESOURCES.items():
            filename = f"{key}.csv"
            local_path = os.path.join(self.data_dir, filename)
            if key == "reserva_semente" and os.path.exists(os.path.join(self.data_dir, "uso_proprio.csv")):
                local_path = os.path.join(self.data_dir, "uso_proprio.csv")

            if self.use_cache and os.path.exists(local_path) and not self.is_file_stale(local_path, 15):
                self.log.info(f"Usando cache SIGEF para {key}...")
                dataframes[key] = pd.read_csv(local_path, sep=";", encoding="utf-8", on_bad_lines="skip", dtype=str)
                continue

            self.log.info(f"Baixando SIGEF {key} de {url}...")
            try:
                try:
                    resp = requests.get(url, timeout=60, verify=True)
                except requests.exceptions.SSLError as ssl_err:
                    self.log.warning(
                        f"Falha de SSL ao conectar com {url}: {ssl_err}. "
                        "Retentando com verificação SSL desabilitada (fallback)..."
                    )
                    import urllib3

                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    resp = requests.get(url, timeout=60, verify=False)

                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                dataframes[key] = pd.read_csv(
                    io.BytesIO(resp.content), sep=";", encoding="utf-8", on_bad_lines="skip", dtype=str
                )
            except Exception as e:
                self.log.error(f"Erro ao baixar SIGEF {key}: {e}")
                if os.path.exists(local_path):
                    dataframes[key] = pd.read_csv(local_path, sep=";", encoding="utf-8", on_bad_lines="skip", dtype=str)

        return dataframes

    def clean(self, dataframes: dict) -> dict:
        processed = {}
        if "campos_producao" in dataframes:
            processed["campos_producao"] = self._clean_producao(dataframes["campos_producao"])
        # Support data sources with varied keys ('reserva_semente' or 'uso_proprio').
        reserva_df = (
            dataframes.get("reserva_semente") if "reserva_semente" in dataframes else dataframes.get("uso_proprio")
        )
        if reserva_df is not None:
            processed["reserva_semente"] = self._clean_reserva_semente(reserva_df)
        return processed

    def _clean_producao(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            self._write_quarantine([])
            self.quality_metrics = self._empty_quality_metrics()
            return df
        df = df.copy()

        # Mapping updated after inspecting raw data (dados.agricultura.gov.br)
        renames = {
            "Safra": "safra",
            "Especie": "especie",
            "Categoria": "categoria",
            "Cultivar": "cultivar_raw",
            "Municipio": "municipio",
            "UF": "uf",
            "Status": "status",
            "Data do Plantio": "data_plantio",
            "Data de Colheita": "data_colheita",
            "Area": "area_ha",
            "Producao bruta": "producao_bruta_t",
            "Producao estimada": "producao_est_t",
            "DS_SAFRA": "safra",
            "DS_ESPECIE": "especie",
            "DS_CATEGORIA": "categoria",
            "DS_CULTIVAR": "cultivar_raw",
            "DS_MUNICIPIO": "municipio",
            "DS_UF": "uf",
            "DS_STATUS": "status",
            "DT_PLANTIO": "data_plantio",
            "DT_COLHEITA": "data_colheita",
            "NR_AREA": "area_ha",
            "NR_PRODUCAO_BRUTA": "producao_bruta_t",
            "NR_PRODUCAO_EST": "producao_est_t",
        }

        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns=renames)

        # Number typing and cleaning
        num_cols = ["area_ha", "producao_bruta_t", "producao_est_t"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")

        # Create the 'cultura' column for dimension mapping
        if "especie" in df.columns:
            df["cultura"] = normalize_string(df["especie"])
        elif "Especie" in df.columns:
            df["cultura"] = normalize_string(df["Especie"])

        df = self._validate_production_dates(df)
        return self._deduplicate_production(df)

    @staticmethod
    def _empty_quality_metrics():
        return {
            "rows_input": 0,
            "dates_accepted": 0,
            "dates_corrected": 0,
            "dates_rejected": 0,
            "chronology_rejected": 0,
            "duplicate_rows_consolidated": 0,
            "duplicate_groups_with_date_conflicts": 0,
            "rows_output": 0,
            "quarantine_records": 0,
        }

    @staticmethod
    def _parse_safra(value):
        """Return the inclusive crop-year bounds, accepting 2023/24 and 2023/2024."""
        match = re.fullmatch(r"\s*(\d{4})\s*[/\-]\s*(\d{2}|\d{4})\s*", str(value or ""))
        if not match:
            return None
        start = int(match.group(1))
        end_text = match.group(2)
        if len(end_text) == 2:
            end = (start // 100) * 100 + int(end_text)
            if end < start:
                end += 100
        else:
            end = int(end_text)
        if end < start or end - start > 2:
            return None
        return start, end

    @staticmethod
    def _row_fingerprint(row):
        values = ["" if pd.isna(value) else str(value) for value in row]
        return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()

    def _validate_production_dates(self, df):
        metrics = self._empty_quality_metrics()
        metrics["rows_input"] = len(df)
        quarantine = []
        date_cols = [column for column in ("data_plantio", "data_colheita") if column in df.columns]

        # Fingerprints make both audit records and tie-breaking independent of input order.
        fingerprint_cols = sorted(df.columns)
        df["_source_fingerprint"] = df[fingerprint_cols].apply(self._row_fingerprint, axis=1)

        for column in date_cols:
            original_column = f"_{column}_original"
            df[original_column] = df[column]
            parsed_values = []
            for _, row in df.iterrows():
                parsed, rule, reason = self._validate_date(row[column], row.get("safra"))
                parsed_values.append(parsed)
                if rule == "accepted":
                    metrics["dates_accepted"] += 1
                elif rule == "year_suffix_corrected":
                    metrics["dates_corrected"] += 1
                    quarantine.append(self._audit_record(row, column, row[column], parsed, rule, ""))
                elif reason:
                    metrics["dates_rejected"] += 1
                    quarantine.append(self._audit_record(row, column, row[column], parsed, rule, reason))
            df[column] = pd.to_datetime(pd.Series(parsed_values, index=df.index), errors="coerce")

        if {"data_plantio", "data_colheita"}.issubset(df.columns):
            invalid_order = (
                df["data_plantio"].notna() & df["data_colheita"].notna() & (df["data_colheita"] < df["data_plantio"])
            )
            for index in df.index[invalid_order]:
                row = df.loc[index]
                quarantine.append(
                    self._audit_record(
                        row,
                        "data_colheita",
                        row["_data_colheita_original"],
                        None,
                        "chronology_rejected",
                        "data_colheita_anterior_data_plantio",
                    )
                )
            count = int(invalid_order.sum())
            metrics["chronology_rejected"] = count
            metrics["dates_rejected"] += count
            # Do not persist a misleading half-pair. The business row remains usable.
            df.loc[invalid_order, ["data_plantio", "data_colheita"]] = pd.NaT

        self._write_quarantine(quarantine)
        metrics["quarantine_records"] = len(quarantine)
        self.quality_metrics = metrics
        self.log.info("Qualidade de datas SIGEF: %s", metrics)
        return df

    @staticmethod
    def _validate_date(value, safra):
        if value is None or pd.isna(value) or not str(value).strip():
            return pd.NaT, "empty", ""
        match = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", str(value))
        if not match:
            return pd.NaT, "rejected", "formato_data_invalido"
        bounds = SigefPipeline._parse_safra(safra)
        if bounds is None:
            return pd.NaT, "rejected", "safra_ausente_ou_invalida"
        day, month, raw_year = map(int, match.groups())
        minimum, maximum = bounds[0] - 1, bounds[1] + 1
        if minimum <= raw_year <= maximum:
            candidate_years = [raw_year]
            rule = "accepted"
        else:
            suffix = raw_year % 100
            candidate_years = [year for year in range(minimum, maximum + 1) if year % 100 == suffix]
            rule = "year_suffix_corrected"
        if len(candidate_years) != 1:
            return pd.NaT, "rejected", "ano_fora_janela_sem_correcao_univoca"
        try:
            parsed = pd.Timestamp(year=candidate_years[0], month=month, day=day)
        except ValueError:
            return pd.NaT, "rejected", "data_calendario_invalida"
        return parsed, rule, ""

    @staticmethod
    def _audit_record(row, field, original, corrected, rule, reason):
        return {
            "source_fingerprint": row["_source_fingerprint"],
            "safra": row.get("safra"),
            "especie": row.get("especie"),
            "cultivar_raw": row.get("cultivar_raw"),
            "municipio": row.get("municipio"),
            "uf": row.get("uf"),
            "campo": field,
            "valor_original": original,
            "valor_corrigido": "" if corrected is None or pd.isna(corrected) else corrected.strftime("%d/%m/%Y"),
            "regra_aplicada": rule,
            "motivo_rejeicao": reason,
        }

    def _write_quarantine(self, records):
        columns = [
            "source_fingerprint",
            "safra",
            "especie",
            "cultivar_raw",
            "municipio",
            "uf",
            "campo",
            "valor_original",
            "valor_corrigido",
            "regra_aplicada",
            "motivo_rejeicao",
        ]
        quarantine = pd.DataFrame(records, columns=columns).sort_values(
            ["source_fingerprint", "campo", "regra_aplicada"], ignore_index=True
        )
        directory = os.path.dirname(os.path.abspath(self.quarantine_path))
        os.makedirs(directory, exist_ok=True)
        temporary_path = f"{self.quarantine_path}.tmp"
        quarantine.to_csv(temporary_path, index=False, encoding="utf-8")
        os.replace(temporary_path, self.quarantine_path)

    @staticmethod
    def _quality_score(df):
        valid_dates = sum(df[column].notna().astype(int) for column in ("data_plantio", "data_colheita"))
        original_dates = sum(
            df.get(f"_{column}_original", pd.Series(index=df.index, dtype=object))
            .fillna("")
            .astype(str)
            .str.strip()
            .ne("")
            .astype(int)
            for column in ("data_plantio", "data_colheita")
        )
        # Prefer two valid dates, then one, then genuinely empty dates, and finally rejected dates.
        return valid_dates * 10 - (original_dates - valid_dates)

    def _deduplicate_production(self, df):
        natural_key = ["municipio", "uf", "safra", "especie", "cultivar_raw", "categoria"]
        if not all(column in df.columns for column in natural_key):
            self.quality_metrics["rows_output"] = len(df)
            return df.drop(columns=[column for column in df.columns if column.startswith("_")], errors="ignore")

        df = df.copy()
        df["_quality_score"] = self._quality_score(df)
        duplicate_mask = df.duplicated(natural_key, keep=False)
        conflicts = 0
        if duplicate_mask.any():
            original_columns = ["_data_plantio_original", "_data_colheita_original"]
            date_signature = df.loc[duplicate_mask, natural_key + original_columns].copy()
            date_signature["_dates"] = (
                date_signature["_data_plantio_original"].fillna("").astype(str)
                + "|"
                + date_signature["_data_colheita_original"].fillna("").astype(str)
            )
            conflicts = int((date_signature.groupby(natural_key, dropna=False)["_dates"].nunique() > 1).sum())

        before = len(df)
        df = df.sort_values(
            natural_key + ["_quality_score", "_source_fingerprint"],
            ascending=[True] * len(natural_key) + [False, True],
            na_position="last",
            kind="stable",
        ).drop_duplicates(natural_key, keep="first")
        self.quality_metrics["duplicate_rows_consolidated"] = before - len(df)
        self.quality_metrics["duplicate_groups_with_date_conflicts"] = conflicts
        self.quality_metrics["rows_output"] = len(df)
        self.log.info("Qualidade final SIGEF: %s", self.quality_metrics)
        return df.drop(columns=[column for column in df.columns if column.startswith("_")], errors="ignore")

    def _clean_reserva_semente(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()

        renames = {
            "TIPOPERIODO": "tipo_periodo",
            "PERIODO": "periodo",
            "AREATOTAL": "area_total_ha",
            "MUNICIPIO": "municipio",
            "UF": "uf",
            "ESPECIE": "especie",
            "CULTIVAR": "cultivar_raw",
            "AREAPLANTADA": "area_plantada_ha",
            "AREAESTIMADA": "area_estimada_ha",
            "QUANTRESERVADA": "quantidade_reservada_t",
            "DATAPLANTIA": "data_plantio",
            "DATAPLANTIO": "data_plantio",
        }
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns=renames)

        num_cols = ["area_total_ha", "area_plantada_ha", "area_estimada_ha", "quantidade_reservada_t"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")

        if "data_plantio" in df.columns:
            df["data_plantio"] = pd.to_datetime(df["data_plantio"], format="mixed", dayfirst=True, errors="coerce")

        if "especie" in df.columns:
            df["cultura"] = normalize_string(df["especie"])

        return df

    def load(self, df_dict: dict, lookups: dict) -> str:
        if not isinstance(df_dict, dict):
            return "0 registros (formato inválido)"

        map_cult = lookups["culturas"]
        map_mun_name = lookups["municipios_nome"]
        total = 0

        for key, df in df_dict.items():
            if df.empty:
                continue
            df_f = df.copy()
            df_f["id_cultura"] = df_f["cultura"].apply(lambda x: get_cultura_id(x, map_cult))
            df_f["id_municipio"] = map_municipio_by_name(df_f, map_mun_name)
            df_f = df_f.dropna(subset=["id_cultura", "id_municipio"])

            if key == "campos_producao":
                index = ["id_cultura", "id_municipio", "safra", "especie", "cultivar_raw", "categoria"]
                upsert_data(FatoSigefProducao, df_f, index_elements=index)
            elif key == "reserva_semente":
                index = ["id_cultura", "id_municipio", "periodo", "especie", "cultivar_raw"]
                upsert_data(FatoSigefReservaSemente, df_f, index_elements=index)

            total += len(df_f)
            self.log.info(f"Fato SIGEF ({key}): Upsert concluído.")

        return f"{total} registros upserted (total)"
