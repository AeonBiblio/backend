from tests.factories import auth_headers, create_payment_profile, create_subscription_plan, create_user


async def test_subscription_flow_lists_plan_subscribes_cancels_and_lists_payments(client, db_session):
    user = await create_user(db_session, email="reader@example.com", username="reader")
    await create_payment_profile(db_session, user=user)
    plan = await create_subscription_plan(db_session, name="Monthly")

    plans = await client.get("/subscriptions/plans")
    assert plans.status_code == 200
    assert plans.json()[0]["id"] == str(plan.id)

    subscribed = await client.post(
        "/subscriptions/subscribe",
        headers=auth_headers(user),
        json={"plan_id": str(plan.id), "auto_renew": True},
    )
    assert subscribed.status_code == 201
    assert subscribed.json()["status"] == "active"

    duplicate = await client.post(
        "/subscriptions/subscribe",
        headers=auth_headers(user),
        json={"plan_id": str(plan.id), "auto_renew": True},
    )
    assert duplicate.status_code == 409

    current = await client.get("/subscriptions/me", headers=auth_headers(user))
    assert current.status_code == 200

    payments = await client.get("/subscriptions/me/payments", headers=auth_headers(user))
    assert payments.status_code == 200
    assert payments.json()[0]["external_payment_id"] == "mock_1111"

    cancelled = await client.post("/subscriptions/me/cancel", headers=auth_headers(user))
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_subscribe_returns_404_for_missing_plan(client, db_session):
    user = await create_user(db_session, email="reader@example.com", username="reader")
    await create_payment_profile(db_session, user=user)

    response = await client.post(
        "/subscriptions/subscribe",
        headers=auth_headers(user),
        json={
            "plan_id": "00000000-0000-0000-0000-000000000001",
            "auto_renew": True,
        },
    )

    assert response.status_code == 404


async def test_current_subscription_returns_null_when_missing(client, db_session):
    user = await create_user(db_session, email="reader@example.com", username="reader")

    response = await client.get("/subscriptions/me", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() is None
