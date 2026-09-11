import os
from functools import lru_cache


class Settings:
    """Application settings loaded from environment variables."""

    @classmethod
    @property
    @lru_cache()
    def app_name(self) -> str:
        return os.getenv("APP_NAME", "rf005_query_post_app")

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
        name `users-app-service`; locally it defaults to localhost:8000.
        """
        return os.getenv("USERS_SERVICE_URL", "http://localhost:8000")

    @classmethod
    @property
    def posts_service_url(self) -> str:
        """Base URL of the Posts service (post fetch + ownership check).

        In Minikube/EKS the service is reachable through the cluster DNS
        name `posts-app-service`; locally it defaults to localhost:8002.
        """
        return os.getenv("POSTS_SERVICE_URL", "http://localhost:8002")

    @classmethod
    @property
    def routes_service_url(self) -> str:
        """Base URL of the Routes service (route resolution target).

        In Minikube/EKS the service is reachable through the cluster DNS
        name `routes-app-service`; locally it defaults to localhost:8001.
        """
        return os.getenv("ROUTES_SERVICE_URL", "http://localhost:8001")

    @classmethod
    @property
    def offers_service_url(self) -> str:
        """Base URL of the Offers service (offers fetch target).

        In Minikube/EKS the service is reachable through the cluster DNS
        name `offers-app-service`; locally it defaults to localhost:8003.
        """
        return os.getenv("OFFERS_SERVICE_URL", "http://localhost:8003")

    @classmethod
    @property
    def scores_service_url(self) -> str:
        """Base URL of the Score service (score lookup target).

        In Minikube/EKS the service is reachable through the cluster DNS
        name `scores-app-service`; locally it defaults to localhost:8004.
        """
        return os.getenv("SCORES_SERVICE_URL", "http://localhost:8004")

    @classmethod
    @property
    def http_timeout(self) -> float:
        """Timeout in seconds for downstream HTTP calls."""
        return float(os.getenv("HTTP_TIMEOUT", "5"))
