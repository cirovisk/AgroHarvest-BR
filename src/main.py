"""
Generic orchestrator.
Registry + BaseSource = no hardcoded imports here.
Iterates over the registry and calls `.run()`. Practical polymorphism.
Clean and easy to maintain.
"""

import argparse
import gc
import logging
import time

# IMPORTANT: import the sources package to trigger @register
import pipeline.sources  # noqa: F401
from db.manager import get_db, init_db
from pipeline.alert_manager import AlertManager
from pipeline.dimensions import (
    carregar_municipios_completo_ibge,
    preencher_dimensao_cultura,
)
from pipeline.registry import get_sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

from config import CULTURAS_ALVO


def main():
    sources = get_sources()

    parser = argparse.ArgumentParser(description="Pipeline AgroHarvest BR")
    parser.add_argument(
        "--sources", nargs="+", choices=sources.keys(), default=list(sources.keys()), help="Data sources to process"
    )
    parser.add_argument("--refresh", action="store_true", help="Force cache refresh")
    args = parser.parse_args()

    log.info("--- Starting AgroHarvest BR Pipeline (Registry) ---")
    init_db()

    from contextlib import closing

    with closing(next(get_db())) as db:
        # Shared lookups (built once and used by every source)
        lookups = {
            "db": db,
            "culturas": preencher_dimensao_cultura(db, CULTURAS_ALVO),
            "municipios_ibge": {},
            "municipios_nome": {},
        }
        map_ibge, map_nome = carregar_municipios_completo_ibge(db)
        lookups["municipios_ibge"] = map_ibge
        lookups["municipios_nome"] = map_nome

        success, failed = [], []
        alert = AlertManager()
        _start = time.monotonic()

        for name in args.sources:
            source_cls = sources.get(name)
            if not source_cls:
                log.warning(f"Source '{name}' is not registered; skipping.")
                continue
            pipeline = source_cls()
            try:
                result = pipeline.run(lookups)
                success.append(name)
                log.info(f"✓ {name}: {result}")
            except Exception as e:
                failed.append(name)
                log.error(f"✗ {name}: {e}")
                alert.record_error(name, e)
            finally:
                gc.collect()

        log.info("--- Pipeline completed ---")
        log.info(f"Success: {success}")
        if failed:
            log.warning(f"Failures: {failed}")

        alert.send_report(success=success, failed=failed, duration=time.monotonic() - _start)


if __name__ == "__main__":
    main()
