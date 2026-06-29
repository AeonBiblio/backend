from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.core.dependencies import get_current_user, require_active_subscription
from app.core.security import create_access_token, create_refresh_token
from app.models.subscription import SubscriptionStatus
from tests.factories import create_active_subscription, create_subscription_plan, create_user


async def test_get_current_user_returns_user_for_valid_access_token(db_session):
    user = await create_user(db_session, email="current@example.com", username="current")

    current_user = await get_current_user(db_session, create_access_token(str(user.id)))

    assert current_user.id == user.id


async def test_get_current_user_rejects_refresh_token(db_session):
    user = await create_user(db_session, email="refresh@example.com", username="refresh")

    with pytest.raises(HTTPException) as exc:
        await get_current_user(db_session, create_refresh_token(str(user.id)))

    assert exc.value.status_code == 401


async def test_get_current_user_rejects_blocked_user(db_session):
    user = await create_user(
        db_session,
        email="blocked@example.com",
        username="blocked",
        is_blocked=True,
    )

    with pytest.raises(HTTPException) as exc:
        await get_current_user(db_session, create_access_token(str(user.id)))

    assert exc.value.status_code == 403


async def test_require_active_subscription_returns_user_when_active(db_session):
    user = await create_user(db_session, email="sub@example.com", username="sub")
    plan = await create_subscription_plan(db_session)
    await create_active_subscription(db_session, user=user, plan=plan)

    current_user = await require_active_subscription(user, db_session)

    assert current_user.id == user.id


async def test_require_active_subscription_rejects_expired_subscription(db_session):
    user = await create_user(db_session, email="expired@example.com", username="expired")
    plan = await create_subscription_plan(db_session)
    subscription = await create_active_subscription(
        db_session,
        user=user,
        plan=plan,
        expires_delta=timedelta(days=-1),
    )
    subscription.status = SubscriptionStatus.active
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await require_active_subscription(user, db_session)

    assert exc.value.status_code == 403
