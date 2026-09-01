from domain.models.score import Score
from domain.ports.score_repository_port import ScoreRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class UpsertScoreUseCase(BaseUseCase):
    """Use case for creating or updating the score of an offer (RF-004).

    Idempotent by offer: the repository stores one current score per offer,
    so repeated writes with the same ``offerId`` update the value in place.
    """

    def __init__(self, score_repository: ScoreRepositoryPort):
        self.score_repository = score_repository

    def execute(self, score: Score) -> Score:
        """Persist the score, creating it or updating the existing row."""
        return self.score_repository.upsert(score)
