from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import AuthService
from app.config import get_settings
from app.database import get_session

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
SESSION_COOKIE_NAME = "game_hub_session"


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    created_at: str


class AuthResponse(BaseModel):
    user: UserResponse


class ErrorResponse(BaseModel):
    code: str
    message: str


SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at.isoformat(),
    )


def auth_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )


async def current_user(
    session: SessionDependency,
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> User:
    user = await AuthService(session).get_user_from_token(token)
    if user is None:
        raise auth_error("AUTHENTICATION_REQUIRED", "Autenticazione richiesta.", status.HTTP_401_UNAUTHORIZED)
    return user


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(credentials: Credentials, session: SessionDependency) -> AuthResponse:
    try:
        user = await AuthService(session).register(credentials.email, credentials.password)
    except ValueError as error:
        if str(error) == "EMAIL_ALREADY_EXISTS":
            raise auth_error("EMAIL_ALREADY_EXISTS", "Questa email e' gia registrata.", status.HTTP_409_CONFLICT) from error
        raise auth_error("PASSWORD_INVALID", "La password deve contenere da 8 a 128 caratteri.", status.HTTP_422_UNPROCESSABLE_ENTITY) from error
    return AuthResponse(user=user_response(user))


@router.post("/login", response_model=AuthResponse)
async def login(credentials: Credentials, response: Response, session: SessionDependency) -> AuthResponse:
    user = await AuthService(session).authenticate(credentials.email, credentials.password)
    if user is None:
        raise auth_error("INVALID_CREDENTIALS", "Email o password non validi.", status.HTTP_401_UNAUTHORIZED)
    token = await AuthService(session).create_session(user)
    set_session_cookie(response, token)
    return AuthResponse(user=user_response(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDependency,
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> None:
    await AuthService(session).delete_session(token)
    response.delete_cookie(SESSION_COOKIE_NAME)


@router.get("/me", response_model=AuthResponse)
async def me(user: Annotated[User, Depends(current_user)]) -> AuthResponse:
    return AuthResponse(user=user_response(user))
