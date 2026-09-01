from domain.ports.score_repository_port import ScoreRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class ResetScoresUseCase(BaseUseCase):
    """Use case for deleting all persisted scores."""

    def __init__(self, score_repository: ScoreRepositoryPort):
        self.score_repository = score_repository

    def execute(self) -> int:
        """Delete every score and return the number of rows removed."""
        return self.score_repository.delete_all()
