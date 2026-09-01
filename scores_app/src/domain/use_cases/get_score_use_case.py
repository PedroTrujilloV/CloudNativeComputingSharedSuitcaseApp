from domain.models.score import Score
from domain.ports.score_repository_port import ScoreRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import ScoreNotFoundError


class GetScoreUseCase(BaseUseCase):
    """Use case for retrieving a score by its id."""

    def __init__(self, score_repository: ScoreRepositoryPort):
        self.score_repository = score_repository

    def execute(self, score_id: str) -> Score:
        """Retrieve a score by its id, raising when it does not exist."""
        score = self.score_repository.get_by_id(score_id)
        if score is None:
            raise ScoreNotFoundError("Score not found")
        return score
