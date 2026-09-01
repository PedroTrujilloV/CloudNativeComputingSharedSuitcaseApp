from domain.models.score import Score
from domain.ports.score_repository_port import ScoreRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class GetScoreByOfferUseCase(BaseUseCase):
    """Use case for querying the score of an offer (RF-005).

    Null-safe: a missing score is a valid state (the offer simply has no
    computed utility yet), so the use case returns ``None`` instead of
    raising.
    """

    def __init__(self, score_repository: ScoreRepositoryPort):
        self.score_repository = score_repository

    def execute(self, offer_id: str) -> Score | None:
        """Return the score for an offer, or ``None`` when not defined yet."""
        return self.score_repository.get_by_offer_id(offer_id)
