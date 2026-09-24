import logging
from uuid import uuid4

from adapters.security.password_hasher import hash_password
from domain.models.user import User, UserStatus
from domain.ports.truenative_port import TrueNativeVerificationPort
from domain.ports.user_repository_port import UserRepositoryPort
from domain.use_cases.base_use_case import BaseUseCase
from errors import TrueNativeRequestError, TrueNativeUnreachableError

logger = logging.getLogger(__name__)

# Statuses TrueNative documents for POST /native/verify rejections: 400 for a
# malformed or incomplete request, 401 or 403 for secret token problems, and
# 409 when a verification for the same user and transaction is in progress.
_TRUE_NATIVE_REJECTION_STATUSES = (400, 401, 403, 409)


class CreateUserUseCase(BaseUseCase):
    """Create a new user and register the identity verification request.

    The user is stored with status POR_VERIFICAR, then the verification
    request is registered with the provider (TrueNative POST /native/verify)
    as a normal synchronous request response call, and the returned RUV is
    stored on the user record. When the provider rejects the request (400,
    401, 403 or 409) or cannot be reached, the user is marked NO_VERIFICADO
    and the creation still completes: the user exists and the outcome can be
    fixed later.
    """

    def __init__(
        self,
        user_repository: UserRepositoryPort,
        verification_provider: TrueNativeVerificationPort,
    ):
        self.user_repository = user_repository
        self.verification_provider = verification_provider

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
        user = self.user_repository.create(user)
        return self._register_verification(user)

    def _register_verification(self, user: User) -> User:
        transaction_identifier = str(uuid4())
        try:
            ruv = self.verification_provider.request_verification(
                user=user,
                user_identifier=user.id,
                transaction_identifier=transaction_identifier,
            )
        except TrueNativeRequestError as err:
            self._log_rejection(user, transaction_identifier, err)
            return self._mark_verification_failed(user)
        except TrueNativeUnreachableError as err:
            logger.error(
                "TrueNative could not register the verification request %s "
                "for user %s (%s); the user is marked NO_VERIFICADO",
                transaction_identifier,
                user.id,
                err,
            )
            return self._mark_verification_failed(user)

        user = self.user_repository.set_ruv(user.id, ruv)
        logger.info(
            "Verification request %s registered with TrueNative for user %s "
            "(RUV %s, status %s)",
            transaction_identifier,
            user.id,
            ruv,
            user.status.value,
        )
        return user

    def _log_rejection(
        self, user: User, transaction_identifier: str, err: TrueNativeRequestError
    ) -> None:
        if err.status_code in _TRUE_NATIVE_REJECTION_STATUSES:
            logger.warning(
                "TrueNative rejected the verification request %s for user %s "
                "with status %s (%s); the user is marked NO_VERIFICADO",
                transaction_identifier,
                user.id,
                err.status_code,
                err.detail,
            )
        else:
            logger.error(
                "TrueNative answered the verification request %s for user %s "
                "with unexpected status %s (%s); the user is marked "
                "NO_VERIFICADO",
                transaction_identifier,
                user.id,
                err.status_code,
                err.detail,
            )

    def _mark_verification_failed(self, user: User) -> User:
        """Set the user to NO_VERIFICADO and refresh updatedAt."""
        user.status = UserStatus.NO_VERIFICADO
        return self.user_repository.update(user)
