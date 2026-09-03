import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""

    @classmethod
    @property
    @lru_cache()
    def app_name(self) -> str:
        return os.getenv("APP_NAME", "rf003_create_post_app")

    @classmethod
    @property
    @lru_cache()
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "DEBUG")

    @classmethod
    @property
    def users_service_url(self) -> str:
        """Base URL of the Users service (auth validation target).

        In Minikube/EKS the service is reachable through the cluster DNS
        name ``users-app-service``; locally it defaults to localhost:8000
        so the orchestrator can be tested next to a running users_app.
        """
        return os.getenv("USERS_SERVICE_URL", "http://localhost:8000")

    @classmethod
    @property
    def routes_service_url(self) -> str:
        """Base URL of the Routes service (route find-or-create target).

        In Minikube/EKS the service is reachable through the cluster DNS
        name ``routes-app-service``; locally it defaults to localhost:8001.
        """
        return os.getenv("ROUTES_SERVICE_URL", "http://localhost:8001")

    @classmethod
    @property
    def posts_service_url(self) -> str:
        """Base URL of the Posts service (post creation target).

        In Minikube/EKS the service is reachable through the cluster DNS
        name ``posts-app-service``; locally it defaults to localhost:8002.
        """
        return os.getenv("POSTS_SERVICE_URL", "http://localhost:8002")

    @classmethod
    @property
    def http_timeout(self) -> float:
        """Timeout in seconds for downstream HTTP calls."""
        return float(os.getenv("HTTP_TIMEOUT", "5"))
