from adapters.security.password_hasher import hash_password
from domain.models.user import User, UserStatus
from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase


class CreateUserUseCase(BaseUseCase):
    """Create a new user with a hashed password."""

    def __init__(self, user_repository: UserRepositoryPort):
        self.user_repository = user_repository

    def execute(
        self,
        *,
        username: str,
        password: str,
        email: str,
        dni: str | None = None,
        fullName: str | None = None,
        phoneNumber: str | None = None,
    ) -> User:
        password_hash, salt = hash_password(password)
        user = User(
            username=username,
            email=email,
            phoneNumber=phoneNumber,
            dni=dni,
            fullName=fullName,
            password=password_hash,
            salt=salt,
            status=UserStatus.POR_VERIFICAR,
        )
        return self.user_repository.create(user)
