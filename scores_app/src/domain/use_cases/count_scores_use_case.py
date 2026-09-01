from domain.ports.score_repository_port import ScoreRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class CountScoresUseCase(BaseUseCase):
    """Use case for counting the persisted scores."""

    def __init__(self, score_repository: ScoreRepositoryPort):
        self.score_repository = score_repository

    def execute(self) -> int:
        """Return the number of persisted scores."""
        return self.score_repository.count()
