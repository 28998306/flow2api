from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import ACCESS_TOKEN, decode_token, hash_api_key
from app.models.api_key import DownstreamApiKey
from app.models.enums import ApiKeyStatus, UserRole
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录已失效,请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise cred_exc
    payload = decode_token(token)
    if not payload or payload.get("type") != ACCESS_TOKEN:
        raise cred_exc
    user_id = payload.get("sub")
    if user_id is None:
        raise cred_exc
    user = await db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise cred_exc
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


async def get_openai_api_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise cred_exc
    raw_key = authorization.split(" ", 1)[1].strip()
    if not raw_key:
        raise cred_exc

    api_key = await db.scalar(
        select(DownstreamApiKey).where(
            DownstreamApiKey.key_hash == hash_api_key(raw_key),
            DownstreamApiKey.is_deleted.is_(False),
        )
    )
    now = datetime.now(timezone.utc)
    if (
        not api_key
        or api_key.status != ApiKeyStatus.active
        or (api_key.expires_at and api_key.expires_at <= now)
    ):
        raise cred_exc

    user = await db.get(User, api_key.user_id) if api_key.user_id else None
    if user is None:
        user = await db.scalar(select(User).where(User.role == UserRole.admin, User.is_active.is_(True)))
    if user is None or not user.is_active:
        raise cred_exc

    api_key.last_used_at = now
    await db.flush()
    return user
