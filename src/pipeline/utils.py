"""
Shared utilities: generic upsert, string normalization, crop lookup,
and municipality mapping by name.
"""

import logging
import unicodedata

import pandas as pd
from sqlalchemy import BigInteger, Integer, inspect
from sqlalchemy.dialects.postgresql import insert

from db.manager import engine

log = logging.getLogger(__name__)


# String Normalization


def normalize_string(series: pd.Series) -> pd.Series:
    """Normalize names by removing accents and lowercasing."""

    def remove_accents(input_str):
        if not isinstance(input_str, str):
            return input_str
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

    return series.apply(remove_accents).str.strip()


# Crop Lookup (with Synonyms)


def get_cultura_id(nome_cultura, mapping):
    if not nome_cultura:
        return None

    def norm(s):
        s = str(s).lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFKD", s) if unicodedata.category(c) != "Mn")
        return s.replace("-", " ").replace("_", " ")

    # Scientific synonym dictionary (SIGEF/MAPA -> common name)
    SYNONYMS = {
        "glycine max": "soja",
        "zea mays": "milho",
        "triticum aestivum": "trigo",
        "gossypium hirsutum": "algodao",
        "avena strigosa": "aveia",
        "avena sativa": "aveia",
        "saccharum": "cana-de-acucar",
    }

    # Try an exact match first, before normalizing
    if nome_cultura in mapping:
        return mapping[nome_cultura]

    nombre_norm = norm(nome_cultura)

    # Apply synonym translation
    for syn, target in SYNONYMS.items():
        if syn in nombre_norm:
            nombre_norm = target
            break

    for alvo, cid in mapping.items():
        alvo_norm = norm(alvo)
        # Match exact terms or whole words to avoid errors such as strigosa -> trigo
        if f" {alvo_norm} " in f" {nombre_norm} " or f" {nombre_norm} " in f" {alvo_norm} ":
            return cid
        if alvo_norm == nombre_norm:
            return cid
    return None


# Municipality Mapping by Name


def map_municipio_by_name(df, map_mun_name):
    """Vectorized id_municipio lookup through (name, state), replacing apply(axis=1)."""
    has_mun = df["municipio"].notna() & df["uf"].notna()
    keys = df["municipio"].str.lower().str.strip() + "|" + df["uf"].str.upper()
    lookup = {f"{n}|{u}": mid for (n, u), mid in map_mun_name.items()}
    return keys.map(lookup).where(has_mun)


# Generic Upsert (PostgreSQL ON CONFLICT)

# ORM metadata cache by model to avoid repeated inspect() calls
_model_meta_cache = {}


def _get_model_meta(model):
    if model not in _model_meta_cache:
        mapper = inspect(model)
        _model_meta_cache[model] = {
            "pk_cols": [c.key for c in mapper.primary_key],
            "int_cols": set(c.key for c in mapper.column_attrs if isinstance(c.expression.type, (Integer, BigInteger))),
            "all_cols": set(c.key for c in mapper.column_attrs),
        }
    return _model_meta_cache[model]


def upsert_data(model, df, index_elements, chunk_size=1000, connection=None):
    if df.empty:
        return

    # Ensure there are no duplicates in the whole set to avoid CardinalityViolation (Postgres)
    df = df.drop_duplicates(subset=index_elements, keep="last")

    # Model metadata (cached across calls)
    meta = _get_model_meta(model)
    pk_cols = meta["pk_cols"]
    model_int_cols = meta["int_cols"]
    model_cols = meta["all_cols"]

    def _execute_chunks(conn):
        for i in range(0, len(df), chunk_size):
            chunk_df = df.iloc[i : i + chunk_size]
            records = chunk_df.to_dict(orient="records")

            valid_records = []
            for r in records:
                valid_row = {}
                for k, v in r.items():
                    if k in model_cols:
                        if pd.isna(v):
                            valid_row[k] = None
                        elif k in model_int_cols:
                            try:
                                # Ensure IDs and other integer fields are int, not float (for example, 4.0 -> 4)
                                valid_row[k] = int(float(v))
                            except (ValueError, TypeError):
                                valid_row[k] = None
                        else:
                            valid_row[k] = v
                valid_records.append(valid_row)

            if not valid_records:
                continue

            stmt = insert(model).values(valid_records)

            # Columns to update on conflict (all except index, PK, and automatic metadata fields)
            update_cols = {
                c: stmt.excluded[c]
                for c in model_cols
                if c not in index_elements and c not in pk_cols and c != "data_modificacao"
            }

            upsert_stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=update_cols)

            conn.execute(upsert_stmt)

    if connection is not None:
        _execute_chunks(connection)
    else:
        # Single connection for all chunks; avoids opening/closing a transaction per chunk
        with engine.begin() as conn:
            _execute_chunks(conn)
