from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthSession, User
from app.auth.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    validate_password_length,
    verify_password,
)

SESSION_DURATION = timedelta(days=30)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(self, email: str, password: str) -> User:
        normalized_email = email.strip().lower()
        if not validate_password_length(password):
            raise ValueError("PASSWORD_INVALID")

        existing_user = await self.session.scalar(
            select(User).where(User.email == normalized_email)
        )
        if existing_user is not None:
            raise ValueError("EMAIL_ALREADY_EXISTS")

        user = User(
            id=str(uuid4()),
            email=normalized_email,
            password_hash=hash_password(password),
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User | None:
        normalized_email = email.strip().lower()
        user = await self.session.scalar(select(User).where(User.email == normalized_email))
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user

    async def create_session(self, user: User) -> str:
        token = create_session_token()
        auth_session = AuthSession(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=int((datetime.now(timezone.utc) + SESSION_DURATION).timestamp()),
        )
        self.session.add(auth_session)
        await self.session.commit()
        return token

    async def get_user_from_token(self, token: str | None) -> User | None:
        if not token:
            return None

        auth_session = await self.session.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hash_session_token(token),
                AuthSession.expires_at > int(datetime.now(timezone.utc).timestamp()),
            )
        )
        if auth_session is None:
            return None
        return await self.session.get(User, auth_session.user_id)

    async def delete_session(self, token: str | None) -> None:
        if not token:
            return
        await self.session.execute(
            delete(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
        )
        await self.session.commit()
