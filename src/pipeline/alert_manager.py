"""
Pipeline Alert Manager (PostgreSQL).
Saves execution status JSON files in data/logs/.
"""

import csv
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


class AlertManager:
    """Collect execution metrics and persist status JSON."""

    def __init__(self, pipeline_name: str = "AgroHarvest BR (PostgreSQL)"):
        self.pipeline_name = pipeline_name
        self.errors: list[dict] = []
        self.warnings: list[str] = []
        self.sources: list[dict] = []
        self.started_at: float = time.monotonic()
        # Filesystem-safe UTC ISO timestamp
        self.start_ts: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        self._log_dir: Path = Path(os.getenv("LOG_STATUS_PATH", "data/logs"))

    def record_error(self, source: str, exc: Exception) -> None:
        self.errors.append({"source": source, "message": str(exc)})

    def record_warning(self, message: str) -> None:
        self.warnings.append(message)

    def record_source(
        self,
        source: str,
        status: str,
        duration: float,
        result: object | None = None,
        error: str | None = None,
    ) -> None:
        self.sources.append(
            {
                "source": source,
                "status": status,
                "duration_seconds": round(duration, 2),
                "result": result,
                "error": error,
            }
        )

    def send_report(
        self,
        success: list[str],
        failed: list[str],
        duration: float | None = None,
        partial: list[str] | None = None,
    ) -> None:
        partial = partial or []
        if duration is None:
            duration = time.monotonic() - self.started_at

        total = len(success) + len(partial) + len(failed)
        if not failed and not partial:
            status = "SUCCESS"
        elif not failed and partial:
            status = "PARTIAL_SUCCESS"
        elif success or partial:
            status = "PARTIAL_FAILURE"
        else:
            status = "FAILURE"

        payload = {
            "run_id": self.start_ts,
            "pipeline": self.pipeline_name,
            "status": status,
            "duration_seconds": round(duration, 1),
            "total_sources": total,
            "sources_ok": success,
            "sources_partial": partial,
            "sources_failed": failed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "sources": self.sources,
        }

        self._save_json(payload)
        self._save_metrics_csv()

    def _save_json(self, payload: dict) -> None:
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            ts_safe = self.start_ts.replace(":", "-")
            out_path = self._log_dir / f"pipeline_status_{ts_safe}.json"
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info(f"[AlertManager] Status written to: {out_path}")
        except Exception as e:
            log.error(f"[AlertManager] Failed to write status JSON: {e}")

    def _save_metrics_csv(self) -> None:
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            ts_safe = self.start_ts.replace(":", "-")
            out_path = self._log_dir / f"pipeline_metrics_{ts_safe}.csv"
            with out_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["source", "status", "duration_seconds", "result", "error"],
                )
                writer.writeheader()
                rows = []
                for source in self.sources:
                    row = source.copy()
                    if not isinstance(row.get("result"), (str, type(None))):
                        row["result"] = json.dumps(row["result"], ensure_ascii=False, sort_keys=True)
                    rows.append(row)
                writer.writerows(rows)
            log.info(f"[AlertManager] Metrics written to: {out_path}")
        except Exception as e:
            log.error(f"[AlertManager] Failed to write metrics CSV: {e}")
