from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from domain.use_cases.base_use_case import BaseUseCase
from entrypoints.api.deps import (
    get_authenticate_user_use_case,
    get_count_users_use_case,
    get_create_user_use_case,
    get_current_user_use_case,
    get_db_session,
    get_reset_users_use_case,
    get_update_user_use_case,
)
from entrypoints.api.schemas.user_schemas import (
    AuthUserRequest,
    AuthUserResponse,
    CountUsersResponse,
    CreateUserRequest,
    CreateUserResponse,
    MeUserResponse,
    ResetUsersResponse,
    UpdateUserRequest,
    UpdateUserResponse,
)
from errors import InvalidTokenError, UserAlreadyExistsError, UserNotFoundError

bearer_scheme = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/users")


@router.get("/ping", response_class=PlainTextResponse)
def health_check():
    """Healthcheck endpoint."""
    return "pong"


@router.post("", response_model=CreateUserResponse, status_code=201)
@router.post("/", response_model=CreateUserResponse, status_code=201, include_in_schema=False)
def create_user(
    payload: CreateUserRequest,
    session: Session = Depends(get_db_session),
):
    """Create a new user."""
    use_case: BaseUseCase = get_create_user_use_case(session)
    try:
        user = use_case.execute(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            dni=payload.dni,
            fullName=payload.fullName,
            phoneNumber=payload.phoneNumber,
        )
    except UserAlreadyExistsError:
        return Response(status_code=412)

    return CreateUserResponse(
        id=user.id,
        createdAt=user.createdAt.strftime("%Y-%m-%dT%H:%M:%S"),
    )


@router.post("/auth", response_model=AuthUserResponse, status_code=200)
def authenticate_user(
    payload: AuthUserRequest,
    session: Session = Depends(get_db_session),
):
    """Authenticate a user and issue an opaque token."""
    use_case: BaseUseCase = get_authenticate_user_use_case(session)
    try:
        user = use_case.execute(username=payload.username, password=payload.password)
    except UserNotFoundError:
        return Response(status_code=404)

    return AuthUserResponse(
        id=user.id,
        token=user.token,
        expireAt=user.expireAt.strftime("%Y-%m-%dT%H:%M:%S"),
    )


@router.get("/me", response_model=MeUserResponse, status_code=200)
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db_session),
):
    """Return the authenticated user profile."""
    if credentials is None or not credentials.credentials:
        return Response(status_code=403)

    use_case: BaseUseCase = get_current_user_use_case(session)
    try:
        user = use_case.execute(token=credentials.credentials)
    except InvalidTokenError:
        return Response(status_code=401)

    return MeUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        fullName=user.fullName,
        dni=user.dni,
        phoneNumber=user.phoneNumber,
        status=user.status.value,
    )


@router.get("/count", response_model=CountUsersResponse, status_code=200)
def count_users(session: Session = Depends(get_db_session)):
    """Return the number of stored users."""
    use_case: BaseUseCase = get_count_users_use_case(session)
    return CountUsersResponse(count=use_case.execute())


@router.post("/reset", response_model=ResetUsersResponse, status_code=200)
def reset_users(session: Session = Depends(get_db_session)):
    """Delete all user records."""
    use_case: BaseUseCase = get_reset_users_use_case(session)
    use_case.execute()
    return ResetUsersResponse(msg="Todos los datos fueron eliminados")


@router.patch("/{user_id}", response_model=UpdateUserResponse, status_code=200)
def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    session: Session = Depends(get_db_session),
):
    """Update allowed public profile fields for a user (no auth required)."""
    use_case: BaseUseCase = get_update_user_use_case(session)
    try:
        use_case.execute(
            user_id=user_id,
            fields_set=payload.model_fields_set,
            status=payload.status,
            dni=payload.dni,
            fullName=payload.fullName,
            phoneNumber=payload.phoneNumber,
        )
    except UserNotFoundError:
        return Response(status_code=404)

    return UpdateUserResponse(msg="el usuario ha sido actualizado")
