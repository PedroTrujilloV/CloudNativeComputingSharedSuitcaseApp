from datetime import datetime, timezone

from sqlalchemy.orm import Session

from adapters.database.models import ScoreModel
from domain.models.score import Score
from domain.ports.score_repository_port import ScoreRepositoryPort


class SQLAlchemyScoreRepositoryAdapter(ScoreRepositoryPort):
    """SQLAlchemy adapter for the Score (Utilidad) repository port.

    Team decision: one current score per offer. ``upsert`` replaces the
    existing row's value (and ``updatedAt``) when the offer already has a
    score, so repeated writes keep a single source of truth per offer.
    """

    def __init__(self, session: Session):
        self.session = session

    def upsert(self, score: Score) -> Score:
        model = self._find_by_offer(score.offer_id)

        if model is None:
            model = ScoreModel(
                id=score.id,
                offerId=score.offer_id,
                value=score.value,
                createdAt=score.created_at,
                updatedAt=score.updated_at,
            )
            self.session.add(model)
        else:
            model.value = score.value
            model.updatedAt = score.updated_at

        self.session.commit()
        self.session.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, score_id: str) -> Score | None:
        model = self.session.get(ScoreModel, score_id)
        return self._to_domain(model) if model else None

    def get_by_offer_id(self, offer_id: str) -> Score | None:
        model = self._find_by_offer(offer_id)
        return self._to_domain(model) if model else None

    def delete(self, offer_id: str) -> bool:
        model = self._find_by_offer(offer_id)
        if model is None:
            return False

        self.session.delete(model)
        self.session.commit()
        return True

    def count(self) -> int:
        return self.session.query(ScoreModel).count()

    def delete_all(self) -> int:
        deleted_items = self.session.query(ScoreModel).delete()
        self.session.commit()
        return deleted_items

    def _find_by_offer(self, offer_id: str) -> ScoreModel | None:
        return (
            self.session.query(ScoreModel)
            .filter(ScoreModel.offerId == offer_id)
            .first()
        )

    @staticmethod
    def _to_utc(value: datetime) -> datetime:
        """Normalize a persisted timestamp to timezone-aware UTC.

        SQLite stores naive datetimes, so a read-back value may lose its
        tzinfo; it is always interpreted as UTC.
        """
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @classmethod
    def _to_domain(cls, model: ScoreModel) -> Score:
        return Score(
            id=model.id,
            offer_id=model.offerId,
            value=model.value,
            created_at=cls._to_utc(model.createdAt),
            updated_at=cls._to_utc(model.updatedAt),
        )
