#!/usr/bin/env python3
"""Validate that the PostgreSQL warehouse has the required tables and data."""

from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg2


@dataclass(frozen=True)
class TableCheck:
    name: str
    required: bool = True


TABLES = [
    TableCheck("dim_cultura"),
    TableCheck("dim_municipio"),
    TableCheck("dim_mantenedor"),
    TableCheck("fato_registro_cultivares"),
    TableCheck("fato_producao_pam"),
    TableCheck("fato_risco_zarc"),
    TableCheck("fato_producao_conab"),
    TableCheck("fato_precos_conab_mensal"),
    TableCheck("fato_precos_conab_semanal"),
    TableCheck("fato_agrofit"),
    TableCheck("fato_fertilizantes_estabelecimentos"),
    TableCheck("fato_sigef_producao"),
    TableCheck("fato_sigef_reserva_semente"),
    TableCheck("fato_meteorologia"),
    TableCheck("fato_ndvi_satelite"),
]


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def connect():
    return psycopg2.connect(
        host=env("POSTGRES_HOST", "postgres"),
        port=env("POSTGRES_PORT", "5432"),
        dbname=env("POSTGRES_DB"),
        user=env("POSTGRES_USER"),
        password=env("POSTGRES_PASSWORD"),
    )


def main() -> int:
    failures = []
    with connect() as conn:
        with conn.cursor() as cur:
            print("table,status,rows")
            for table in TABLES:
                cur.execute("SELECT to_regclass(%s)", (table.name,))
                exists = cur.fetchone()[0] is not None
                if not exists:
                    print(f"{table.name},missing,0")
                    failures.append(f"{table.name}: missing")
                    continue

                cur.execute(f"SELECT COUNT(*) FROM {table.name}")
                rows = int(cur.fetchone()[0])
                status = "ok" if rows > 0 else "empty"
                print(f"{table.name},{status},{rows}")
                if table.required and rows == 0:
                    failures.append(f"{table.name}: empty")

    if failures:
        print("\nValidation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nValidation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
