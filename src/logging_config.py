"""Centralized logging setup for pipeline and API processes."""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

run_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("run_id", default="-")


def set_run_id(run_id: str) -> None:
    run_id_var.set(run_id)


class RunContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = run_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", "-"),
            "message": record.getMessage(),
        }
        for key in ("event", "source", "stage", "status", "rows", "duration_seconds", "error_id", "method", "path"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _level() -> int:
    return getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)


def configure_logging(default_file: str = "data/logs/app.log") -> None:
    log_format = os.getenv("LOG_FORMAT", "text").lower()
    log_file = os.getenv("LOG_FILE", default_file)
    max_bytes = int(os.getenv("LOG_MAX_BYTES", "5242880"))
    backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    context_filter = RunContextFilter()

    if log_format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] [run_id=%(run_id)s] %(name)s: %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(context_filter)

    file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    logging.basicConfig(level=_level(), handlers=[console, file_handler], force=True)
