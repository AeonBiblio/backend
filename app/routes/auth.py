from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.user import RefreshRequest, TokenPair, UserLogin, UserOut, UserRegister

router = APIRouter()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where((User.email == body.email) | (User.username == body.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email или username уже занят")

    user = User(
        email=body.email,
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    if user.is_blocked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")

    access_token = create_access_token(str(user.id))
    refresh_token_raw = create_refresh_token(str(user.id))

    token_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_password(refresh_token_raw),
        expires_at=datetime.fromtimestamp(
            decode_token(refresh_token_raw)["exp"], tz=timezone.utc
        ),
        created_at=datetime.now(timezone.utc),
    )
    db.add(token_record)
    await db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token_raw)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный refresh-токен"
    )
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_exc
        user_id: str = payload.get("sub")
    except jwt.PyJWTError:
        raise credentials_exc

    result = await db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
    tokens = result.scalars().all()

    matched_token = None
    for t in tokens:
        if t.revoked_at is None and verify_password(body.refresh_token, t.token_hash):
            matched_token = t
            break

    if not matched_token:
        raise credentials_exc

    matched_token.revoked_at = datetime.now(timezone.utc)

    new_access = create_access_token(user_id)
    new_refresh_raw = create_refresh_token(user_id)

    new_token_record = RefreshToken(
        user_id=matched_token.user_id,
        token_hash=hash_password(new_refresh_raw),
        expires_at=datetime.fromtimestamp(
            decode_token(new_refresh_raw)["exp"], tz=timezone.utc
        ),
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_token_record)
    await db.commit()

    return TokenPair(access_token=new_access, refresh_token=new_refresh_raw)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        user_id: str = payload.get("sub")
    except jwt.PyJWTError:
        return

    result = await db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
    tokens = result.scalars().all()

    for t in tokens:
        if t.revoked_at is None and verify_password(body.refresh_token, t.token_hash):
            t.revoked_at = datetime.now(timezone.utc)
            await db.commit()
            break
