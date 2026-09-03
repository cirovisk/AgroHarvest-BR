"""
Generic orchestrator.
Registry + BaseSource = no hardcoded imports here.
Iterates over the registry and calls `.run()`. Practical polymorphism.
Clean and easy to maintain.
"""

import argparse
import gc
import logging
import re
import time
from datetime import datetime, timezone

from logging_config import configure_logging, set_run_id

configure_logging()

# IMPORTANT: import the sources package to trigger @register
import pipeline.sources  # noqa: F401
from config import CULTURAS_ALVO
from db.manager import get_db, init_db
from pipeline.alert_manager import AlertManager
from pipeline.dimensions import (
    carregar_municipios_completo_ibge,
    preencher_dimensao_cultura,
)
from pipeline.registry import get_sources

log = logging.getLogger(__name__)


ZERO_RESULT_RE = re.compile(r"\b0\s+registro", re.IGNORECASE)


def main():
    sources = get_sources()

    parser = argparse.ArgumentParser(description="Pipeline AgroHarvest BR")
    parser.add_argument(
        "--sources", nargs="+", choices=sources.keys(), default=list(sources.keys()), help="Data sources to process"
    )
    parser.add_argument("--refresh", action="store_true", help="Force cache refresh")
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    set_run_id(run_id)
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

        success, partial, failed = [], [], []
        alert = AlertManager()
        _start = time.monotonic()

        for name in args.sources:
            source_cls = sources.get(name)
            if not source_cls:
                log.warning(f"Source '{name}' is not registered; skipping.")
                continue
            pipeline = source_cls()
            source_start = time.monotonic()
            try:
                result = pipeline.run(lookups, refresh=args.refresh)
                duration = time.monotonic() - source_start
                result_status = result.get("status", "success") if isinstance(result, dict) else "success"
                if result_status == "partial":
                    partial.append(name)
                    for warning in result.get("warnings", []):
                        alert.record_warning(f"{name}: {warning}")
                elif result_status == "failure":
                    failed.append(name)
                else:
                    success.append(name)
                alert.record_source(name, result_status, duration, result=result)
                log.info(
                    f"✓ {name}: {result}",
                    extra={
                        "event": "pipeline_source_complete",
                        "source": name,
                        "status": result_status,
                        "duration_seconds": round(duration, 2),
                    },
                )
                if ZERO_RESULT_RE.search(str(result)):
                    warning = f"{name}: pipeline returned zero records"
                    alert.record_warning(warning)
                    log.warning(warning, extra={"event": "pipeline_source_warning", "source": name, "status": "empty"})
            except Exception as e:
                failed.append(name)
                duration = time.monotonic() - source_start
                alert.record_source(name, "failure", duration, error=str(e))
                log.error(
                    f"✗ {name}: {e}",
                    extra={
                        "event": "pipeline_source_complete",
                        "source": name,
                        "status": "failure",
                        "duration_seconds": round(duration, 2),
                    },
                )
                alert.record_error(name, e)
            finally:
                gc.collect()

        log.info("--- Pipeline completed ---")
        log.info(f"Success: {success}")
        if partial:
            log.warning(f"Partial: {partial}")
        if failed:
            log.warning(f"Failures: {failed}")

        alert.send_report(success=success, partial=partial, failed=failed, duration=time.monotonic() - _start)


if __name__ == "__main__":
    main()
