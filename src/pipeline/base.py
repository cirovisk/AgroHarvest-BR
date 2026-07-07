"""
Base contract for all data-source pipelines.
Each source MUST implement extract(), clean(), and load().
"""

import logging
import os
import time
from abc import ABC, abstractmethod


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

    def run(self, lookups: dict, **kwargs) -> str:
        """Run the full pipeline: extract -> clean -> load."""
        self.log.info("Starting pipeline...")
        raw = self.extract(**kwargs)
        clean = self.clean(raw)
        result = self.load(clean, lookups)
        self.log.info(f"Pipeline completed: {result}")
        return result

    def is_file_stale(self, path: str, threshold_days: int = 30) -> bool:
        """
        Check whether a local file is stale based on its age.
        """
        if not os.path.exists(path):
            return True
        file_age_days = (time.time() - os.path.getmtime(path)) / (24 * 3600)
        return file_age_days > threshold_days
