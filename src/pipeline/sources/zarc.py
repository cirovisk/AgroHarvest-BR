"""Pipeline do Zoneamento Agrícola de Risco Climático (ZARC/MAPA)."""

import hashlib
import json
import logging
import os
import re
from pathlib import Path

import pandas as pd
import requests

from db.manager import FatoRiscoZARC
from pipeline.base import BaseSource
from pipeline.registry import register
from pipeline.utils import get_cultura_id, normalize_string, upsert_data

log = logging.getLogger(__name__)


@register("zarc")
class ZarcPipeline(BaseSource):
    """Baixa e processa a tábua de risco do MAPA em blocos."""

    from config import CULTURAS_ALVO

    TARGET_CROPS = CULTURAS_ALVO
    DEFAULT_SAFRA = "2025-2026"
    RESOURCE_IDS = {
        "2025-2026": "f9d597f9-0fee-47eb-9344-8642274ca9da",
        "2026-2027": "139e5a60-1f43-4cc8-aeab-a35dbbf816c0",
    }
    CROP_ALIASES = {
        "soja": ("soja",),
        "milho": ("milho",),
        "trigo": ("trigo",),
        "algodao": ("algodao",),
    }

    def __init__(
        self,
        use_cache: bool = True,
        data_dir: str = "data/zarc",
        chunksize: int = 50000,
        safra: str | None = None,
        resource_id: str | None = None,
        resource_url: str | None = None,
    ):
        super().__init__()
        self.use_cache = use_cache
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chunksize = chunksize
        self.safra = self._validate_safra(safra or os.getenv("ZARC_SAFRA", self.DEFAULT_SAFRA))
        self.resource_id = resource_id or os.getenv("ZARC_RESOURCE_ID") or self.RESOURCE_IDS.get(self.safra)
        self.resource_url = resource_url or os.getenv("ZARC_RESOURCE_URL") or self._official_url()
        self.last_result: dict | None = None
        self._coverage_rows = {crop: 0 for crop in self.TARGET_CROPS}

    @staticmethod
    def _validate_safra(safra: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{4}", safra):
            raise ValueError("ZARC_SAFRA deve usar o formato AAAA-AAAA")
        start, end = map(int, safra.split("-"))
        if end != start + 1:
            raise ValueError("ZARC_SAFRA deve representar anos consecutivos")
        return safra

    def _official_url(self) -> str:
        if not self.resource_id:
            raise ValueError(
                f"Safra ZARC {self.safra} sem recurso conhecido; defina ZARC_RESOURCE_ID ou ZARC_RESOURCE_URL"
            )
        return (
            "https://dados.agricultura.gov.br/dataset/6d3d141c-885e-41a4-ab7f-dc8ff323b96f/"
            f"resource/{self.resource_id}/download/dados-abertos-tabua-de-risco-safra-{self.safra}.csv"
        )

    @property
    def raw_file(self) -> Path:
        return self.data_dir / f"zarc_raw_{self.safra}.csv"

    @property
    def manifest_file(self) -> Path:
        return self.data_dir / f"zarc_{self.safra}.manifest.json"

    def crop_file(self, crop: str) -> Path:
        return self.data_dir / f"zarc_{self.safra}_{crop}.csv"

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _write_manifest(self) -> dict:
        metadata = {
            "safra": self.safra,
            "resource_id": self.resource_id,
            "url": self.resource_url,
            "raw_file": self.raw_file.name,
            "sha256": self._sha256(self.raw_file),
        }
        self.manifest_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return metadata

    def _cache_is_valid(self) -> bool:
        if not self.use_cache or not self.raw_file.exists():
            return False
        if not self.manifest_file.exists():
            self._write_manifest()
            return True
        try:
            metadata = json.loads(self.manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return (
            metadata.get("safra") == self.safra
            and metadata.get("resource_id") == self.resource_id
            and metadata.get("url") == self.resource_url
            and metadata.get("sha256") == self._sha256(self.raw_file)
        )

    @staticmethod
    def _normalize_crop(value) -> str:
        normalized = normalize_string(pd.Series([value], dtype="object")).iloc[0]
        return str(normalized).replace("_", "-") if pd.notna(normalized) else ""

    def _crop_masks(self, chunk: pd.DataFrame) -> dict[str, pd.Series]:
        name_col = next((c for c in ("Nome_cultura", "nome_cultura", "cultura") if c in chunk.columns), None)
        names = (
            chunk[name_col].astype(str).map(self._normalize_crop)
            if name_col
            else pd.Series("", index=chunk.index, dtype="object")
        )
        masks = {}
        for crop in self.TARGET_CROPS:
            aliases = self.CROP_ALIASES.get(crop, (crop,))
            masks[crop] = names.map(lambda value: any(alias in value for alias in aliases))
        return masks

    def run(self, lookups: dict, **kwargs) -> dict:
        """Executa a carga e informa explicitamente lacunas de cobertura."""
        self.log.info("Iniciando pipeline ZARC (streaming) para a safra %s...", self.safra)
        self._coverage_rows = {crop: 0 for crop in self.TARGET_CROPS}
        self.download_data(force_refresh=bool(kwargs.get("refresh")))
        total = 0
        for chunk in self.extract():
            clean_chunk = self.clean(chunk)
            for crop, count in clean_chunk["cultura"].value_counts().items():
                if crop in self._coverage_rows:
                    self._coverage_rows[crop] += int(count)
            total += self.load(clean_chunk, lookups)

        missing = [crop for crop, count in self._coverage_rows.items() if count == 0]
        status = "partial" if missing else "success"
        metadata = json.loads(self.manifest_file.read_text(encoding="utf-8")) if self.manifest_file.exists() else {}
        self.last_result = {
            "source": "zarc",
            "status": status,
            "rows_extracted": sum(self._coverage_rows.values()),
            "rows_loaded": total,
            "coverage_expected": list(self.TARGET_CROPS),
            "coverage_observed": [crop for crop, count in self._coverage_rows.items() if count > 0],
            "warnings": [f"Cultura sem registros na safra {self.safra}: {crop}" for crop in missing],
            "snapshot_metadata": metadata,
        }
        self.log.info("Pipeline ZARC concluído: %s", self.last_result)
        return self.last_result

    def download_data(self, force_refresh: bool = False):
        """Obtém o consolidado da safra e cria caches individuais por cultura."""
        missing_crops = [crop for crop in self.TARGET_CROPS if not self.crop_file(crop).exists()]
        cache_is_valid = not force_refresh and self._cache_is_valid()
        if not missing_crops and cache_is_valid:
            self.log.info("Cache ZARC da safra %s validado por SHA-256.", self.safra)
            return
        if not cache_is_valid:
            self.log.info("Baixando a tábua ZARC da safra %s...", self.safra)
            part_file = self.raw_file.with_suffix(".csv.part")
            headers = {"User-Agent": "cultivares-tcc/1.0 (+https://dados.agricultura.gov.br/)"}
            try:
                with requests.get(self.resource_url, stream=True, timeout=60, headers=headers) as response:
                    response.raise_for_status()
                    with part_file.open("wb") as output:
                        for block in response.iter_content(chunk_size=1024 * 1024):
                            if block:
                                output.write(block)
                part_file.replace(self.raw_file)
            except Exception:
                part_file.unlink(missing_ok=True)
                raise
            self._write_manifest()
            # Um novo consolidado invalida todos os derivados, não apenas os ausentes.
            missing_crops = list(self.TARGET_CROPS)
        self._split_raw_file(missing_crops)

    def _split_raw_file(self, crops: list[str]):
        headers_written = {crop: False for crop in crops}
        for crop in crops:
            self.crop_file(crop).unlink(missing_ok=True)
        reader = pd.read_csv(
            self.raw_file, sep=";", encoding="utf-8-sig", on_bad_lines="skip", chunksize=200000, dtype=str
        )
        for chunk in reader:
            masks = self._crop_masks(chunk)
            for crop in crops:
                selected = chunk.loc[masks[crop]]
                if selected.empty:
                    continue
                selected.to_csv(self.crop_file(crop), sep=";", index=False, mode="a", header=not headers_written[crop])
                headers_written[crop] = True
        self.log.info("Cache ZARC separado por cultura para a safra %s.", self.safra)

    def extract(self, **kwargs):
        """Gera blocos dos caches pertencentes exclusivamente à safra configurada."""
        for crop in self.TARGET_CROPS:
            cache_file = self.crop_file(crop)
            if not cache_file.exists():
                self.log.warning("Cultura %s ausente no ZARC da safra %s.", crop, self.safra)
                continue
            try:
                with cache_file.open("rb") as stream:
                    compression = "gzip" if stream.read(2) == b"\x1f\x8b" else None
                reader = pd.read_csv(
                    cache_file,
                    sep=";",
                    encoding="utf-8-sig",
                    on_bad_lines="skip",
                    chunksize=self.chunksize,
                    compression=compression,
                    dtype=str,
                )
                for chunk in reader:
                    chunk["cultura_cache"] = crop
                    yield chunk
            except Exception as error:
                self.log.error("Erro no cache ZARC %s: %s", cache_file.name, error)

    def get_municipios_only(self):
        """Extrai os municípios dos caches da safra configurada."""
        municipalities = []
        for chunk in self.extract():
            clean = self.clean(chunk)
            required = ["cod_municipio_ibge", "municipio", "uf"]
            if all(column in clean.columns for column in required):
                municipalities.append(clean[required].drop_duplicates())
        if not municipalities:
            return pd.DataFrame()
        return pd.concat(municipalities).drop_duplicates(subset=["cod_municipio_ibge"])

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        clean = df.copy()
        clean.columns = (
            clean.columns.str.lower()
            .str.replace(" ", "_", regex=False)
            .str.replace("-", "_", regex=False)
            .str.normalize("NFKD")
            .str.encode("ascii", errors="ignore")
            .str.decode("utf-8")
        )
        municipality_column = next((c for c in clean.columns if "ibge" in c or "cd_mun" in c or "geocodigo" in c), None)
        if municipality_column:
            clean = clean.rename(columns={municipality_column: "cod_municipio_ibge"})
        if "cod_cultura" in clean.columns:
            clean["cod_cultura_zarc"] = clean["cod_cultura"].astype(str).str.replace(r"\.0$", "", regex=True)
        else:
            clean["cod_cultura_zarc"] = pd.NA
        source_culture = clean.get(
            "nome_cultura",
            clean.get("cultura_raw", clean.get("cultura_cache", pd.Series("", index=clean.index))),
        )
        clean["cultura"] = normalize_string(source_culture.astype(str)).str.replace(" ", "-", regex=False)
        # O ZARC detalha algumas culturas por finalidade/safra; consolide
        # esses nomes na cultura-alvo para cobertura e dimensão consistentes.
        for target, aliases in self.CROP_ALIASES.items():
            mask = clean["cultura"].map(lambda value: any(alias in value for alias in aliases))
            clean.loc[mask, "cultura"] = target
        clean["finalidade"] = "nao-se-aplica"
        if "safraini" in clean.columns and "safrafin" in clean.columns:
            clean["safra"] = clean["safraini"].astype(str) + "-" + clean["safrafin"].astype(str)
        else:
            clean["safra"] = self.safra
        clean["safra"] = clean["safra"].where(clean["safra"].str.fullmatch(r"\d{4}-\d{4}"), self.safra)
        return clean

    def load(self, df: pd.DataFrame, lookups: dict) -> int:
        if df.empty:
            return 0
        frame = df.copy()
        frame["id_cultura"] = frame["cultura"].apply(lambda value: get_cultura_id(value, lookups["culturas"]))
        if "cod_municipio_ibge" not in frame.columns:
            return 0
        frame["cod_municipio_ibge"] = (
            frame["cod_municipio_ibge"].astype(str).str.replace(r"\.0$", "", regex=True).str[:7]
        )
        frame["id_municipio"] = frame["cod_municipio_ibge"].map(lookups["municipios_ibge"])
        period_columns = [column for column in frame.columns if re.fullmatch(r"dec\d+", column)]
        if period_columns:
            frame = frame.melt(
                id_vars=[column for column in frame.columns if column not in period_columns],
                value_vars=period_columns,
                var_name="periodo_plantio",
                value_name="risco_climatico",
            )
        if "cod_solo" in frame.columns:
            frame = frame.rename(columns={"cod_solo": "tipo_solo"})
        columns = [
            "id_cultura",
            "id_municipio",
            "tipo_solo",
            "periodo_plantio",
            "risco_climatico",
            "safra",
            "finalidade",
            "cod_cultura_zarc",
        ]
        frame = frame[[column for column in columns if column in frame.columns]]
        frame = frame.dropna(subset=["id_cultura", "id_municipio", "risco_climatico"])
        index_elements = [
            "id_cultura",
            "id_municipio",
            "tipo_solo",
            "periodo_plantio",
            "safra",
            "finalidade",
        ]
        upsert_data(FatoRiscoZARC, frame, index_elements=index_elements)
        self.log.info("Fato ZARC: %d registros processados neste bloco.", len(frame))
        return len(frame)
