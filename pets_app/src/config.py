import os
from functools import lru_cache


class Settings:
    """Application settings."""

    @classmethod
    @property
    @lru_cache()
    def app_name(self) -> str:
        return os.getenv("APP_NAME", "Pet example")

    @classmethod
    @property
    @lru_cache()
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "DEBUG")
