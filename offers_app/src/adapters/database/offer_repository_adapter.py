from uuid import UUID

from adapters.database.models import OfferModel
from domain.models.offer import Offer
from domain.ports.offer_repository_port import OfferRepositoryPort
from sqlalchemy.orm import Session


class SQLAlchemyOfferRepositoryAdapter(OfferRepositoryPort):
    def __init__(self, session: Session):
        self.session = session

    def create(self, offer: Offer) -> Offer:
        model = OfferModel(
            id=offer.id,
            postId=offer.post_id,
            userId=offer.user_id,
            description=offer.description,
            size=offer.size,
            fragile=offer.fragile,
            offer=offer.offer,
            createdAt=offer.created_at,
        )

        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, offer_id: UUID) -> Offer | None:
        model = self.session.get(OfferModel, offer_id)
        return self._to_domain(model) if model else None

    def search(
        self,
        post_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> list[Offer]:
        query = self.session.query(OfferModel)

        if post_id is not None:
            query = query.filter(OfferModel.postId == post_id)
        if user_id is not None:
            query = query.filter(OfferModel.userId == user_id)

        return [self._to_domain(model) for model in query.all()]

    def delete(self, offer_id: UUID) -> bool:
        model = self.session.get(OfferModel, offer_id)
        if model is None:
            return False

        self.session.delete(model)
        self.session.commit()
        return True

    def count(self) -> int:
        return self.session.query(OfferModel).count()

    def delete_all(self) -> int:
        deleted_items = self.session.query(OfferModel).delete()
        self.session.commit()
        return deleted_items

    @staticmethod
    def _to_domain(model: OfferModel) -> Offer:
        return Offer(
            id=model.id,
            post_id=model.postId,
            user_id=model.userId,
            description=model.description,
            size=model.size,
            fragile=model.fragile,
            offer=model.offer,
            created_at=model.createdAt,
        )
