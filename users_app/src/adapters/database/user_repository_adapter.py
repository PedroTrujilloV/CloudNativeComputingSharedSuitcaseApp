from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from adapters.database.models import UserModel
from domain.models.user import User, UserStatus
from domain.ports.user_repository_port import UserRepositoryPort
from errors import UserAlreadyExistsError, UserNotFoundError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SQLAlchemyUserRepositoryAdapter(UserRepositoryPort):
    """PostgreSQL-backed user repository using SQLAlchemy."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, user: User) -> User:
        """Persist a new user. Password must already be hashed."""
        now = _utc_now()
        model = UserModel(
            id=user.id or str(uuid4()),
            username=user.username,
            email=str(user.email),
            phoneNumber=user.phoneNumber,
            dni=user.dni,
            fullName=user.fullName,
            password=user.password,
            salt=user.salt,
            token=user.token,
            status=user.status.value,
            ruv=user.ruv,
            expireAt=user.expireAt,
            createdAt=user.createdAt or now,
            updatedAt=user.updatedAt or now,
        )
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise UserAlreadyExistsError(
                "username or email already exists"
            ) from exc
        self.session.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, user_id: str) -> User | None:
        model = self.session.get(UserModel, user_id)
        return self._to_domain(model) if model else None

    def get_by_username(self, username: str) -> User | None:
        model = (
            self.session.query(UserModel)
            .filter(UserModel.username == username)
            .one_or_none()
        )
        return self._to_domain(model) if model else None

    def get_by_token(self, token: str) -> User | None:
        model = (
            self.session.query(UserModel)
            .filter(UserModel.token == token)
            .one_or_none()
        )
        return self._to_domain(model) if model else None

    def update(self, user: User) -> User:
        if not user.id:
            raise UserNotFoundError("User id is required for update")

        model = self.session.get(UserModel, user.id)
        if not model:
            raise UserNotFoundError(f"User with id {user.id} not found")

        model.username = user.username
        model.email = str(user.email)
        model.phoneNumber = user.phoneNumber
        model.dni = user.dni
        model.fullName = user.fullName
        model.password = user.password
        model.salt = user.salt
        model.token = user.token
        model.status = user.status.value
        model.ruv = user.ruv
        model.expireAt = user.expireAt
        model.updatedAt = _utc_now()

        self.session.commit()
        self.session.refresh(model)
        return self._to_domain(model)

    def set_ruv(self, user_id: str, ruv: str) -> User:
        """Store the RUV on the user without touching status or updatedAt."""
        model = self.session.get(UserModel, user_id)
        if not model:
            raise UserNotFoundError(f"User with id {user_id} not found")

        model.ruv = ruv
        self.session.commit()
        self.session.refresh(model)
        return self._to_domain(model)

    def count(self) -> int:
        return self.session.query(UserModel).count()

    def delete_all(self) -> None:
        self.session.query(UserModel).delete()
        self.session.commit()

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            phoneNumber=model.phoneNumber,
            dni=model.dni,
            fullName=model.fullName,
            password=model.password,
            salt=model.salt,
            token=model.token,
            status=UserStatus(model.status),
            ruv=model.ruv,
            expireAt=model.expireAt,
            createdAt=model.createdAt,
            updatedAt=model.updatedAt,
        )
