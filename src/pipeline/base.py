"""
Base contract for all data-source pipelines.
Each source MUST implement extract(), clean(), and load().
"""

import logging
import os
import time
from abc import ABC, abstractmethod


def _row_count(data) -> int | None:
    if data is None:
        return None
    if isinstance(data, dict):
        total = 0
        found = False
        for value in data.values():
            if hasattr(value, "__len__"):
                total += len(value)
                found = True
        return total if found else None
    if hasattr(data, "__len__") and not isinstance(data, (str, bytes)):
        return len(data)
    return None


class BaseSource(ABC):
    """Interface every data source must follow."""

    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def extract(self, **kwargs):
        """Extract raw data from the source. Returns a DataFrame, dict, or generator."""
        ...

    @abstractmethod
    def clean(self, raw_data):
        """Clean and standardize raw data."""
        ...

    @abstractmethod
    def load(self, clean_data, lookups: dict):
        """Load clean data into the database through upsert."""
        ...

    def run(self, lookups: dict, **kwargs) -> object:
        """Run the full pipeline: extract -> clean -> load."""
        source = self.__class__.__name__
        self.log.info("Starting pipeline...", extra={"event": "pipeline_source_start", "source": source})

        refresh = bool(kwargs.pop("refresh", False))
        if refresh and hasattr(self, "use_cache"):
            self.use_cache = False

        started = time.monotonic()
        raw = self.extract(**kwargs)
        self.log.info(
            "Extract completed",
            extra={
                "event": "pipeline_stage",
                "source": source,
                "stage": "extract",
                "status": "success",
                "rows": _row_count(raw),
                "duration_seconds": round(time.monotonic() - started, 2),
            },
        )

        started = time.monotonic()
        clean = self.clean(raw)
        self.log.info(
            "Clean completed",
            extra={
                "event": "pipeline_stage",
                "source": source,
                "stage": "clean",
                "status": "success",
                "rows": _row_count(clean),
                "duration_seconds": round(time.monotonic() - started, 2),
            },
        )

        started = time.monotonic()
        result = self.load(clean, lookups)
        self.log.info(
            f"Pipeline completed: {result}",
            extra={
                "event": "pipeline_stage",
                "source": source,
                "stage": "load",
                "status": "success",
                "duration_seconds": round(time.monotonic() - started, 2),
            },
        )
        return result

    def is_file_stale(self, path: str, threshold_days: int = 30) -> bool:
        """
        Check whether a local file is stale based on its age.
        """
        if not os.path.exists(path):
            return True
        file_age_days = (time.time() - os.path.getmtime(path)) / (24 * 3600)
        return file_age_days > threshold_days
