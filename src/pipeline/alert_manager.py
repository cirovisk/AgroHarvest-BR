"""
Pipeline Alert Manager (PostgreSQL).
Saves execution status JSON files in data/logs/.
"""

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
        self.started_at: float = time.monotonic()
        # Filesystem-safe UTC ISO timestamp
        self.start_ts: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        self._log_dir: Path = Path(os.getenv("LOG_STATUS_PATH", "data/logs"))

    def record_error(self, source: str, exc: Exception) -> None:
        self.errors.append({"source": source, "message": str(exc)})

    def record_warning(self, message: str) -> None:
        self.warnings.append(message)

    def send_report(self, success: list[str], failed: list[str], duration: float | None = None) -> None:
        if duration is None:
            duration = time.monotonic() - self.started_at

        total = len(success) + len(failed)
        if not failed:
            status = "SUCCESS"
        elif success:
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
            "sources_failed": failed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }

        self._save_json(payload)

    def _save_json(self, payload: dict) -> None:
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            ts_safe = self.start_ts.replace(":", "-")
            out_path = self._log_dir / f"pipeline_status_{ts_safe}.json"
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info(f"[AlertManager] Status written to: {out_path}")
        except Exception as e:
            log.error(f"[AlertManager] Failed to write status JSON: {e}")
